import json

from morphologic_server.network.kafka import KafkaConnection
from morphologic_server.services.messages import ReceivedMessage
from morphologic_server.config import ServerSettings

from morphologic_server.awakening import MorphoLogicHeart

def get_test_message_via_kafka(test_msg: dict | None = None) -> ReceivedMessage:
    """Test function to produce and consume a test message via Kafka."""
    heart = MorphoLogicHeart(ServerSettings())
    with KafkaConnection(heart) as kafka:
        test_topic = "test_topic"
        kafka.subscribe_to_topics(["test_topic"])
        
        if not test_msg:
            test_msg = {
                "metadata": {
                    "username": "testuser",
                    "client_version": "0.1",
                    "timestamp": "1991-03-19 15:04:00"
                },
                "payload": {
                    "type": "user_input",
                    "message": "rozejrzyj się",
                }
            }
        
        kafka.producer.produce(test_topic, value=json.dumps(test_msg).encode("utf-8"))
        kafka.producer.flush()

        msgs = kafka.consumer.consume(num_messages=1, timeout=5)
        if msgs:
            msg = msgs[0] if isinstance(msgs, list) else msgs
            if msg.error():
                print("Kafka error:", msg.error())
            else:
                print("Received message from Kafka:", json.loads(msg.value().decode("utf-8")))
        else:
            print("No message received from Kafka.")
            
    client_msg = ReceivedMessage(msg)
    return client_msg  