"""The main module starting the server and all needed services."""
import asyncio
import json

from .utils.logger import logger
from .config import settings as _SETTINGS
from .network.kafka import (
    KafkaConnection,
    CLIENT_HANDSHAKE_TOPIC as _CLIENT_HANDSHAKE_TOPIC,
    SERVER_HANDSHAKE_TOPIC as _SERVER_HANDSHAKE_TOPIC
)

import time

####################################################################################################
# Configuration & Logging
####################################################################################################

# Global stop event
stop_event = asyncio.Event()

async def awake():
    "Entry point of the server."
    print("The morphoLogic laws of physics bound itself into existence!")
    logger.info("Server version: %s", _SETTINGS.get("server_version", "ERROR"))
    logger.info("Waking up laws of nature.")
    # while not stop_event.is_set():
    try:
        while True:
                # consume_and_handle(kafka)
            # print("rzezc")
            await asyncio.sleep(1)
        # print("Keyboard Interrupt madafasak")
    # with KafkaConnection() as kafka:
        # while not stop_event.is_set():
        #     # consume_and_handle(kafka)
        #     time.sleep(1)
    except asyncio.CancelledError:
        logger.exception("ASYNKOEROROER")
    logger.info("Server closing down.")


def consume_and_handle(kafka: KafkaConnection):
    """
    A handler that consumes message from globalTopic and decides to which function
    it needs to be handled.
    """
    try:
        msg = kafka.consumer.consume(num_messages=1, timeout=-1)
        if msg:
            if isinstance(msg, list):
                msg = msg[0]

            if msg.error():
                logger.warning(
                    "Error consuming message: %s", msg.error().str())
                return

            # We want to know to which topic the message was sent
            msg_topic = msg.topic()
            # Other needed data from kafka message
            kafka_msg = _decode_msg(msg)
            
            
            # # Ignoring if the message was send by itself
            # if kafka_msg['metadata']['source'] == "server":
            #     return
            
            system_message = kafka_msg.get("system_message", "")
            sending_user = kafka_msg['metadata']['username'] # this is also topic name
            # The aboce WILL CHANGE. TOPIC PER USERNAME SHOULD BE TRACKING SOMEWHERE


            # Handling handhske messages from clients
            if msg_topic == _SERVER_HANDSHAKE_TOPIC:
                # Handshake requests
                if system_message:
                    match system_message:
                        case "REQUEST_SERVER_CONNECTION":
                            _handshake_topic_creation(kafka, kafka_msg)
                        case _:
                            raise RuntimeError(
                                f'Uknown system message from client side in {msg_topic}: "{system_message}"')

            else:
                # System messages from client side handler
                if system_message:
                    match system_message:
                        # Handshake in dedicated topic handler
                        case "HANDSHAKE_GLOBAL_TOPIC":
                            _check_and_acknowledge_client_topic(kafka, sending_user, kafka_msg)
                        case _:
                            raise RuntimeError(
                                f'Uknown system message from client side in topic {msg_topic}: "{system_message}"')

    except Exception:
        logger.exception("Error in main loop of server.")


def _decode_msg(msg) -> dict:
    kafka_msg = msg.value().decode("utf-8")
    logger.debug('Consumed message from %s: "%s"', msg.topic(), kafka_msg)
    return json.loads(kafka_msg)


def _handshake_topic_creation(kafka: KafkaConnection, client_handshake_msg: dict):
    username = client_handshake_msg['metadata'].get("username", "")
    if username:  # tu można później dodać walidację, czy użytkownik istnieje i jaki topic itp.
        topics_created = kafka.create_new_topics([username])
        if topics_created and len(topics_created) == 1:
            logger.info('Successfuly created topic: "%s"', topics_created[0])
            dedicated_topic = topics_created[0]
        else:
            dedicated_topic = username
        
        # kafka.update_subscription([dedicated_topic])
        kafka.send_data_to_user(
            _CLIENT_HANDSHAKE_TOPIC,
            username,
            data={"client_topic_handoff": dedicated_topic},
            system_message="TOPIC_CREATED_SEND_HANDSHAKE_THERE"
        )


def _check_and_acknowledge_client_topic(kafka: KafkaConnection, msg_topic: str, msg: dict):
    """
    After client's HANDSHAKE_GLOBAL_TOPIC check if the topic is subscribed and 
    then send there an "ACK" system message
    """
    username = msg['metadata']["username"]
    # current_subscription = kafka.consumer.assignment()
    # logger.debug('Current subscribed: "%s"', [
    #              topic_partition.topic for topic_partition in current_subscription])
    
    # Bez sensu to poniżej, przecież to dla nich jest ten topic
    # is_subscribed = False
    # for topic_partition in current_subscription:
    #     if msg_topic == topic_partition.topic:
    #         is_subscribed = True
    #         break
    
    # Na razie taka beznadziejna walidacja, do zastąpienia czymś sensownym
    # if msg_topic == username:
    kafka.send_data_to_user(msg_topic, username=username, system_message="ACK")

    # else:
    #     # NOT IMPLEMENTED FULLY
    #     logger.error('Client want to talk in wrong topic. Topic: "%s", Username: "%s"', msg_topic, username)


if __name__ == "__main__":
    awake()
