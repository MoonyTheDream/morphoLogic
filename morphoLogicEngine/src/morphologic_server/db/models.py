"Database Models with Spatial Data and Domain Behavior"

from enum import Enum as E
from typing import ClassVar, List, Optional

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    column_property,
    mapped_column,
    relationship,
    validates,
)

from geoalchemy2 import Geometry
from geoalchemy2.functions import ST_DWithin, ST_Force2D, ST_Intersects
from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point

from morphologic_server import logger
from morphologic_server.exceptions import PermissionDeniedError

STANDARD_LENGTH = 60


class PermisionLevel(E):
    """Simple Enum representing available Permission Levels in DB Tables"""

    ADMIN = 0
    BUILDER = 1
    PLAYER = 2


_ALLOWED_TO_DELETE = PermisionLevel.BUILDER


# 888888b.
# 888  "88b
# 888  .88P
# 8888888K.   8888b.  .d8888b   .d88b.
# 888  "Y88b     "88b 88K      d8P  Y8b
# 888    888 .d888888 "Y8888b. 88888888
# 888   d88P 888  888      X88 Y8b.
# 8888888P"  "Y888888  88888P'  "Y8888
# ------------------------------------------------------------------------------------------------ #
class Base(DeclarativeBase):
    """
    Base class for all database models.
    Provides save/refresh/delete persistence methods.
    """

    _sessionmaker: ClassVar[Optional[async_sessionmaker]] = None

    async def save(self):
        """Save the object to the database."""
        async with self._sessionmaker() as session:
            session.add(self)
            await session.commit()
            await session.refresh(self)

    async def refresh(self):
        """Refresh the object from the database."""
        async with self._sessionmaker() as session:
            refreshed = await session.execute(
                select(self.__class__).where(self.__class__.id == self.id)
            )
            refreshed = refreshed.scalars().first()
            if refreshed:
                # Copy state from refreshed instance
                for attr in self.__class__.__table__.columns.keys():
                    setattr(self, attr, getattr(refreshed, attr))

    async def delete(self):
        """Deletes the object from the database."""
        async with self._sessionmaker() as session:
            await session.delete(self)
            await session.commit()
        return {"success": True, "message": "Object deleted from database."}


