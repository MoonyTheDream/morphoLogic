"""ClientMessage and ServerMessage definitions using Pydantic models."""
import json

from typing import Literal

from pydantic import BaseModel

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
    """Parsed wrapper around a raw Kafka message."""

    def __init__(self, raw_msg):
        self.topic = raw_msg.topic()
        self.data = ClientMessage.model_validate_json(raw_msg.value())
    
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