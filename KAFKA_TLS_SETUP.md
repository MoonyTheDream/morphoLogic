# Kafka TLS Setup Guide

Full encryption via Kafka SSL on port 9093.

**Overview:**
- certbot gets a dedicated Let's Encrypt cert (Caddy serves the ACME challenge)
- Kafka gets an SSL listener on port 9093 using that cert
- Python server and Godot client connect via TLS
- The godot-kafka-extension C++ code needs two new methods per class

---

## Step 0 — Pi setup

### a) Configure Caddy to serve ACME challenge files
Add to Caddyfile under your domain block:
```caddyfile
handle /.well-known/acme-challenge/* {
    root * /var/www/certbot-webroot
    file_server
}
```
```bash
sudo mkdir -p /var/www/certbot-webroot
sudo systemctl reload caddy
```

### b) Get cert with certbot
```bash
sudo apt install certbot
sudo certbot certonly --webroot -w /var/www/certbot-webroot -d <yourdomain>
# Cert files land at:
#   /etc/letsencrypt/live/<yourdomain>/fullchain.pem
#   /etc/letsencrypt/live/<yourdomain>/privkey.pem
# certbot's systemd timer handles renewal automatically
```

### c) Copy certs to a Kafka-accessible directory
The Let's Encrypt `privkey.pem` is `600` (root-only). The Bitnami container runs as user `1001` and cannot read it directly from `/etc/letsencrypt/live/`. Copy the certs to a dedicated directory:

```bash
sudo mkdir -p /etc/kafka-certs
sudo cp /etc/letsencrypt/live/<yourdomain>/fullchain.pem /etc/kafka-certs/
sudo cp /etc/letsencrypt/live/<yourdomain>/privkey.pem /etc/kafka-certs/
sudo chown -R 1001:1001 /etc/kafka-certs
sudo chmod 644 /etc/kafka-certs/fullchain.pem
sudo chmod 640 /etc/kafka-certs/privkey.pem
```

### d) Add post-renewal hook to reload Kafka
The hook must also refresh the copies in `/etc/kafka-certs/`:
```bash
sudo tee /etc/letsencrypt/renewal-hooks/post/reload-kafka.sh > /dev/null << 'EOF'
#!/bin/bash
cp /etc/letsencrypt/live/<yourdomain>/fullchain.pem /etc/kafka-certs/
cp /etc/letsencrypt/live/<yourdomain>/privkey.pem /etc/kafka-certs/
chown 1001:1001 /etc/kafka-certs/fullchain.pem /etc/kafka-certs/privkey.pem
chmod 640 /etc/kafka-certs/privkey.pem
docker restart morphoLogic_kafka
EOF
sudo chmod +x /etc/letsencrypt/renewal-hooks/post/reload-kafka.sh
```

### e) Configure Kafka SSL — docker-compose.yml
Kafka is a **bitnami/kafka Docker container** (`morphoLogic_kafka`).

Bitnami has two layers of TLS config that must both be set:
- `KAFKA_TLS_TYPE=PEM` — tells Bitnami's entrypoint script to expect PEM (not JKS). Without this, the script errors out looking for `.jks` files regardless of `KAFKA_CFG_SSL_*` vars.
- `KAFKA_TLS_CLIENT_AUTH=none` — Bitnami-level equivalent of `KAFKA_CFG_SSL_CLIENT_AUTH`.
- Bitnami expects certs at **fixed filenames** inside `/bitnami/kafka/config/certs/` — the `KAFKA_CFG_SSL_KEYSTORE_*` path vars are ignored when `KAFKA_TLS_TYPE=PEM`.
- The CONTROLLER listener must be on its own port (9094) — it cannot share port 9093 with the SSL listener.

**Full `docker-compose.yml`:**
```yaml
version: '1'

services:
  kafka:
    image: bitnami/kafka:latest
    container_name: morphoLogic_kafka
    ports:
      - "9092:9092"
      - "9093:9093"
    environment:
      - KAFKA_CFG_NODE_ID=0
      - KAFKA_CFG_PROCESS_ROLES=broker,controller
      - KAFKA_CFG_CONTROLLER_QUORUM_VOTERS=0@kafka:9094
      - KAFKA_CFG_LISTENERS=PLAINTEXT://localhost:9092,SSL://0.0.0.0:9093,CONTROLLER://kafka:9094
      - KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092,SSL://<yourdomain>:9093
      - KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT,SSL:SSL,CONTROLLER:PLAINTEXT
      - KAFKA_CFG_CONTROLLER_LISTENER_NAMES=CONTROLLER
      - KAFKA_CFG_INTER_BROKER_LISTENER_NAME=PLAINTEXT
      - KAFKA_TLS_TYPE=PEM
      - KAFKA_TLS_CLIENT_AUTH=none
      - KAFKA_KRAFT_CLUSTER_ID=<base64-uuid from: docker run --rm bitnami/kafka kafka-storage.sh random-uuid>
    volumes:
      - kafka_data:/bitnami/kafka
      - /etc/kafka-certs/fullchain.pem:/bitnami/kafka/config/certs/kafka.keystore.pem:ro
      - /etc/kafka-certs/privkey.pem:/bitnami/kafka/config/certs/kafka.keystore.key:ro
      - /etc/kafka-certs/fullchain.pem:/bitnami/kafka/config/certs/kafka.truststore.pem:ro
    restart: unless-stopped
    networks:
      - kafka_net

volumes:
  kafka_data:

networks:
  kafka_net:
    driver: bridge
```

Note: port 9094 (CONTROLLER) is internal — no `ports:` mapping needed.

### f) Open firewall port and forward on router
```bash
sudo ufw allow 9093/tcp
```
Also forward port 9093 TCP on your router to the Pi's local IP.

