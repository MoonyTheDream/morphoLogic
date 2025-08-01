"""Global context for the morphologic server services."""

import asyncio

from dataclasses import dataclass

from ..network.kafka import KafkaConnection

@dataclass
class Context:
    """Global context for the morphologic server services."""

    tg: asyncio.TaskGroup
    stop_server: bool = False
    kafka: KafkaConnection
