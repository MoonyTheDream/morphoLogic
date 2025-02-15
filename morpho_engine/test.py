import websockets
import asyncio
import json

async def test_ws():
    uri = "ws://localhost:8000/ws/testplayer"
    async with websockets.connect(uri) as websocket:
        await websocket.send(json.dumps({"move": {"x": 10, "y": 10, "z": 0}}))
        response = await websocket.recv()
        print(response)

asyncio.run(test_ws())