#        d8888                                            888
#       d88888                                            888
#      d88P888                                            888
#     d88P 888  .d8888b .d8888b .d88b.  888  888 88888b.  888888 .d8888b
#    d88P  888 d88P"   d88P"   d88""88b 888  888 888 "88b 888    88K
#   d88P   888 888     888     888  888 888  888 888  888 888    "Y8888b.
#  d8888888888 Y88b.   Y88b.   Y88..88P Y88b 888 888  888 Y88b.       X88
# d88P     888  "Y8888P "Y8888P "Y88P"   "Y88888 888  888  "Y888  88888P'
class Account(Base):
    """
    Class representing a table with player accounts.
    """

    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(STANDARD_LENGTH), unique=True)
    email: Mapped[str] = mapped_column(String(STANDARD_LENGTH), unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Permissions: 0 - admin, 1 - builder, 2 - player
    permission_level: Mapped[int] = mapped_column(Integer, default=2)

    # Relationship to character souls
    character_souls: Mapped[Optional[List["CharacterSoul"]]] = relationship(
        back_populates="account", cascade="all, delete-orphan", lazy="selectin"
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Validation ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @validates("name")
    def _validate_name(self, key, value):
        if len(value) > STANDARD_LENGTH:
            raise ValueError(
                f"Account name cannot be longer than {STANDARD_LENGTH} characters."
            )
        return value

    @validates("email")
    def _validate_email(self, key, value):
        if len(value) > STANDARD_LENGTH:
            raise ValueError(
                f"Account email cannot be longer than {STANDARD_LENGTH} characters."
            )
        elif "@" not in value or "." not in value:
            raise ValueError("Invalid email address.")
        return value

    @validates("permission_level")
    def _validate_permission_level(self, key, value):
        if value not in (0, 1, 2):
            raise ValueError(
                "Permission level must be 0 (admin), 1 (builder) or 2 (player)."
            )
        return value

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Password ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    def set_password(self, plain: str) -> None:
        """Hash and store a password for this account."""
        import bcrypt

        self.password_hash = bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

    def check_password(self, plain: str) -> bool:
        """Return True if plain matches the stored hash."""
        import bcrypt

        if not self.password_hash:
            return False
        return bcrypt.checkpw(plain.encode(), self.password_hash.encode())


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
class CharacterSoul(Base):
    """
    Unlike Character, the CharacterSouls is an entity that can puppet other GameObjects (usually
    just it's own Character).
    It also have it's aura - a way of representing kind and not so kind deeds.
    """

    __tablename__ = "character_souls"
    id: Mapped[int] = mapped_column(primary_key=True)

    # Name is not needed. Souls don't have a name. They have a meaning and attitude.
    aura: Mapped[int] = mapped_column(Integer, default=0)

    # Relation with Account
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id"))
    account: Mapped["Account"] = relationship(
        back_populates="character_souls", foreign_keys=account_id, lazy="selectin"
    )

    # Permissions: 0 - admin, 1 - builder, 2 - player
    permission_level: Mapped[int] = mapped_column(Integer, default=2)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Object This Soul Is Puppeting ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    bound_character: Mapped["Character"] = relationship(
        back_populates="soul",
        passive_deletes=True,
        foreign_keys="Character.soul_id",
        lazy="selectin",
    )
    puppeting: Mapped[Optional["GameObject"]] = relationship(
        back_populates="puppeted_by",
        passive_deletes=True,
        foreign_keys="GameObject.puppeted_by_id",
        lazy="selectin",
    )
    # -------------------------------------------------------------------------------------------- #

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Validation ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @validates("permission_level")
    def _validate_permission_level(self, key, value):
        if value not in (0, 1, 2):
            raise ValueError(
                "Permission level must be 0 (admin), 1 (builder) or 2 (player)."
            )
        return value

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Table Args ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    __table_args__ = (
        Index("ix_character_souls_account_id", "account_id"),
    )

    # ******************************************************************************************** #
    #                                            METHODS                                           #
    # ******************************************************************************************** #

    def check_permissions(
        self, required_permission_level: PermisionLevel | int
    ) -> bool:
        """Raises PermissionDeniedError if the soul lacks the required permission level."""
        required_permission_value = (
            required_permission_level.value
            if isinstance(required_permission_level, PermisionLevel)
            else required_permission_level
        )
        if self.permission_level > required_permission_value:
            return False
        return True

    async def delete_object(self, target_object: "Base") -> dict:
        """Deletes given object from DB after checking permissions."""
        if self.check_permissions(_ALLOWED_TO_DELETE):
            async with self._sessionmaker() as session:
                await session.delete(target_object)
                await session.commit()
            return {"success": True, "message": "Target object deleted."}
        raise PermissionDeniedError(
            "Permission denied. The puppeting soul of the caller object "
            "don't have permission to delete this object."
        )


# 88888888888                               d8b
#     888                                   Y8P
#     888
#     888   .d88b.  888d888 888d888 8888b.  888 88888b.
#     888  d8P  Y8b 888P"   888P"      "88b 888 888 "88b
#     888  88888888 888     888    .d888888 888 888  888
#     888  Y8b.     888     888    888  888 888 888  888
#     888   "Y8888  888     888    "Y888888 888 888  888
class TerrainType(E):
    """Simple Enum representing available Terrain Types in DB Tables"""

    SOIL = "soil"
    SAND = "sand"
    ROCK = "rock"
    WATER = "water"


class Terrain(Base):
    """
    Class representing a table with each playable area in the game.
    """

    __tablename__ = "terrain"
    id: Mapped[int] = mapped_column(primary_key=True)

    # Spatial location as a 3D point in SRID 3857 (metres, not really 3D)
    _location: Mapped[str] = mapped_column(
        "location", Geometry(geometry_type="POINTZ", srid=3857)
    )

    # Type of terrain, like forest, desert, water, etc.
    type: Mapped[str] = mapped_column(Enum(TerrainType), default=TerrainType.SOIL)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Location Property ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @hybrid_property
    def location(self):
        """Return location as a Shapely Point."""
        return to_shape(self._location)

    @location.inplace.setter
    def _location_set(self, value):
        """Set location from (x, y, z) tuple or raw Geometry."""
        if isinstance(value, tuple):
            if any(v is None for v in value):
                raise ValueError("Coordinates cannot be None.")
            self._location = from_shape(Point(*value), srid=3857)
        else:
            self._location = value

    @location.inplace.expression
    @classmethod
    def _location_expr(cls):
        """SQL expression returns raw Geometry column."""
        return cls._location

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Validation ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @validates("type")
    def _validate_type(self, key, value):
        if isinstance(value, str):
            value = TerrainType(value)
        if not isinstance(value, TerrainType):
            raise ValueError("Terrain type must be an instance of TerrainType.")
        return value

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Table Args ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    # Functional GIST index on ST_Force2D(location) so the planner can use it for the
    # 2D-distance queries in memory.py and Character.get_terrain_nearby, which wrap
    # the column in ST_Force2D(). A plain GIST on `location` would be ignored by those
    # queries because the expression doesn't match.
    __table_args__ = (
        Index(
            "idx_terrain_location_2d",
            func.ST_Force2D(_location),
            postgresql_using="gist",
        ),
    )

    # ******************************************************************************************** #
    #                                            METHODS                                           #
    # ******************************************************************************************** #
    async def find_nearby(self, distance_m=1.0):
        """Find nearby terrain by coordinates and distance."""
        x, y = self.location.x, self.location.y
        if x is None or y is None:
            logger.warning(
                "Terrain %s has no coordinates. Cannot find nearby terrain.",
                self.id,
            )
            return None

        point = from_shape(Point(x, y), srid=3857)
        async with self._sessionmaker() as session:
            stmt = select(Terrain).where(
                ST_DWithin(Terrain.location, point, distance_m)
            )
            result = await session.execute(stmt)
            terrain = result.scalars().all()

            if terrain:
                return list(terrain)
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
class Area(Base):
    """
    Class representing a table of areas in the game.
    It's a helper class to use for example as building, or a room, or any other area that might
    need to query for all objects inside to interact with it in some way.
    It do not need Z, as it's main purpose is to do spatial queries.
    """

    __tablename__ = "areas"
    id: Mapped[int] = mapped_column(primary_key=True)

    polygon: Mapped[str] = mapped_column(Geometry(geometry_type="POLYGON", srid=3857))
    name: Mapped[str] = mapped_column(String(STANDARD_LENGTH))
    description: Mapped[Optional[str]] = mapped_column(Text)
    # Priority 0 is a ground level default area for description. Priority above 0 takes
    # over the lower priority. For now 1 is max.
    priority: Mapped[int] = mapped_column(Integer, default=0)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Validation ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @validates("name")
    def _validate_name(self, key, value):
        if len(value) > STANDARD_LENGTH:
            raise ValueError(
                f"Area name cannot be longer than {STANDARD_LENGTH} characters."
            )
        return value

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Table Args ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    __table_args__ = (
        Index("idx_areas_polygon", "polygon", postgresql_using="gist"),
    )


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
#
class ObjectType(E):
    """Simple Enum representing available Object Types in DB Tables"""

    ITEM = "item"
    CHARACTER = "character"
    # NPC = "npc"


class GameObject(Base):
    """
    Representing a table of all game objects in the game, with position and attributes.
    """

    __tablename__ = "game_objects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(STANDARD_LENGTH))
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Object type for inheritance
    object_type: Mapped[ObjectType] = mapped_column(Enum(ObjectType))

    # Spatial location as a 3D point in SRID 3857 (metres, not really 3D)
    _location: Mapped[str] = mapped_column(
        "location", Geometry(geometry_type="POINTZ", srid=3857)
    )

    # JSONB column to store dynamic attributes
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)

    # ~~~~~~~~ Containment Relationship: One-to-many (one Object Can Contain Many Others) ~~~~~~~~ #
    container_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("game_objects.id", ondelete="SET NULL")
    )
    container: Mapped["GameObject"] = relationship(
        back_populates="stored",
        remote_side=id,
        foreign_keys=[container_id],
        passive_deletes=True,
        lazy="noload",
    )
    stored: Mapped[List["GameObject"]] = relationship(
        back_populates="container", lazy="noload"
    )
    # -------------------------------------------------------------------------------------------- #

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~ Reference To Soul Puppeting This Object ~~~~~~~~~~~~~~~~~~~~~~~~~ #
    puppeted_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("character_souls.id", ondelete="SET NULL")
    )
    puppeted_by: Mapped["CharacterSoul"] = relationship(
        back_populates="puppeting", lazy="selectin"
    )
    # -------------------------------------------------------------------------------------------- #

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Location Property ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @hybrid_property
    def location(self):
        """Return location as a Shapely Point."""
        return to_shape(self._location)

    @location.inplace.setter
    def _location_set(self, value):
        """Set location from (x, y, z) tuple or raw Geometry."""
        if isinstance(value, tuple):
            if any(v is None for v in value):
                raise ValueError("Coordinates cannot be None.")
            self._location = from_shape(Point(*value), srid=3857)
        else:
            self._location = value

    @location.inplace.expression
    @classmethod
    def _location_expr(cls):
        """SQL expression returns raw Geometry column."""
        return cls._location

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Validation ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    @validates("name")
    def _validate_name(self, key, value):
        if len(value) > STANDARD_LENGTH:
            raise ValueError(
                f"Name cannot be longer than {STANDARD_LENGTH} characters."
            )
        return value

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Table Args ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    __table_args__ = (
        Index("idx_game_objects_location", "location", postgresql_using="gist"),
        Index("ix_game_objects_container_id", "container_id"),
        Index("ix_game_objects_puppeted_by_id", "puppeted_by_id"),
    )

    __mapper_args__ = {
        "polymorphic_on": object_type,
        "polymorphic_identity": ObjectType.ITEM,
    }


