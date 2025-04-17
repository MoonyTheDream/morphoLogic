"""API for saving and querrying data from DB"""

import asyncio

from typing import Optional, Type

from sqlalchemy import select
from geoalchemy2 import shape

from geoalchemy2.functions import ST_DWithin, ST_Equals, ST_Force2D
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point, Polygon

from morphologic_server import logger
from morphologic_server.db.engine import DBAsyncSession
from morphologic_server.db.models import (
    BaseDB,
    AccountDB,
    CharacterSoulDB,
    TerrainType,
    TerrainDB,
    AreaDB,
    ObjectType,
    GameObjectDB,
    CharacterDB,
    STANDARD_LENGTH as _DB_STANDARD_LENGTH,
)

# __all__ = [
#     "add_or_edit_terrain",
# ]


def convert_object_location_to_point(ob):
    """Convert a location of an object to a Shapely Point."""
    ob.location = shape.to_shape(ob.location)
    return ob


# ------------------------------------------------------------------------------------------------ #
#        d8888                 888               888
#       d88888                 888               888
#      d88P888                 888               888
#     d88P 888 888d888 .d8888b 88888b.   .d88b.  888888 888  888 88888b.   .d88b.  .d8888b
#    d88P  888 888P"  d88P"    888 "88b d8P  Y8b 888    888  888 888 "88b d8P  Y8b 88K
#   d88P   888 888    888      888  888 88888888 888    888  888 888  888 88888888 "Y8888b.
#  d8888888888 888    Y88b.    888  888 Y8b.     Y88b.  Y88b 888 888 d88P Y8b.          X88
# d88P     888 888     "Y8888P 888  888  "Y8888   "Y888  "Y88888 88888P"   "Y8888   88888P'
#                                                            888 888
#                                                       Y8b d88P 888
#                                                        "Y88P"  888
# ------------------------------------------------------------------------------------------------ #


