"""
ClientMessage and ServerMessage definitions using Pydantic models.
The general idea is to be able to easily access Kafka messages like in the following way:
    msg = ReceivedMessage(raw_msg)
    msg.user  # Access username
    msg.type  # Access message type
    msg.msg   # Access message content
"""
from typing import Literal

from pydantic import BaseModel

from confluent_kafka import Message as KafkaMessage

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Client Messages ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
class ClientMetadata(BaseModel):
    """Metadata sent by the client with each message."""
    username: str
    client_version: str
    timestamp: str
    
class ClientPayload(BaseModel):
    """Payload of a message sent by the client."""
    type: Literal["user_input", "system_message"]
    message: str
    content: str | None = None
    
class ClientMessage(BaseModel):
    """Message sent by the client to the server."""
    metadata: ClientMetadata
    payload: ClientPayload
    topic: str = ""
    
class ReceivedMessage():
    """
    Parsed wrapper around a raw Kafka message.
    Provides easy access to the message's topic, user, type, content, etc.
    
        msg.user  # Access username
        msg.type  # Access message type ("user_input" or "system_message")
        msg.msg   # Access the actual message content
        msg.content # Access any additional content (if provided)
    """

    def __init__(self, raw_msg: KafkaMessage):
        self.topic = raw_msg.topic()
        raw = raw_msg.value()
        if raw is None:
            raise ValueError("Kafka message has no value.")
        self.data = ClientMessage.model_validate_json(raw)
    
    @property
    def user(self):
        return self.data.metadata.username

    @property
    def type(self):
        return self.data.payload.type
    
    @property
    def msg(self):
        return self.data.payload.message
    
    @property
    def content(self):
        return self.data.payload.content
    
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Server Messages ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
class ServerMetadata(BaseModel):
    """Metadata sent by the server with each message."""
    to_user: str
    server_version: str
    timestamp: str
    
class ServerPayload(BaseModel):
    """Payload of a message sent by the server."""
    type: Literal["server_message", "surroundings_data"]
    message: str
    content: str | None = None
    objects: dict | None = None
    
class ServerMessage(BaseModel):
    """Message sent by the server to the client."""
    metadata: ServerMetadata
    payload: ServerPayload