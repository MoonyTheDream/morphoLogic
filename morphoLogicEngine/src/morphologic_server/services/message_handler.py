"""MessageHandler class for receiving message from kafka and processing it."""

import asyncio
import json

from confluent_kafka import Message

from morphologic_server import logger, Context

class KafkaMessage:
    """
    Represents a message from Kafka.
    """
    
    topic: str
    msg: str = ""
    system_msg: str = ""
    user_input: str = ""
    sending_user: str = ""

    def __init__(self, raw_msg: Message):
        self.topic = raw_msg.topic()
        self.msg = self._decode_msg(raw_msg)
        self.system_msg = self.msg["payload"].get("system_message", "")
        self.user_input = self.msg["payload"].get("user_input", "")
        self.sending_user = self.msg["metadata"]["username"]

    def _decode_msg(self, raw_msg) -> dict:
        kafka_msg = raw_msg.value().decode("utf-8")
        logger.debug('Consumed message from %s: "%s"', raw_msg.topic(), kafka_msg)
        return json.loads(kafka_msg)
    
class MessageHandler:
    """Handles messages from Kafka and processes them."""
    
    context: Context
    _stop = False

    def __init__(self, context: Context):
        self.context = context

    async def start(self):
        """
        Starts the message handler by creating a task to consume messages.
        """
        self.context.tg.create_task(self.consume_and_send_to_process())
        # self.tg.create_task(self.handle_message())
        
    def stop(self):
        """
        Stops the message handler.
        """
        self._stop = True
        
    async def consume_and_send_to_process(self):
        """
        Consumes a message from Kafka and sends it for processing.
        """
        while not self._stop:
            msg = await asyncio.to_thread(
                lambda: self.context.kafka.consumer.consume(num_messages=1, timeout=1)
            )
            if msg:
                if isinstance(msg, list):
                    msg = msg[0]

                if msg.error():
                    logger.warning("Error consuming message: %s", msg.error().str())
                    return

                msg = KafkaMessage(msg)
                
                self.context.tg.create_task(self.message_handler(msg))

    async def message_handler(self, msg: KafkaMessage):
        """
        Handles messages to the proper processor.
        """
        if msg.system_msg:
            self.context.tg.create_task(SystemMessageProcessor(msg, self.context))
        

