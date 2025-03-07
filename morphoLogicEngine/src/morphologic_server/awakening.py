"""The main module starting the server and all needed services."""
import json

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
            consume_and_handle(kafka)
    logger.info("Server closing down.")
            

def consume_and_handle(kafka: KafkaConnection):
    """
    A handler that consumes message from globalTopic and decides to which function
    it needs to be handled.
    """
    try:
        msg = kafka.consumer.consume(num_messages=1, timeout=-1)
        if msg:
            for msg in msg:
                
                if msg.error():
                    logger.warning(
                        "Error consuming message: %s", msg.error().str())
                    continue
                    
                if msg.topic() == _HANDSHAKE_TOPIC:
                    kafka_msg = _decode_msg(msg)
                    if kafka_msg['auth']['source'] == "server":
                        return
                    
                    # Handler
                    system_message = kafka_msg.get("system_message", "") 
                    match system_message:
                        case "REQUEST_SERVER_CONNECTION":
                            _handshake_topic_creation(kafka, kafka_msg)
                        case _:
                            raise RuntimeError(f'Uknown system message from client side: "{system_message}"')
                
                kafka_msg = _decode_msg(msg)
                
                # System messages handler
                system_message = kafka_msg.get("system_message", "")
                match system_message:
                    # Handshake in dedicated topic handler
                    case "HANDSHAKE_DEDICATED_TOPIC":
                        _check_and_acknowledge_client_topic(kafka, kafka_msg)
                        
                    
                
    except Exception:
        logger.exception("Error in main loop of server.")

    
def _decode_msg(msg) -> dict:
    kafka_msg = msg.value().decode("utf-8")
    logger.debug('Consumed message from Kafka: "%s"', kafka_msg)
    return json.loads(kafka_msg)
    

def _handshake_topic_creation(kafka: KafkaConnection, client_handshake_msg: dict):
    username = client_handshake_msg['auth'].get("username", "")
    if username: # tu można później dodać walidację, czy użytkownik istnieje i jaki topic itp.
        kafka.create_new_topics([username])
        kafka.update_subscription([username])
        kafka.send_data_to_user(
            _HANDSHAKE_TOPIC,
            username,
            data={"client_topic_handoff": username},
            system_message="TOPIC_CREATED_SEND_HANDSHAKE_THERE"
            )

def _check_and_acknowledge_client_topic(kafka: KafkaConnection, msg: dict):
    """
    After client's HANDSHAKE_DEDICATED_TOPIC check if the topic is subscribed and 
    then send there an "ACK" system message
    """
    topic = msg['auth']["username"]
    current_subscription = kafka.consumer.assignment()
    logger.debug('Current subscribed: "%s"', [topic_partition.topic for topic_partition in current_subscription])
    is_subscribed = False
    for topic_partition in current_subscription:
        if topic == topic_partition.topic:
            is_subscribed = True
            break
    
    if is_subscribed:
        kafka.send_data_to_user(topic, username=topic, system_message="ACK")
        
    else:
        # NOT IMPLEMENTED FULLY
        logger.error('Client what to talk in non-existing topic: "%s"', topic)
    
if __name__ == "__main__":
    awake()
    
