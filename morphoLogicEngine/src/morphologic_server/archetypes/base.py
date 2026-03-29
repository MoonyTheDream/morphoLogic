"""API for saving and querrying data from DB"""

from abc import ABC  # , abstractmethod
from enum import Enum
from typing import Optional, Type

from sqlalchemy import select

# from sqlalchemy.orm import selectinload
from geoalchemy2 import shape

from geoalchemy2.functions import ST_DWithin, ST_Force2D, ST_Intersects
from geoalchemy2.shape import from_shape  # , to_shape
from shapely.geometry import Point, Polygon

from morphologic_server import logger
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

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ EXCEPTIONS ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
class PermissionDeniedError(Exception):
    """Custom exception for permission denied errors."""


class ObjectNotFoundError(Exception):
    """Custom exception for object not found errors."""


# class DBError(Exception):
#     """Custom exception for database errors."""
# ------------------------------------------------------------------------------------------------ #


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


# Abstract class for all archetypes in the game
class Archetypes(ABC):
    """Base class for all archetypes in the game."""

    linked_db_obj = BaseDB
    _db_obj = None
    _sessionmaker = None  # Set at startup by MorphoLogicHeart

    @property
    def db_obj(self):
        """Return the database object."""
        return self._db_obj

    @property
    def as_dict(self):

        result = {}

        for attr_name in dir(self):
            # Skip private/protected and callables. "as_dict" must be skipped to avoid recursion.
            if attr_name.startswith("_") or attr_name in {
                "as_dict",
                "container",
                "stored",
                "db_obj",
            }:
                continue

            attr = getattr(self.__class__, attr_name, None)

            # Only process properties
            if isinstance(attr, property):
                try:
                    value = getattr(self, attr_name)

                    # For spatial Point object
                    if isinstance(
                        value, (Character, GameObject, CharacterSoul, Account)
                    ):
                        continue
                    elif attr_name == "location" and hasattr(value, "x"):
                        result[attr_name] = {"x": value.x, "y": value.y, "z": value.z}
                    elif isinstance(value, Enum):
                        result[attr_name] = value.value
                    else:
                        result[attr_name] = value
                except Exception as e:
                    logger.warning("Could not get %s: %s", attr_name, e)
        return result

    # ******************************************************************************************** #
    #                                            METHODS                                           #
    # ******************************************************************************************** #

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Save ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    async def save(self):
        """Save the object to the database."""
        if self._db_obj is not None:
            async with Archetypes._sessionmaker() as session:
                # Attributes of this class always mirror _db_obj attributes
                # So we can just pass the _db_obj to the SQLAlchemy session
                session.add(self._db_obj)
                await session.commit()
                await session.refresh(self._db_obj)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Refresh ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    async def refresh(self):
        """Refresh the object from the database."""
        async with Archetypes._sessionmaker() as session:
            refreshed = await session.execute(
                select(self._db_obj.__class__).where(
                    self._db_obj.__class__.id == self._db_obj.id
                )
            )
            refreshed = refreshed.scalars().first()
            if refreshed:
                self._db_obj = refreshed

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Delete ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    async def delete(self):
        """Deletes the object from the database."""
        async with Archetypes._sessionmaker() as session:
            await session.delete(self._db_obj)
            await session.commit()
            # self._db_obj = None
        return {"success": True, "message": "Calling object deleted from database."}


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

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Permission Level ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def permission_level(self) -> int:
        """Return permission level of this account"""
        return self._db_obj.permission_level

    @permission_level.setter
    def permission_level(self, value: int):
        """Set permission level of this account"""
        if value not in [0, 1, 2]:
            raise ValueError(
                "Permission level must be 0 (admin), 1 (builder) or 2 (player)."
            )
        self._db_obj.permission_level = value

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

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Password ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    def set_password(self, plain: str) -> None:
        """Hash and store a password for this account."""
        import bcrypt
        self._db_obj.password_hash = bcrypt.hashpw(
            plain.encode(), bcrypt.gensalt()
        ).decode()

    def check_password(self, plain: str) -> bool:
        """Return True if plain matches the stored hash."""
        import bcrypt
        if not self._db_obj.password_hash:
            return False
        return bcrypt.checkpw(plain.encode(), self._db_obj.password_hash.encode())


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

    # ******************************************************************************************** #
    #                                            METHODS                                           #
    # ******************************************************************************************** #

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ DELETE ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    def permission_level_is(self, permission_levels: int | tuple[int]) -> bool:
        """Check if the soul has the required permission level.

        Args:
            permission_level (int | list[int]): desired permission level or list of permission
                levels

        Returns:
            bool: True if the character soul has the required permission level, False otherwise
        """
        permission_levels = (
            permission_levels
            if isinstance(permission_levels, tuple)
            else (permission_levels,)
        )
        return self.permission_level in permission_levels

    def check_permissions(self, permission_levels: int | tuple[int] = (0, 1)) -> None:
        """Check if the soul has the required permission level.

        Args:
            permission_level (int | tuple[int]): desired permission level or list of permission
                levels

        Returns:
            None: Raises PermissionDeniedError if the character soul doesn't have the required
                permission level
        """
        if not self.permission_level_is(permission_levels):
            raise PermissionDeniedError(
                "Permission denied. The puppeting soul of the caller object don't have permission to delete this object."
            )

    async def delete_object(self, target_object: Type[Archetypes]) -> dict:
        """Deletes given object from DB.

        Args:
            target_object (Type[Archetypes]): Target object to delete.

        Returns:
            dict: {success: bool, message: str} - success is True if the object was deleted,
                False otherwise.
        """
        # First we check if the permission level of the souls is 0 or 1 (admin or builder)
        self.check_permissions()
        async with Archetypes._sessionmaker() as session:
            await session.delete(target_object.db_obj)
            await session.commit()
        return {"success": True, "message": "Target object deleted."}


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
        async with Archetypes._sessionmaker() as session:
            stmt = select(TerrainDB).where(
                ST_DWithin(TerrainDB.location, point, distance_m)
            )
            result = await session.execute(stmt)
            terrain = result.scalars().all()

            if terrain:
                return [Terrain(t) for t in terrain]
            else:
                return None


