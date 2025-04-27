"""The main module starting the server and all needed services."""

import asyncio
import json

from morphologic_server import logger, settings as _SETTINGS
from .network.kafka import (
    KafkaConnection,
    CLIENT_HANDSHAKE_TOPIC as _CLIENT_HANDSHAKE_TOPIC,
    SERVER_HANDSHAKE_TOPIC as _SERVER_HANDSHAKE_TOPIC,
)

__all__ = ["awake"]

#        d8888                        888
#       d88888                        888
#      d88P888                        888
#     d88P 888 888  888  888  8888b.  888  888  .d88b.
#    d88P  888 888  888  888     "88b 888 .88P d8P  Y8b
#   d88P   888 888  888  888 .d888888 888888K  88888888
#  d8888888888 Y88b 888 d88P 888  888 888 "88b Y8b.
# d88P     888  "Y8888888P"  "Y888888 888  888  "Y8888
async def awake(tg: asyncio.TaskGroup):
    "Entry point of the server."
    print("The morphoLogic laws of physics bound itself into existence!")
    logger.info("Server version: %s", _SETTINGS.SERVER_VERSION)
    logger.info("Waking up laws of nature.")

    tg.create_task(consume_and_handle())


# ------------------------------------------------------------------------------------------------ #


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Consume And Handle ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
async def consume_and_handle():
    """
    A handler that consumes message from globalTopic and decides to which function
    it needs to be handled.
    """
    try:

        with KafkaConnection() as kafka:
            while True:
                msg = await asyncio.to_thread(
                    lambda: kafka.consumer.consume(num_messages=1, timeout=1)
                )
                if msg:
                    if isinstance(msg, list):
                        msg = msg[0]

                    if msg.error():
                        logger.warning("Error consuming message: %s", msg.error().str())
                        return

                    # We want to know to which topic the message was sent
                    msg_topic = msg.topic()
                    # Other needed data from kafka message
                    kafka_msg = _decode_msg(msg)
                    payload = kafka_msg["payload"]
                    payload_type = payload["type"]
                    content = payload["content"]
                    
                    # system_message = kafka_msg.get("system_message", "")
                    
                    # this is also topic name
                    sending_user = kafka_msg["metadata"]["username"]
                    # The above WILL CHANGE. TOPIC PER USERNAME SHOULD BE TRACKING SOMEWHERE

                    # Handling handhske messages from clients
                    if payload_type == "system_message":
                        if msg_topic == _SERVER_HANDSHAKE_TOPIC:
                            # Handshake requests
                            match content:
                                case "REQUEST_SERVER_CONNECTION":
                                    _handshake_topic_creation(kafka, kafka_msg)
                                case _:
                                    raise RuntimeError(
                                        f'Uknown system message from client side in {msg_topic}: "{system_message}"'
                                    )

                    elif payload_type == "system_message":
                        # System messages from client side handler
                        if system_message:
                            match system_message:
                                # Handshake in dedicated topic handler
                                case "HANDSHAKE_GLOBAL_TOPIC":
                                    _check_and_acknowledge_client_topic(
                                        kafka, sending_user, kafka_msg
                                    )
                                case _:
                                    raise RuntimeError(
                                        f'Uknown system message from client side in topic {msg_topic}: "{system_message}"'
                                    )

    except Exception:
        logger.exception("Error in main loop of server.")


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Decode Msg ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
def _decode_msg(msg) -> dict:
    kafka_msg = msg.value().decode("utf-8")
    logger.debug('Consumed message from %s: "%s"', msg.topic(), kafka_msg)
    return json.loads(kafka_msg)


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Handshake ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
def _handshake_topic_creation(kafka: KafkaConnection, client_handshake_msg: dict):
    username = client_handshake_msg["metadata"].get("username", "")
    if (
        username
    ):  # tu można później dodać walidację, czy użytkownik istnieje i jaki topic itp.
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
            content=(dedicated_topic),
            payload_type="client_topic_handoff",
        )


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ACK ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
def _check_and_acknowledge_client_topic(
    kafka: KafkaConnection, msg_topic: str, msg: dict
):
    """
    888       888 8888888 8888888b.
    888   o   888   888   888   Y88b
    888  d8b  888   888   888    888
    888 d888b 888   888   888   d88P
    888d88888b888   888   8888888P"
    88888P Y88888   888   888
    8888P   Y8888   888   888
    888P     Y888 8888888 888
    
    After client's HANDSHAKE_GLOBAL_TOPIC check if the topic is subscribed and
    then send there an "ACK" system message
    """
    username = msg["metadata"]["username"]

    # Na razie taka beznadziejna walidacja, do zastąpienia czymś sensownym
    kafka.send_data_to_user(msg_topic, username=username, system_message="ACK")


# if __name__ == "__main__":
#     awake()
