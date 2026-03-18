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

### c) Add post-renewal hook to reload Kafka
Kafka runs as a Docker container named `morphoLogic_kafka`, so the hook restarts it:
```bash
sudo tee /etc/letsencrypt/renewal-hooks/post/reload-kafka.sh > /dev/null << 'EOF'
#!/bin/bash
docker restart morphoLogic_kafka
EOF
sudo chmod +x /etc/letsencrypt/renewal-hooks/post/reload-kafka.sh
```

### d) Configure Kafka SSL
Kafka is a **bitnami/kafka Docker container** (`morphoLogic_kafka`). Bitnami's image is configured via environment variables, not by editing `server.properties` directly.

**Mount the certs into the container** (add to your `docker run` command or `docker-compose.yml`):
```yaml
volumes:
  - /etc/letsencrypt/live/<yourdomain>:/etc/kafka/certs:ro
```

**Set these env vars on the container:**
```
KAFKA_CFG_LISTENERS=PLAINTEXT://localhost:9092,SSL://0.0.0.0:9093
KAFKA_CFG_ADVERTISED_LISTENERS=PLAINTEXT://localhost:9092,SSL://<yourdomain>:9093
KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT,SSL:SSL
KAFKA_CFG_SSL_KEYSTORE_TYPE=PEM
KAFKA_CFG_SSL_KEYSTORE_CERTIFICATE_CHAIN=/etc/kafka/certs/fullchain.pem
KAFKA_CFG_SSL_KEYSTORE_KEY=/etc/kafka/certs/privkey.pem
KAFKA_CFG_SSL_CLIENT_AUTH=none
```

Recreate the container to apply changes:
```bash
docker compose up -d kafka   # or however you manage the container
# Verify TLS works:
openssl s_client -connect <yourdomain>:9093 -brief
```

### e) Open firewall port
```bash
sudo ufw allow 9093/tcp
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
