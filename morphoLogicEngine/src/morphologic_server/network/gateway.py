"""A Gateway with one face to the outside world via websockets and client connections, 
and the other face to the internal network of the morphoLogicEngine via Kafka."""

import asyncio

from websockets.asyncio.server import serve

from morphologic_server.heart import MorphoLogicHeart
from morphologic_server.network.messages import client_message_adapter

class Gateway:
    def __init__(self, heart: MorphoLogicHeart):
        self.heart = heart
        self.host = self.heart.settings.WEBSOCKET_HOST
        self.port = self.heart.settings.WEBSOCKET_PORT

    async def handle_client(self, websocket):
        # First we need to authenticate the client. This hould always be the first message
        # sent by the client, otherwise we close the connection.
        try:
            raw_message = await websocket.recv()
            msg = client_message_adapter.validate_json(raw_message)
            self.heart.log.info("Received message from client: %s", msg)
        except Exception as ex:
            self.heart.log.error("Error occurred while handling client message: %s", ex)
            await websocket.close()

    async def start(self):
        async with serve(self.handle_client, self.host, self.port) as websocket_server:
            self.heart.log.info("Gateway started on %s:%d", self.host, self.port)
            await websocket_server.wait_closed()