"""Server handlers for saving and querrying data from DB"""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from geoalchemy2 import shape
from shapely.geometry import Point

from morphologic_server import settings, logger
from morphologic_server.db.models import (
    Account,
    CharacterSoul,
    GameObject,
    Character,
    ObjectType,
)

_DB_ADDRESS = settings.get("db_address", None)

try:
    engine = create_engine(
        "postgresql://" + _DB_ADDRESS
    )
except Exception:
    logger.exception("Could not connect to database!")
    raise
        