Bring up and verify:
```bash
docker compose up -d kafka
openssl s_client -connect <yourdomain>:9093 -brief
# Expected: CONNECTION ESTABLISHED, Verification: OK
```

---

## Step 1 — C++ extension: add SSL methods

Repo: https://github.com/MoonyTheDream/godot-kafka-extension

Both `KafkaProducer` and `KafkaConsumer` need **identical** changes.

### KafkaProducer.h / KafkaConsumer.h — add private members + public declarations
```cpp
private:
    String security_protocol = "";
    String ssl_ca_location = "";  // empty = use system CA bundle (Linux/Mac)

public:
    void set_security_protocol(const String &protocol);
    void set_ssl_ca_location(const String &path);
```

### KafkaProducer.cpp / KafkaConsumer.cpp — implement setters
```cpp
void KafkaProducer::set_security_protocol(const String &protocol) {
    security_protocol = protocol;
}
void KafkaProducer::set_ssl_ca_location(const String &path) {
    ssl_ca_location = path;
}
```

Apply to rdkafka conf **before `rd_kafka_new`** (in the lazy-init / `start()` block):
```cpp
if (!security_protocol.is_empty()) {
    conf->set("security.protocol",
              std::string(security_protocol.utf8().get_data()), errstr);
}
if (!ssl_ca_location.is_empty()) {
    conf->set("ssl.ca.location",
              std::string(ssl_ca_location.utf8().get_data()), errstr);
}
// Let's Encrypt → hostname verification works → do NOT disable it
```

### register_types.cpp — bind methods (×2, once per class)
```cpp
ClassDB::bind_method(D_METHOD("set_security_protocol", "protocol"),
                     &KafkaProducer::set_security_protocol);
ClassDB::bind_method(D_METHOD("set_ssl_ca_location", "path"),
                     &KafkaProducer::set_ssl_ca_location);
// Repeat for KafkaConsumer
```

After changes: **rebuild Linux `.so` + Windows `.dll`**, copy into `morphoLogicClient/bin/`.

**Windows clients:** librdkafka on Windows doesn't use the system cert store.
- Download `cacert.pem` from https://curl.se/ca/cacert.pem
- Save as `morphoLogicClient/cacert.pem`
- Windows clients set `sslCaLocation = "res://cacert.pem"` in their config

---

## Step 2 — Python server

### `morphoLogicEngine/src/morphologic_server/config.py`
Add two optional fields to `ServerSettings`:
```python
KAFKA_SECURITY_PROTOCOL: str = ""   # set to "ssl" to enable TLS
KAFKA_SSL_CA_LOCATION: str = ""     # leave empty on Linux (LE root is in system trust store)
```

### `morphoLogicEngine/src/morphologic_server/network/kafka.py`
Add a helper method and merge SSL config into all three conf dicts:
```python
def _ssl_conf(self) -> dict:
    if not settings.KAFKA_SECURITY_PROTOCOL:
        return {}
    c = {"security.protocol": settings.KAFKA_SECURITY_PROTOCOL}
    if settings.KAFKA_SSL_CA_LOCATION:
        c["ssl.ca.location"] = settings.KAFKA_SSL_CA_LOCATION
    return c
```
In `__enter__`:
```python
admin_conf    = {"bootstrap.servers": settings.KAFKA_SERVER, **self._ssl_conf()}
producer_conf = {"bootstrap.servers": settings.KAFKA_SERVER, "acks": "all", **self._ssl_conf()}
consumer_conf = {
    "bootstrap.servers": settings.KAFKA_SERVER,
    "group.id": settings.KAFKA_GROUP_ID,
    "auto.offset.reset": "earliest",
    "enable.partition.eof": False,
    **self._ssl_conf(),
}
```

### `morphoLogicEngine/src/morphologic_server/.env`
```
KAFKA_SERVER=<yourdomain>:9093
KAFKA_SECURITY_PROTOCOL=ssl
# KAFKA_SSL_CA_LOCATION=    ← leave empty on Linux
```

---

## Step 3 — Godot client

### `morphoLogicClient/client_config.cfg`
```ini
[kafka]
bootstrapServer = "<yourdomain>:9093"
securityProtocol = "ssl"
sslCaLocation = ""    # empty on Linux/Mac; "res://cacert.pem" on Windows
```

### `morphoLogicClient/ClientData.gd`
Add fields and read them alongside `bootstrap_server`:
```gdscript
var security_protocol: String = ""
var ssl_ca_location: String = ""

# In _ready(), in the config-reading block:
security_protocol = config.get_value("kafka", "securityProtocol", "")
ssl_ca_location   = config.get_value("kafka", "sslCaLocation", "")
```

### `morphoLogicClient/Kafka.gd`
After `set_bootstrap_servers()` calls, before `consumer.start()`:
```gdscript
if ClientData.security_protocol != "":
    consumer.set_security_protocol(ClientData.security_protocol)
    producer.set_security_protocol(ClientData.security_protocol)
    if ClientData.ssl_ca_location != "":
        var abs_path := ProjectSettings.globalize_path(ClientData.ssl_ca_location)
        consumer.set_ssl_ca_location(abs_path)
        producer.set_ssl_ca_location(abs_path)
```

---

## Verification

1. `openssl s_client -connect <yourdomain>:9093 -brief` → Let's Encrypt cert shown, no errors
2. `morphologic start -l` → server connects to Kafka on 9093, no SSL errors in logs
3. Godot client connects → full handshake → SURROUNDINGS_DATA arrives
4. `tcpdump -i eth0 port 9093 -A` on Pi → no plaintext JSON visible in output
