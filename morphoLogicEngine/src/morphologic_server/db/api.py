"""API for saving and querrying data from DB"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from geoalchemy2 import shape

from geoalchemy2.functions import ST_DWithin, ST_Equals, ST_Force2D
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point

from morphologic_server import settings, logger
from morphologic_server.db.models import (
    Account,
    CharacterSoul,
    TerrainType,
    Terrain,
    Area,
    ObjectType,
    GameObject,
    Character,
)

__all__ = [
    "add_or_edit_terrain",
]

engine = create_async_engine("postgresql+asyncpg://" + settings.DB_ADDRESS)

DBAsyncSession = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


def convert_object_location_to_point(ob):
    """Convert a location of an object to a Shapely Point."""
    ob.location = shape.to_shape(ob.location)
    return ob


# ------------------------------------------------------------------------------------------------ #

# 8888888b.  888888b.
# 888  "Y88b 888  "88b
# 888    888 888  .88P
# 888    888 8888888K.
# 888    888 888  "Y88b
# 888    888 888    888
# 888  .d88P 888   d88P
# 8888888P"  8888888P"


# 888    888        d8888 888b    888 8888888b.  888      8888888888 8888888b.   .d8888b.
# 888    888       d88888 8888b   888 888  "Y88b 888      888        888   Y88b d88P  Y88b
# 888    888      d88P888 88888b  888 888    888 888      888        888    888 Y88b.
# 8888888888     d88P 888 888Y88b 888 888    888 888      8888888    888   d88P  "Y888b.
# 888    888    d88P  888 888 Y88b888 888    888 888      888        8888888P"      "Y88b.
# 888    888   d88P   888 888  Y88888 888    888 888      888        888 T88b         "888
# 888    888  d8888888888 888   Y8888 888  .d88P 888      888        888  T88b  Y88b  d88P
# 888    888 d88P     888 888    Y888 8888888P"  88888888 8888888888 888   T88b  "Y8888P"

# ------------------------------------------------------------------------------------------------ #

#        d8888  .d8888b.   .d8888b.   .d88888b.  888     888 888b    888 88888888888 .d8888b.
#       d88888 d88P  Y88b d88P  Y88b d88P" "Y88b 888     888 8888b   888     888    d88P  Y88b
#      d88P888 888    888 888    888 888     888 888     888 88888b  888     888    Y88b.
#     d88P 888 888        888        888     888 888     888 888Y88b 888     888     "Y888b.
#    d88P  888 888        888        888     888 888     888 888 Y88b888     888        "Y88b.
#   d88P   888 888    888 888    888 888     888 888     888 888  Y88888     888          "888
#  d8888888888 Y88b  d88P Y88b  d88P Y88b. .d88P Y88b. .d88P 888   Y8888     888    Y88b  d88P
# d88P     888  "Y8888P"   "Y8888P"   "Y88888P"   "Y88888P"  888    Y888     888     "Y8888P"

async def get_account_by_id(account_id: int) -> Account:
    """Get account from DB"""

    async with DBAsyncSession() as session:
        stmt = select(Account).where(Account.id == account_id)
        result = await session.execute(stmt)
        account = result.scalars().first()

        if account:
            return account
        else:
            return None
        
async def get_account_by_name_or_email(input: str) -> Account:
    """Get account from DB by name or email"""
    if "@" in input:
        # If the input contains '@', it's an email
        stmt = select(Account).where(Account.email == input)
    else:
        # Otherwise, it's a name
        stmt = select(Account).where(Account.name == input)
    async with DBAsyncSession() as session:
        result = await session.execute(stmt)
        account = result.scalars().first()

        if account:
            return account
        else:
            return None

# 88888888888                               d8b
#     888                                   Y8P
#     888
#     888   .d88b.  888d888 888d888 8888b.  888 88888b.
#     888  d8P  Y8b 888P"   888P"      "88b 888 888 "88b
#     888  88888888 888     888    .d888888 888 888  888
#     888  Y8b.     888     888    888  888 888 888  888
#     888   "Y8888  888     888    "Y888888 888 888  888


async def get_terrain_by_id(terrain_id: int) -> Terrain:
    """Get terrain from DB"""

    async with DBAsyncSession() as session:
        stmt = select(Terrain).where(Terrain.id == terrain_id)
        result = await session.execute(stmt)
        terrain = result.scalars().first()

        if terrain:
            return terrain
        else:
            return None


async def get_terrain_by_xy(x: int, y: int) -> Terrain:
    """Get terrain from DB"""

    async with DBAsyncSession() as session:
        point = Point(float(x), float(y), 0.0)
        point_geom = shape.from_shape(point, srid=3857)

        stmt = select(Terrain).where(
            ST_DWithin(
                ST_Force2D(Terrain.location),
                ST_Force2D(point_geom),
                0.1,
            )
        )
        result = await session.execute(stmt)
        terrain = result.scalars().first()

        if terrain:
            return terrain
        else:
            return None


async def add_or_edit_terrain(
    x: int, y: int, z: int = 0, terrain_type: TerrainType = TerrainType.SOIL
) -> Terrain:
    """Add or edit terrain in DB"""

    async with DBAsyncSession() as session:
        point3d = Point(float(x), float(y), float(z))
        point_geom = shape.from_shape(point3d, srid=3857)

        # First check if the terrain already exists
        stmt = select(Terrain).where(
            ST_DWithin(
                ST_Force2D(Terrain.location),
                ST_Force2D(shape.from_shape(Point(float(x), float(y)), srid=3857)),
                0.1,
            )
        )
        result = await session.execute(stmt)
        terrain = result.scalars().first()

        if terrain:
            # Terrain already exists, update it
            old_point = shape.to_shape(terrain.location)
            new_point = Point(old_point.x, old_point.y, float(z))

            terrain.location = shape.from_shape(new_point, srid=3857)
            terrain.type = terrain_type
        else:
            # Terrain doesn't exist, create a new one

            terrain = Terrain(location=point_geom, type=terrain_type)
            session.add(terrain)

        await session.commit()
        await session.refresh(terrain)
        return terrain


# ------------------------------------------------------------------------------------------------ #


# async def test_querry():
#     session = AsyncSession(engine)
#     stmt = select(Character)
#     result = await session.scalars(stmt)
#     result = result.all()
#     # print(result)
#     for line in result:
#         print(vars(line))
#     await session.close()
#     return result


# async def query_nearby(x: float, y: float, distance_m=1.0):
#     async with AsyncSession(engine) as session:
#         point = from_shape(
#             Point(x, y), srid=3857
#         )  # Replace 4326 with your SRID if different

#         stmt = select(GameObject).where(
#             ST_DWithin(GameObject.location, point, distance_m)
#         )
#         result = await session.scalars(stmt)
#         result = result.all()

#         print("Współżędne itemów:\n")
#         for line in result:
#             point = to_shape(line.location)
#             print(f"x: {point.x} y: {point.y}\n")

#         print(
#             f"\nItemy w odległości {distance_m}m od punktu ({x}, {y}):\n"
#             + str(len(result))
#         )
#         return result


# async def zakolejkuj():
#     async with asyncio.TaskGroup() as tg:
#         # tg.create_task(test_querry())
#         tg.create_task(query_nearby(0, 0, 3))


# if __name__ == "__main__":
#     asyncio.run(zakolejkuj())
