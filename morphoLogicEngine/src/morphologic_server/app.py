"""
Application bootstrap.

Server class — accepts ServerSettings, runs via a TaskGroup provided by cli.py.
This is the ONLY place where globals happen (at startup in main()).
Everything else receives dependencies explicitly.
"""

import asyncio
import logging

from morphologic_server.config import ServerSettings
from morphologic_server.network.kafka import KafkaConnection
from morphologic_server.services.message_handler import MessageHandler


class Server:
    """
    The application server. All dependencies injected, no hidden globals.

    Usage (from cli.py):
        settings = ServerSettings()
        server = Server(settings)
        async with asyncio.TaskGroup() as tg:
            tg.create_task(server.run(tg))
            tg.create_task(MorphoLogicCmd().cmdloop())
    """

    def __init__(self, settings: ServerSettings):
        self.settings = settings
        self._stop = False
        # Adjust the module logger level according to settings
        level = logging.DEBUG if settings.is_debug() else logging.INFO
        logging.getLogger("morphoLogic Server").setLevel(level)

    async def run(self, tg: asyncio.TaskGroup) -> None:
        """
        Open a Kafka connection, start the message handler, and keep running.

        Takes the outer TaskGroup from cli.py so the server and CLI run as
        concurrent tasks in the same cancellation domain.
        """
        log = logging.getLogger("morphoLogic Server")
        log.info("Starting morphoLogic v%s", self.settings.SERVER_VERSION)

        with KafkaConnection() as kafka:
            handler = MessageHandler(kafka=kafka, tg=tg)
            tg.create_task(handler.start())

            while not self._stop:
                await asyncio.sleep(1)

        log.info("Server stopped.")

    def stop(self):
        self._stop = True


# ---------------------------------------------------------------------------
# Stand-alone entry point (used when running app.py directly, not via CLI)
# ---------------------------------------------------------------------------

async def main() -> None:
    """Entry point without CLI — just runs the server loop."""
    settings = ServerSettings()
    server = Server(settings)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(server.run(tg))


if __name__ == "__main__":
    asyncio.run(main())
