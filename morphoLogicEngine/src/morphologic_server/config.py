"""Config module loading settings from JSON file."""
import os

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()  # Load .env into environment variables

@dataclass
class SettingsDataclass:
    """
    Class that represents settings for the morphologic server.
    """

    SERVER_VERSION: str = "0.1.0"
    LOG_LEVEL_DEBUG: bool = True
    GENERAL_TOPIC: str = "serverGeneralTopic"
    CLIENT_HANDSHAKE_TOPIC: str = "clientHandshakeTopic"
    SERVER_HANDSHAKE_TOPIC: str = "serverHandshakeTopic"
    
    # # Checking for sercret settings file
    # if Path.cwd() / "secret_settings.py":
    #     try:
    #         from morphologic_server.secret_settings import secret_settings
    #     except ImportError:
    #         print("\nSecret settings file not found or not properly configured.\n")
    #         secret_settings = {}
    # LOCAL_DEVELOPING: bool = False

    # KAFKA_SERVER: str
    # DB_ADDRESS: str

    KAFKA_SERVER: str = os.getenv("KAFKA_SERVER") if os.getenv("KAFKA_SERVER") else "localhost:9092"
    DB_ADDRESS: str = os.getenv("DB_ADDRESS")


settings = SettingsDataclass()


# settings = load_settings()
# settings = None


# def return_enum_like_class(name, data_dict: dict):
#     return type("Settings", (),{key.upper(): value for key, value in data_dict.items()})


# class SettingsEnumLike:
#     """
#     Class that loads settings from JSON file and makes them available as class attributes.
#     """

#     SERVER_VERSION: str
#     LOG_LEVEL_DEBUG: bool
#     KAFKA_SERVER: str
#     GENERAL_TOPIC: str
#     CLIENT_HANDSHAKE_TOPIC: str
#     SERVER_HANDSHAKE_TOPIC: str
#     DB_ADDRESS: str

#     def _load_settings(self):
#         """
#         Loads global settings from JSON file.
#         Raises FileNotFoundError if file is missing.
#         """
#         settings_path = Path(__file__).resolve().parents[2] / "config/settings.json"
#         if not os.path.exists(settings_path):
#             raise FileNotFoundError("Settings file not found.")

#         with open(settings_path, "r", encoding="utf-8") as f:
#             return json.load(f)

#     def __init__(self):
#         _settings_json = self._load_settings()
#         # for key, value in settings_json.items():
#         #     setattr(self, key.upper(), value)
#         self.SERVER_VERSION = _settings_json.get("server_version", "ERROR")
#         self.LOG_LEVEL_DEBUG = _settings_json.get("log_level_debug", False)
#         self.KAFKA_SERVER = _settings_json.get("kafka_server", 'localhost:9092')
#         self.GENERAL_TOPIC = _settings_json.get("generalTopic", "serverGeneralTopic")
#         self.CLIENT_HANDSHAKE_TOPIC = _settings_json.get("clientHandshakeTopic", "clientHandshakeTopic")
#         self.SERVER_HANDSHAKE_TOPIC = _settings_json.get("serverHandshakeTopic", "serverHandshakeTopic")
#         self.DB_ADDRESS = _settings_json.get("db_address", "localhost:5432")
