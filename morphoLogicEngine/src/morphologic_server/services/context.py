"""Global context for the morphologic server services."""

import asyncio

from dataclasses import dataclass


@dataclass
class Context:
    """Global context for the morphologic server services."""

    tg: asyncio.TaskGroup
    stop_server: bool = False
    kafka: "KafkaConnection" = None  # Placeholder for Kafka connection type