class Archetypes:
    """Base class for all archetypes in the game."""

    linked_db_obj = BaseDB
    _db_obj = None

    async def save(self):
        """Save the object to the database."""
        # Compare self to self._db_obj and match the attributes
        if self._db_obj is not None:
            async with DBAsyncSession() as session:
                session.add(self._db_obj)
                await session.commit()
                await session.refresh(self._db_obj)

    async def find_account(self, account_name: str):
        """
        Find account by name.
        If "#[int]" is being searched, it will be searched by ID.
        :param account_name: Name of the account to search for.
        :return: Account object if found, None otherwise.
        """
        async with DBAsyncSession() as session:

            if account_name.startswith("#"):
                try:
                    account_id = int(account_name[1:])
                except ValueError:
                    logger.warning(
                        "Invalid account ID format: %s. Expected format: #[int].",
                        account_name,
                    )
                    return None
                stmt = select(AccountDB).where(AccountDB.id == account_id)

            else:
                # If account name is not a number, search by name
                stmt = select(AccountDB).where(AccountDB.name == account_name)
            result = await session.execute(stmt)
            account = result.scalars().first()

            if account:
                return Account(account)
            return None

    async def search(self, name_or_id: str, archetype: Type["Archetypes"]):
        """
        Search for an object by name or ID.
        If "#[int]" is being searched, it will be searched by ID.

        :param name_or_id: Name or ID of the object to search for.
        :param archetype: The archetype class to search in.
        :return: Object if found, None otherwise.
        """
        model = archetype.linked_db_obj

        async with DBAsyncSession() as session:
            if name_or_id.startswith("#"):
                try:
                    object_id = int(name_or_id[1:])
                except ValueError:
                    logger.warning(
                        "Invalid object ID format: %s. Expected format: #[int].",
                        name_or_id,
                    )
                    return None
                stmt = select(model).where(model.id == object_id)
            else:
                # If name_or_id is not a number, search by name
                stmt = select(model).where(model.name == name_or_id)
            result = await session.execute(stmt)
            obj = result.scalars().first()

            return archetype(obj) if obj else None

    async def simple_query(self, value, attribute: str, model: Type["Archetypes"]):
        """Simple query to find rows from specified table by attribute.

        Args:
            value (any): the value to search for
            attribute (str): an atttribute to search for
            model (Archetypes): the model to search in

        Returns:
            Archetypes: Returns object or objects if found, None otherwise.
        """
        async with DBAsyncSession() as session:
            stmt = select(model.linked_db_obj).where(
                getattr(model.linked_db_obj, attribute) == value
            )
            result = await session.execute(stmt)
            obj = result.scalars().all()

            if obj:
                return [model(o) for o in obj] if len(obj) > 1 else model(obj[0])
            return None

    async def search_by_xy(self, x: float, y: float, archetype: Type["Archetypes"]):
        """Search for an object by coordinates."""
        point = from_shape(Point(x, y), srid=3857)
        model = archetype.linked_db_obj
        async with DBAsyncSession() as session:
            stmt = select(model).where(
                ST_DWithin(
                    ST_Force2D(model.location),
                    ST_Force2D(point),
                    0.1,
                )
            )
            result = await session.execute(stmt)
            obj = result.scalars().first()

            return archetype(obj) if obj else None

    async def add_or_edit_terrain(
        self, x: int, y: int, z: int = 0, terrain_type: TerrainType = TerrainType.SOIL
    ) -> Type["Terrain"]:
        """Add or edit terrain in DB"""

        async with DBAsyncSession() as session:
            point3d = Point(float(x), float(y), float(z))
            point_geom = shape.from_shape(point3d, srid=3857)

            # First check if the terrain already exists
            stmt = select(TerrainDB).where(
                ST_DWithin(
                    ST_Force2D(TerrainDB.location),
                    ST_Force2D(point_geom),
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

                terrain = TerrainDB(location=point_geom, type=terrain_type)
                session.add(terrain)

            await session.commit()
            await session.refresh(terrain)
            return Terrain(terrain)


# Tymczasowo, żeby móc w shell'u korzystać z self
temp_self = Archetypes()


#        d8888                                            888
#       d88888                                            888
#      d88P888                                            888
#     d88P 888  .d8888b .d8888b .d88b.  888  888 88888b.  888888 .d8888b
#    d88P  888 d88P"   d88P"   d88""88b 888  888 888 "88b 888    88K
#   d88P   888 888     888     888  888 888  888 888  888 888    "Y8888b.
#  d8888888888 Y88b.   Y88b.   Y88..88P Y88b 888 888  888 Y88b.       X88
# d88P     888  "Y8888P "Y8888P "Y88P"   "Y88888 888  888  "Y888  88888P'


class Account(Archetypes):
    """Class representing an account in the game"""

    linked_db_obj = AccountDB

    def __init__(self, db_obj: AccountDB):
        self._db_obj = db_obj

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ID ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def id(self):
        """Return account ID"""
        return self._db_obj.id

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Name ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def name(self):
        """Return account name"""
        return self._db_obj.name

    @name.setter
    def name(self, value: str):
        """Set account name"""
        if len(value) > _DB_STANDARD_LENGTH:
            raise ValueError(
                f"Account name cannot be longer than {_DB_STANDARD_LENGTH} characters."
            )
        self._db_obj.name = value

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Email ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def email(self):
        """Return account email"""
        return self._db_obj.email

    @email.setter
    def email(self, value: str):
        """Set account email"""
        if len(value) > _DB_STANDARD_LENGTH:
            raise ValueError(
                f"Account email cannot be longer than {_DB_STANDARD_LENGTH} characters."
            )
        self._db_obj.email = value

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Character Souls ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def character_souls(self) -> list["CharacterSoul"]:
        """Return character souls linked to this account"""
        try:
            souls = [CharacterSoul(soul) for soul in self._db_obj.character_souls]
            return souls
        except Exception as e:
            logger.warning(
                "Failed to get character souls for account %s: %s",
                self._db_obj.id,
                e,
            )
            return []


#  .d8888b.  888                                        888
# d88P  Y88b 888                                        888
# 888    888 888                                        888
# 888        88888b.   8888b.  888d888 8888b.   .d8888b 888888 .d88b.  888d888
# 888        888 "88b     "88b 888P"      "88b d88P"    888   d8P  Y8b 888P"
# 888    888 888  888 .d888888 888    .d888888 888      888   88888888 888
# Y88b  d88P 888  888 888  888 888    888  888 Y88b.    Y88b. Y8b.     888
#  "Y8888P"  888  888 "Y888888 888    "Y888888  "Y8888P  "Y888 "Y8888  888


#  .d8888b.                    888
# d88P  Y88b                   888
# Y88b.                        888
#  "Y888b.    .d88b.  888  888 888 .d8888b
#     "Y88b. d88""88b 888  888 888 88K
#       "888 888  888 888  888 888 "Y8888b.
# Y88b  d88P Y88..88P Y88b 888 888      X88
#  "Y8888P"   "Y88P"   "Y88888 888  88888P'


class CharacterSoul(Archetypes):
    """Class representing a character soul in the game"""

    linked_db_obj = CharacterSoulDB

    def __init__(self, db_obj: CharacterSoulDB):
        self._db_obj = db_obj

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ID ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def id(self):
        """Return character soul ID"""
        return self._db_obj.id

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Aura ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def aura(self) -> int:
        """Return character soul aura"""
        return self._db_obj.aura

    @aura.setter
    def aura(self, value: int):
        """Set character soul aura"""
        self._db_obj.aura = value

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Account ID ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def account_id(self) -> int:
        """Return account ID linked to this character soul"""
        return self._db_obj.account_id

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Account ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def account(self) -> Optional[Account]:
        """Return account linked to this character soul"""
        try:
            account = Account(self._db_obj.account)
            return account
        except Exception as e:
            logger.warning(
                "Failed to get account for character soul %s: %s",
                self._db_obj.id,
                e,
            )
            return None

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Permision Level ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def permission_level(self) -> int:
        """Return permission level of this character soul"""
        return self._db_obj.permission_level

    @permission_level.setter
    def permission_level(self, value: int):
        """Set permission level of this character soul"""
        if value not in [0, 1, 2]:
            raise ValueError(
                "Permission level must be 0 (admin), 1 (builder) or 2 (player)."
            )
        self._db_obj.permission_level = value

    @property
    def bound_character(self) -> Optional[CharacterDB]:
        """Return character linked to this character soul"""
        try:
            character = Character(self._db_obj.bound_character)
            return character
        except Exception as e:
            logger.warning(
                "Failed to get bound character for character soul %s: %s",
                self._db_obj.id,
                e,
            )
            return None

    @property
    def puppeting(self) -> Optional[GameObjectDB]:
        """Return game object linked to this character soul"""
        try:
            game_object = GameObject(self._db_obj.puppeting)
            return game_object
        except Exception as e:
            logger.warning(
                "Failed to get puppeting game object for character soul %s: %s",
                self._db_obj.id,
                e,
            )
            return None


#  .d8888b.                                   .d88888b.  888       d8b                   888
# d88P  Y88b                                 d88P" "Y88b 888       Y8P                   888
# 888    888                                 888     888 888                             888
# 888         8888b.  88888b.d88b.   .d88b.  888     888 88888b.  8888  .d88b.   .d8888b 888888
# 888  88888     "88b 888 "888 "88b d8P  Y8b 888     888 888 "88b "888 d8P  Y8b d88P"    888
# 888    888 .d888888 888  888  888 88888888 888     888 888  888  888 88888888 888      888
# Y88b  d88P 888  888 888  888  888 Y8b.     Y88b. .d88P 888 d88P  888 Y8b.     Y88b.    Y88b.
#  "Y8888P88 "Y888888 888  888  888  "Y8888   "Y88888P"  88888P"   888  "Y8888   "Y8888P  "Y888
#                                                                  888
#                                                                 d88P
#                                                               888P"
class GameObject(Archetypes):
    """Class representing a game object in the game"""

    linked_db_obj = GameObjectDB

    def __init__(self, db_obj: GameObjectDB):
        self._db_obj = db_obj

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ID ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def id(self):
        """Return ID"""
        return self._db_obj.id

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Name ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def name(self):
        """Return name"""
        return self._db_obj.name

    @name.setter
    def name(self, value: str):
        """Set name"""
        if len(value) > _DB_STANDARD_LENGTH:
            raise ValueError(
                f"The name cannot be longer than {_DB_STANDARD_LENGTH} characters."
            )
        self._db_obj.name = value

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Description ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def description(self):
        """Return description"""
        return self._db_obj.description

    @description.setter
    def description(self, value: str):
        """Set description"""
        self._db_obj.description = value

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Object Type ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def object_type(self):
        """Return object type"""
        return self._db_obj.object_type

    @object_type.setter
    def object_type(self, value: ObjectType):
        """Set object type"""
        self._db_obj.object_type = value

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Location ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def location(self):
        """Return location"""
        return shape.to_shape(self._db_obj.location)

    @location.setter
    def location(self, x: float = None, y: float = None, z: float = None):
        """Set location"""

        # Check if x, y, z are None and set them to previous values
        previous = shape.to_shape(self._db_obj.location)
        for attr in ["x", "y", "z"]:
            if locals()[attr] is None:
                locals()[attr] = getattr(previous, attr)

        if x is None or y is None or z is None:
            raise ValueError("Coordinates cannot be None.")

        point = Point(float(x), float(y), float(z))
        self._db_obj.location = shape.from_shape(point, srid=3857)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Attributes ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def attributes(self) -> dict:
        """Return attributes"""
        return self._db_obj.attributes

    @attributes.setter
    def attributes(self, value: dict):
        """Set attributes"""
        if not isinstance(value, dict):
            raise ValueError("Attributes must be a dictionary.")
        self._db_obj.attributes = value

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Container ID ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def container_id(self):
        """Return container ID"""
        return self._db_obj.container_id

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Container ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def container(self):
        """Return container linked to this game object"""
        try:
            container = GameObject(self._db_obj.container)
            return container
        except Exception as e:
            logger.warning(
                "Failed to get container for game object %s: %s",
                self._db_obj.id,
                e,
            )
            return None

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Stored ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def stored(self):
        """Return game objects stored in this game object"""
        try:
            items = [GameObject(item) for item in self._db_obj.stored]
            return items
        except Exception as e:
            logger.warning(
                "Failed to get stored items for game object %s: %s",
                self._db_obj.id,
                e,
            )
            return None

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Puppeted By ID ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def puppeted_by_id(self):
        """Return ID of character soul linked to this game object"""
        return self._db_obj.puppeted_by_id

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Puppeted By ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def puppeted_by(self):
        """Return character soul linked to this game object"""
        try:
            character_soul = CharacterSoul(self._db_obj.puppeted_by)
            return character_soul
        except Exception as e:
            logger.warning(
                "Failed to get puppeted by character soul for game object %s: %s",
                self._db_obj.id,
                e,
            )
            return None


#  .d8888b.  888                                        888
# d88P  Y88b 888                                        888
# 888    888 888                                        888
# 888        88888b.   8888b.  888d888 8888b.   .d8888b 888888 .d88b.  888d888
# 888        888 "88b     "88b 888P"      "88b d88P"    888   d8P  Y8b 888P"
# 888    888 888  888 .d888888 888    .d888888 888      888   88888888 888
# Y88b  d88P 888  888 888  888 888    888  888 Y88b.    Y88b. Y8b.     888
#  "Y8888P"  888  888 "Y888888 888    "Y888888  "Y8888P  "Y888 "Y8888  888
class Character(GameObject):
    """Class representing a character in the game"""

    linked_db_obj = CharacterDB

    def __init__(self, db_obj: CharacterDB):
        super().__init__(db_obj)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Soul ID ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def soul_id(self):
        """Return character soul ID"""
        return self._db_obj.soul_id

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Soul ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def soul(self) -> Optional[CharacterSoulDB]:
        """Return character soul linked to this character"""
        if self._db_obj.soul:
            character_soul = CharacterSoul(self._db_obj.soul)
            return character_soul
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


class Terrain(Archetypes):
    """Class representing a terrain in the game"""

    linked_db_obj = TerrainDB

    def __init__(self, db_obj: TerrainDB):
        self._db_obj = db_obj

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ID ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def id(self):
        """Return terrain ID"""
        return self._db_obj.id

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Location ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def location(self):
        """Return location"""
        return shape.to_shape(self._db_obj.location)

    @location.setter
    def location(self, x: float = None, y: float = None, z: float = None):
        """Set location"""

        # Check if x, y, z are None and set them to previous values
        previous = shape.to_shape(self._db_obj.location)
        for attr in ["x", "y", "z"]:
            if locals()[attr] is None:
                locals()[attr] = getattr(previous, attr)

        if x is None or y is None or z is None:
            raise ValueError("Coordinates cannot be None.")

        point = Point(float(x), float(y), float(z))
        self._db_obj.location = shape.from_shape(point, srid=3857)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Terrain Type ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def terrain_type(self):
        """Return terrain type"""
        return self._db_obj.type

    @terrain_type.setter
    def terrain_type(self, value: TerrainType):
        """Set terrain type"""
        if not isinstance(value, TerrainType):
            raise ValueError("Terrain type must be an instance of TerrainType.")
        self._db_obj.type = value

    async def find_nearby(self, distance_m=1.0):
        """Find nearby terrain by coordinates and distance"""
        x, y = self.location.x, self.location.y
        if x is None or y is None:
            logger.warning(
                "Terrain %s has no coordinates. Cannot find nearby terrain.",
                self.id,
            )
            return None

        point = from_shape(Point(x, y), srid=3857)
        async with DBAsyncSession() as session:
            stmt = select(TerrainDB).where(
                ST_DWithin(TerrainDB.location, point, distance_m)
            )
            result = await session.execute(stmt)
            terrain = result.scalars().all()

            if terrain:
                return [Terrain(t) for t in terrain]
            else:
                return None

class Area(Archetypes):
    """Class representing an area in the game"""

    linked_db_obj = AreaDB

    def __init__(self, db_obj: AreaDB):
        self._db_obj = db_obj

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ID ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def id(self):
        """Return area ID"""
        return self._db_obj.id
    
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Area ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def area(self):
        """Return area"""
        return shape.to_shape(self._db_obj.area)
    @area.setter
    def area(self, value):
        """Set area"""
        polygon = Polygon(value)
        self._db_obj.area = shape.from_shape(polygon, srid=3857)
        