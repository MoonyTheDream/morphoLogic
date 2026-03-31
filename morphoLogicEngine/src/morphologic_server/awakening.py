"""
The main module starting the server and all needed services.
Aplication bootstrap.
"""

import asyncio
import logging

from morphologic_server.config import ServerSettings
from morphologic_server.network.kafka import KafkaConnection
from morphologic_server.services.message_handler import MessageHandler

from morphologic_server.db.engine import create_sessionmaker
from morphologic_server.db.memory import Memory
from morphologic_server.db.models import Base


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
        morpho_heart = MorphoLogicHeart(ServerSettings())
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

        # Spinning up the sessionmaker and Memory — all DB ops go through heart.memory
        try:
            self.db_sessionmaker = create_sessionmaker(settings.DB_ADDRESS)
            self.memory = Memory(self.db_sessionmaker)
            Base._sessionmaker = self.db_sessionmaker
        except Exception as e:
            self.log.exception("Failed to connect to the database: %s", e)
            raise

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
                await asyncio.sleep(
                    1
                )  # temporary, there will be beating heart and timer

        self.log.info("The Heart is going to rest. The server stopped.")
