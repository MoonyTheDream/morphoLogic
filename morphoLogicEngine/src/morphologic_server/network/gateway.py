"""A Gateway with one face to the outside world via websockets and client connections, 
and the other face to the internal network of the morphoLogicEngine via Kafka."""

import asyncio

from websockets.asyncio.server import serve

from morphologic_server.heart import MorphoLogicHeart

class Gateway:
    def __init__(self, host: str, port: int, heart: MorphoLogicHeart):
        self.host = host
        self.port = port
        self.heart = heart

    async def handle_client(self, websocket):
        # First we need to authenticate the client.
        
    async def start(self):
        async with serve()