"""
The main module starting the server and all needed services.
Aplication bootstrap.
"""

import asyncio

# import json
import logging

# from morphologic_server import (
#     logger,
#     Context,
#     force_terminate_task_group,
# )
from morphologic_server.config import ServerSettings
from morphologic_server.network.kafka import KafkaConnection
from morphologic_server.services.message_handler import MessageHandler

# # from morphologic_server.utils.search import get_objects_in_proximity
# from morphologic_server.services.message_handler import MessageHandler
# from .network.kafka import (
#     KafkaConnection,
#     CLIENTS_GENERAL_TOPIC as _CLIENTS_GENERAL_TOPIC,
# )

# __all__ = ["awake"]

#        d8888                        888
#       d88888                        888
#      d88P888                        888
#     d88P 888 888  888  888  8888b.  888  888  .d88b.
#    d88P  888 888  888  888     "88b 888 .88P d8P  Y8b
#   d88P   888 888  888  888 .d888888 888888K  88888888
#  d8888888888 Y88b 888 d88P 888  888 888 "88b Y8b.
# d88P     888  "Y8888888P"  "Y888888 888  888  "Y8888


class MorphoLogicHeart:
    """
    The Heart of the Morpho.
    The application server and entry point. All dependencies injected and no globals.

    Usage (from cli.py):
        settings = ServerSettings()
        morpho_heart = Server(settings)
        async with asyncio.TaskGroup() as tg:
            tg.create_task(morpho_heart.awake(tg))
            tg.create_task(MorphoLogicCmd().cmdloop())
    """

    def __init__(self, settings: ServerSettings):
        self.settings = settings
        self._stop = False

        # Adjust the module loger level as in the settings
        self.log = logging.getLogger("morphoLogic Server")
        self.log.setLevel(settings.logging_level())

    async def awake(self, tg: asyncio.TaskGroup) -> None:
        """
        Open a Kafka connection, start the message handler, and keep beating.

        Args:
            tg (asyncio.TaskGroup): Takes the outer TaskGroup from cli.py so the server and CLI run as
        concurent tasks in the same cancellation domain.

        Returns:
            _type_: None
        """
        self.log.info(
            "MorphoLogic Heart is beating again. It's the Artistic Beloved Hearth numbered %s.",
            self.settings.SERVER_VERSION,
        )

        with KafkaConnection(self) as kafka:
            handler = MessageHandler(heart=self, kafka=kafka, tg=tg)
            tg.create_task(handler.start())

            while not self._stop:
                await asyncio.sleep(1) # temporary, there will be beating heart and timer

        self.log.info("The Heart is going to rest. The server stopped.")


class AwakenedHeart:
    """
    The Hearth of the Morpho.
    """

    context: Context
    tg: asyncio.TaskGroup

    def __init__(self, context: Context):
        self.context = context
        self.tg = context.tg

    async def awake(self):
        """
        The main entry point of the server.
        Initializes Kafka connection, starts consuming messages,
        and introduces a loop to handle ticks and other tasks.
        """
        print("The morphoLogic laws of physics bound itself into existence!")
        logger.info("Waking up laws of nature.")

        with KafkaConnection() as kafka:
            self.context.kafka = kafka

            message_handler = MessageHandler(self.context)
            # Start consuming messages from Kafka
            self.tg.create_task(message_handler.start())

            while not self.context.stop_server:
                # Handle ticks and other tasks
                await asyncio.sleep(1)

        # Stop all tasks gracefully
        logger.info("Stopping the server.")
        self.tg.create_task(force_terminate_task_group())

    def stop_server(self):
        """Stop the server."""
        self.context.stop_server = True


# async def awake(tg: asyncio.TaskGroup):
#     "Entry point of the server."
#     print("The morphoLogic laws of physics bound itself into existence!")
#     logger.info("Server version: %s", _SETTINGS.SERVER_VERSION)
#     logger.info("Waking up laws of nature.")

#     tg.create_task(consume_and_handover(tg))


# # ------------------------------------------------------------------------------------------------ #

# # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Periodically Health Status ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
# # async def automated_periodical_health_status(tg: asyncio.TaskGroup):


# # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Consume And Handle ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
# async def consume_and_handover(tg: asyncio.TaskGroup):
#     """
#     A handler that consumes message from globalTopic and handing them over to handler.
#     """
#     try:

#         with KafkaConnection() as kafka:
#             while True:
#                 msg = await asyncio.to_thread(
#                     lambda: kafka.consumer.consume(num_messages=1, timeout=1)
#                 )
#                 if msg:
#                     if isinstance(msg, list):
#                         msg = msg[0]

#                     if msg.error():
#                         logger.warning("Error consuming message: %s", msg.error().str())
#                         return

#                     tg.create_task(handle_message(msg, kafka, tg))

#     except Exception:
#         logger.exception("Error in main loop of server.")


async def handle_message(msg, kafka: KafkaConnection, tg: asyncio.TaskGroup):
    """An actual handler of the message."""
    # We want to know to which topic the message was sent
    msg_topic = msg.topic()
    # Other needed data from kafka message
    kafka_msg = _decode_msg(msg)
    # payload = kafka_msg["payload"]
    system_message = kafka_msg["payload"].get("system_message", "")

    # # Don't freak out, just answer and carry on
    # if system_message == "YO_ANYBODY_HOME?":
    #     kafka.health_status()
    #     return

    user_input = kafka_msg["payload"].get("user_input", "")
    # message_content = kafka_msg["payload"].get("message_content", "")

    # system_message = kafka_msg.get("system_message", "")

    # this is also topic name
    sending_user = kafka_msg["metadata"]["username"]
    # The above WILL CHANGE. TOPIC PER USERNAME SHOULD BE TRACKING SOMEWHERE

    # Handling handhske messages from clients
    match system_message:

        # Handshake requests
        case "ITS'A_ME_MARIO":
            _handshake_topic_creation(kafka, kafka_msg)
        # Handshake in dedicated topic handler
        case "WALLS_HAVE_EARS_GOT_IT":
            _check_and_acknowledge_client_topic(kafka, sending_user, kafka_msg)
        case "LOUD_AND_CLEAR":
            await send_initial_objects_data(kafka, sending_user)
        case "":
            pass
        case _:
            raise RuntimeError(
                f'Uknown system message from client side in {msg_topic}: "{system_message}"'
            )
    if user_input:
        if user_input == "odeslij":
            tg.create_task(testowy_odeslij(kafka, sending_user, tg))
        logger.debug(
            'User "%s" sent message: "%s" to topic "%s"',
            sending_user,
            user_input,
            msg_topic,
        )

        # case _:
        #     logger.warning(
        #         'Unknown payload type in topic "%s": "%s". Content: "%s"',
        #         msg_topic,
        #         payload_type,
        #         content
        #     )


async def send_initial_objects_data(kafka: KafkaConnection, username: str):
    from morphologic_server.archetypes.base import search, Character

    # BARDZO WIP
    user = await search("MoonyTheDream", Character)
    # user = await search("AnotherCharacter", Character)

    objects = await user.get_surrounding_description()
    kafka.send_data_to_user(
        topic=username,
        username=username,
        server_message="SURROUNDINGS_DATA",
        content=objects,
    )


async def testowy_odeslij(kafka: KafkaConnection, username: str, tg):
    """
    Testowy handler do wysyłania wiadomości do użytkownika
    """
    logger.debug('Sending test message to "%s"', username)
    kafka.send_data_to_user(
        topic=username,
        username=username,
        direct_message="MASZ! Nażryj się, machoniu.\n",
    )
    for i in range(100):
        tg.create_task(send_initial_objects_data(kafka, username))


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
            _CLIENTS_GENERAL_TOPIC,
            username,
            server_message="SHH_LET'S_TALK_IN_PRIVATE",
            content=dedicated_topic,
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

    After client's WALLS_HAVE_EARS_GOT_IT check if the topic is subscribed and
    then send there an "ACK" system message
    """
    username = msg["metadata"]["username"]

    # Na razie taka beznadziejna walidacja, do zastąpienia czymś sensownym
    kafka.send_data_to_user(
        msg_topic, username=username, server_message="CAN_YOU_HEAR_ME?"
    )


# if __name__ == "__main__":
#     awake()
