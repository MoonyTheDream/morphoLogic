"""A Gateway with one face to the outside world via websockets and client connections, 
and the other face to the internal network of the morphoLogicEngine via Kafka."""

import asyncio

from websockets.asyncio.server import serve

from morphologic_server.heart import MorphoLogicHeart
from morphologic_server.network.messages import client_message_adapter

host = "localhost"
port = 8765

async def handle_client(websocket):
    # First we need to authenticate the client. This hould always be the first message
    # sent by the client, otherwise we close the connection.
    # try:
    raw_message = await websocket.recv()
    msg = client_message_adapter.validate_json(raw_message)
    print(msg)
    print(type(msg))
    print(msg.timestamp)
    return
    
    
async def start():
        async with serve(handle_client, host, port) as websocket_server:
            print("Gateway started on %s:%d", host, port)
            await websocket_server.serve_forever()
            
if __name__ == "__main__":
    asyncio.run(start())