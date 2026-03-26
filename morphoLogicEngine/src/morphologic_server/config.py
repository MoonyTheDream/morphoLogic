"""Config module loading settings from environment variables with validation."""

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env from the same directory as this file, regardless of CWD
_env_file = Path(__file__).parent / ".env"
load_dotenv(_env_file)


class ServerSettings(BaseSettings):
    """
    Server configuration loaded from environment variables with validation.

    All required settings must be provided via environment variables or .env file.
    This ensures configuration is explicit, validated, and production-safe.

    .env.template example available in the project root.
    """

    # Application
    SERVER_VERSION: str = Field(default="0.1.0", description="Server version")
    ENVIRONMENT: str = Field(
        default="development",
        description="Environment (development, staging, production)",
    )
    KAFKA_SECURITY_PROTOCOL: str = ""  # set to "ssl" to enable TSL
    KAFKA_SSL_CA_LOCATIONS: str = ""

    # Kafka configuration
    KAFKA_SERVER: str = Field(
        default="localhost:9092", description="Kafka bootstrap servers"
    )
    SERVER_GENERAL_TOPIC: str = Field(
        default="serverGeneralTopic", description="Topic for general server messages"
    )
    CLIENTS_GENERAL_TOPIC: str = Field(
        default="clientsGeneralTopic", description="Topic for general client messages"
    )
    SERVER_HANDSHAKE_TOPIC: str = Field(
        default="serverHandshakeTopic", description="Topic for server handshake"
    )
    KAFKA_GROUP_ID: str = Field(
        default="morphoLogicServerGroup", description="Kafka consumer group ID"
    )

    # Database configuration
    DB_ADDRESS: Optional[str] = Field(
        default=None, description="PostgreSQL connection URL"
    )

    model_config = {
        "env_file": str(Path(__file__).parent / ".env"),
        "case_sensitive": False,
    }

    @field_validator("KAFKA_SERVER")
    @classmethod
    def validate_kafka_server(cls, v: str) -> str:
        """Validate Kafka server format."""
        if not v or not isinstance(v, str):
            raise ValueError("KAFKA_SERVER must be a non-empty string")

        if ":" not in v:
            raise ValueError(
                f"KAFKA_SERVER must include port (e.g., localhost:9092), got: {v}"
            )

        _, port = v.rsplit(":", 1)
        try:
            port_num = int(port)
            if not (0 < port_num < 65536):
                raise ValueError(f"Port {port_num} out of valid range (1-65535)")
        except ValueError as e:
            raise ValueError(f"Invalid port in KAFKA_SERVER: {port}") from e

        return v

    @field_validator("DB_ADDRESS")
    @classmethod
    def validate_db_address(cls, v: Optional[str]) -> Optional[str]:
        """Validate database connection string."""
        if v is None:
            return v

        if not isinstance(v, str) or not v:
            raise ValueError("DB_ADDRESS must be a non-empty string if provided")

        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment value."""
        valid_envs = {"development", "staging", "production"}
        if v.lower() not in valid_envs:
            raise ValueError(f"ENVIRONMENT must be one of {valid_envs}, got: {v}")
        return v.lower()

    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT == "production"

    def is_debug(self) -> bool:
        """Check if debug mode is enabled."""
        return not self.is_production()

    def logging_level(self) -> str:
        """Sets "DEBUG" or "INFO" as string depending on being on production or not."""
        return "INFO" if self.is_production() else "DEBUG"
