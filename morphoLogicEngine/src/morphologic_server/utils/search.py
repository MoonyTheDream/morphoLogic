from typing import Type

from sqlalchemy import select

from geoalchemy2.shape import from_shape
from geoalchemy2.functions import ST_DWithin, ST_Force2D

from shapely.geometry import Point

from morphologic_server import logger
from morphologic_server.db.engine import DBAsyncSession
from morphologic_server.db.models import (
    GameObjectDB,
    CharacterDB,
)
from morphologic_server.archetypes.base import (
    Archetypes,
    GameObject
)

STANDARD_VISIBILITY_RADIUS = 10.0  # IN METERES


async def get_objects_in_proximity(
    focal_point: Type["Archetypes"], radius: float = STANDARD_VISIBILITY_RADIUS
):
    point = from_shape(Point(focal_point.location.x, focal_point.location.y), srid=3857)
    # model = focal_point.linked_db_obj
    async with DBAsyncSession() as session:
        stmt1 = select(GameObjectDB).where(
            ST_DWithin(
                ST_Force2D(GameObjectDB.location),
                ST_Force2D(point),
                radius,
            )
        )
        stmt2 = select(CharacterDB).where(
            ST_DWithin(
                ST_Force2D(CharacterDB.location),
                ST_Force2D(point),
                radius,
            )
        )
        result1 = await session.execute(stmt1)
        result2 = await session.execute(stmt2)
        
        objs1 = result1.scalars().all()
        objs2 = result2.scalars().all()
        
        objs = objs1 + objs2
        objs = [obj.name for obj in objs]
        logger.debug(str(GameObject(objs1[0])))
        logger.debug(str(objs))
        
        # return archetype(obj) if obj else None
