# Docker Kafka Client Commands
## kafka_2.13-3.9.0
docker run -p 9092:9092 apache/kafka:latest
bin/kafka-topics.sh --create --topic quickstart-events --bootstrap-server localhost:9092
bin/kafka-console-producer.sh --topic quickstart-events --bootstrap-server localhost:9092 --timeout 0
bin/kafka-console-consumer.sh --topic quickstart-events --from-beginning --bootstrap-server localhost:9092

# pip
<!-- Just the latest -->
confluent-kafka 