#  .d8888b.  888                                        888
# d88P  Y88b 888                                        888
# 888    888 888                                        888
# 888        88888b.   8888b.  888d888 8888b.   .d8888b 888888 .d88b.  888d888
# 888        888 "88b     "88b 888P"      "88b d88P"    888   d8P  Y8b 888P"
# 888    888 888  888 .d888888 888    .d888888 888      888   88888888 888
# Y88b  d88P 888  888 888  888 888    888  888 Y88b.    Y88b. Y8b.     888
#  "Y8888P"  888  888 "Y888888 888    "Y888888  "Y8888P  "Y888 "Y8888  888
class Character(GameObject):
    """
    A table represents game objects that are playable characters. It is separated from soul as if
    a CharacterSoul puppet something else that the Character itself should stay where it was before.
    """

    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(ForeignKey("game_objects.id"), primary_key=True)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Character Specific Fields ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    # Relationship to account. It is allowed for a Character to exist without soul. It does not
    # live, but still exists.
    soul_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("character_souls.id", ondelete="SET NULL")
    )
    soul: Mapped["CharacterSoul"] = relationship(
        back_populates="bound_character", lazy="selectin"
    )

    # Name inheritance
    name: Mapped[str] = column_property(GameObject.name)

    # ------------------------------------------------------------------------------------------------ #

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Table Args ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    __table_args__ = (
        Index("ix_characters_soul_id", "soul_id"),
    )

    __mapper_args__ = {
        "polymorphic_identity": ObjectType.CHARACTER,
        "inherit_condition": id == GameObject.id,
    }

    # ******************************************************************************************** #
    #                                            METHODS                                           #
    # ******************************************************************************************** #
    async def get_areas_im_in(self):
        """Get all areas that contain this character's location."""
        async with self._sessionmaker() as session:
            stmt = select(Area).where(
                ST_Intersects(Area.polygon, ST_Force2D(self._location))
            )
            results = await session.execute(stmt)
            return results.scalars().all()

    async def get_area_im_in(self):
        """Get the highest-priority area this character is currently in."""
        areas = await self.get_areas_im_in()
        areas.sort(key=lambda obj: obj.priority, reverse=True)
        if len(areas) > 1 and areas[0].priority == areas[1].priority:
            logger.warning(
                "More than one area of the same priority at location %s",
                self._location,
            )
        return areas[0] if areas else None

    async def get_terrain_nearby(self, distance_m: float = 10.0) -> list["Terrain"]:
        """Get all terrain points within distance of this character's location."""
        async with self._sessionmaker() as session:
            stmt = select(Terrain).where(
                ST_DWithin(
                    ST_Force2D(Terrain.location),
                    ST_Force2D(self._location),
                    distance_m,
                )
            )
            results = await session.execute(stmt)
            return results.scalars().all()
