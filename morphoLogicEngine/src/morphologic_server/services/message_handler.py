"""MessageHandler class for receiving message from kafka and processing it."""

import asyncio

from morphologic_server import logger
from ..network.kafka import KafkaConnection

class MessageHandler:
    """Handles messages from Kafka and processes them."""
    
    tg: asyncio.TaskGroup
    kafka: KafkaConnection
    queue = asyncio.Queue()
    _stop = False
    

    def __init__(self, tg: asyncio.TaskGroup, kafka: KafkaConnection):
        self.tg = tg
        self.kafka = kafka
        
    def start(self):
        """
        Starts the message handler by creating a task to consume messages.
        """
        self.tg.create_task(self.consume_and_put_to_queue())
        self.tg.create_task(self.handle_message())
        
    def stop(self):
        """
        Stops the message handler.
        """
        self._stop = True
        
    async def consume_and_put_to_queue(self):
        """
        Consumes a message from Kafka and puts it into the queue.
        """
        while not self._stop:
            msg = await asyncio.to_thread(
                lambda: self.kafka.consumer.consume(num_messages=1, timeout=1)
            )
            if msg:
                if isinstance(msg, list):
                    msg = msg[0]

                if msg.error():
                    logger.warning("Error consuming message: %s", msg.error().str())
                    return

                await self.queue.put_nowait(msg)
                
    async def process_message(self):
        """
        Processes messages from the queue.
        """
        while not self._stop:
            
            