#        d8888
#       d88888
#      d88P888
#     d88P 888 888d888 .d88b.   8888b.
#    d88P  888 888P"  d8P  Y8b     "88b
#   d88P   888 888    88888888 .d888888
#  d8888888888 888    Y8b.     888  888
# d88P     888 888     "Y8888  "Y888888
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

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Polygon ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def area(self):
        """Return area"""
        return shape.to_shape(self._db_obj.area)

    @area.setter
    def area(self, value):
        """Set area"""
        polygon = Polygon(value)
        self._db_obj.area = shape.from_shape(polygon, srid=3857)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Name ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def name(self):
        """Return area name"""
        return self._db_obj.name

    @name.setter
    def name(self, value: str):
        """Set area name"""
        if len(value) > _DB_STANDARD_LENGTH:
            raise ValueError(
                f"Area name cannot be longer than {_DB_STANDARD_LENGTH} characters."
            )
        self._db_obj.name = value

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Description ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def description(self):
        """Return description"""
        return self._db_obj.description

    @description.setter
    def description(self, value: str):
        """Set description"""
        self._db_obj.description = value

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Priority ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @property
    def priority(self):
        """Return priority"""
        return self._db_obj.priority

    @priority.setter
    def priority(self, value: int):
        """Set priority"""
        self._db_obj.priority = value


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
    def location(self, value: tuple[float, float, float]):
        """Set location from (x, y, z), using previous value for any missing ones."""

        for i in value:
            if i is None:
                raise ValueError("Coordinates cannot be None.")

        point = Point(value)
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

    async def container(self):
        """Return container linked to this game object"""
        if not self.container_id:
            return None
        async with Archetypes._sessionmaker() as session:
            result = await session.execute(
                select(GameObjectDB).where(GameObjectDB.id == self.container_id)
            )
            container = result.scalar_one_or_none()
            return GameObject(container) if container else None

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Stored ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    async def stored(self):
        """Return game objects stored in this game object"""
        async with Archetypes._sessionmaker() as session:
            result = await session.execute(
                select(GameObjectDB).where(GameObjectDB.container_id == self.id)
            )
            children = result.scalars().all()
            return [GameObject(obj) for obj in children]

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
            character_soul = (
                CharacterSoul(self._db_obj.puppeted_by)
                if self._db_obj.puppeted_by
                else None
            )
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

    # ******************************************************************************************** #
    #                                            METHODS                                           #
    # ******************************************************************************************** #
    async def get_areas_im_in(self):
        async with Archetypes._sessionmaker() as session:
            stmt = select(AreaDB).where(
                ST_Intersects(AreaDB.polygon, ST_Force2D(self._db_obj.location))
            )
            results = await session.execute(stmt)
            results = results.scalars().all()
        return [Area(areadb) for areadb in results]

    async def get_area_im_in(self):
        areas = await self.get_areas_im_in()
        areas.sort(key=lambda obj: obj.priority, reverse=True)
        if len(areas) > 1 and areas[0].priority == areas[1].priority:
            logger.warning(
                "More than one area of the same place in location %s",
                self._db_obj.location,
            )
        # sorted_list = sorted(my_list, key=lambda obj: obj.priority)
        return areas[0] if areas else None

    async def get_surrounding_description(self, memory):
        """Get description of the area this character is in."""
        area = await self.get_area_im_in()
        objects = await memory.get_objects_in_proximity(self)
        game_objects = objects.get("game_objects", [])
        characters = objects.get("characters", [])
        characters_str = "\n".join([f"{char.name} ({char.id})" for char in characters])
        game_objects_str = "\n".join([f"{obj.name} ({obj.id})" for obj in game_objects])

        test_text = f'Character {self.name} is in area "{area.name}" \n Characters around:\n {characters_str} \n\n Objects around:\n {game_objects_str}'
        return test_text
