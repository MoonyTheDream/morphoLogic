import json

from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, Field, TypeAdapter

# from confluent_kafka import Message as KafkaMessage

from morphologic_server import settings
from morphologic_server.utils.time_helpers import get_gmt_time


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Server Messages For Clients ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
class ServerEnvelope(BaseModel):
    """Metadata for the messages sent by the server to the clients"""

    timestamp: datetime = Field(default_factory=get_gmt_time)
    server_version: str = settings.SERVER_VERSION


# class
class ReceivedMessage:
    pass


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Client Messages ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
class ClientEnvelope(BaseModel):
    """Expected additional information for messages sent by the clients"""

    timestamp: datetime
    client_version: str


class Authenticate(ClientEnvelope):
    """Message sent by the client to authenticate."""

    type: Literal["authenticate"]
    username: str
    password: str


class Command(ClientEnvelope):
    """Command sent by the user to the server."""

    type: Literal["command"]
    text: str


# Using Annotated and TypeAdapter to create a discriminated union of client messages.
ClientMessage = Annotated[Authenticate | Command, Field(discriminator="type")]
client_message_adapter = TypeAdapter(ClientMessage)
# Usage:
# msg = client_message_adapter.validate_json(raw_json_string)
# returns the right subclass; pydantic picks by `type`
