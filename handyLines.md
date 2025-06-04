# TOPICS
## Communication server -> client
- A given topic per client
-> clientHandshakeTopic
## Communication client -> server
-> serverGeneralTopic 
-> serverHandshakeTopic

# Docker Kafka Client Commands
## kafka_2.13-3.9.0
docker pull apache/kafka:latest
docker run -p 9092:9092 apache/kafka:latest
bin/kafka-topics.sh --create --topic serverGeneralTopic --bootstrap-server <localhost/kafka_server_address>:9092
  --config retention.ms=60000 // for hansdhake topics
    key = None
bin/kafka-topics.sh --create --topic addresedToClients --bootstrap-server <localhost/kafka_server_address>:9092
    key = <userName>

bin/kafka-console-producer.sh --topic Moony --bootstrap-server localhost:9092 --timeout 0
bin/kafka-console-consumer.sh --topic serverGeneralTopic --from-beginning --bootstrap-server localhost:9092

# pip
<!-- Just the latest -->
confluent-kafka 

# Docker Itself
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

sudo groupadd docker
sudo usermod -aG docker $USER

*restart* for *vscode* to also be able to see docker


