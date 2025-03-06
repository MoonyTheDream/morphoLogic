"""The main module starting the server and all needed services."""
from .utils.logger import logger
from .config import settings as _SETTINGS
from .network.kafka import KafkaConnection, HANDSHAKE_TOPIC as _HANDSHAKE_TOPIC


####################################################################################################
# Configuration & Logging
####################################################################################################



def awake():
    "Entry point of the server."
    print("The morphoLogic laws of physics bound itself into existance!")
    logger.info("Server version: %s", _SETTINGS.get("server_version", "ERROR"))
    logger.info("Waking up laws of nature.")
    with KafkaConnection() as kafka:
        while True:
            msg = kafka.consumer.consume(num_messages=1, timeout=-1)
            # logger.debug(msg)
            if msg:
                for msg in msg:
                    if not msg.error():
                        if msg.topic() == _HANDSHAKE_TOPIC
                        kafka_msg = msg.value().decode("utf-8")
                        if kafka_msg:
                            logger.debug(
                                'Consumed message from Kafka: "%s"', kafka_msg)

if __name__ == "__main__":
    awake()
