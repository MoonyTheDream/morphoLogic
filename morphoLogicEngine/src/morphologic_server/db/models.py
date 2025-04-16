"Database Models with Spacial Data"

from enum import Enum as E
from typing import List, Optional

from sqlalchemy.orm import (
    column_property,
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy import Enum, String, Text, Integer, Index, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry

STANDARD_LENGTH = 60


# ------------------------------------------------------------------------------------------------ #
class BaseDB(DeclarativeBase):
    """
    Base class for all database models.
    """
    pass


class AccountDB(BaseDB):
    """
    Class representing a table with player accounts.
    """

    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(STANDARD_LENGTH))
    email: Mapped[str] = mapped_column(String(STANDARD_LENGTH))
    # password_hash: Mapped[str] = mapped_column(String(255))

    # Relationship to character souls
    character_souls: Mapped[Optional[List["CharacterSoulDB"]]] = relationship(
        back_populates="account", cascade="all, delete-orphan",
        lazy="selectin"
    )


class CharacterSoulDB(BaseDB):
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
    account: Mapped["AccountDB"] = relationship(
        back_populates="character_souls",
        foreign_keys=account_id,
        lazy="selectin"
    )

    # Permissions: 0 - admin, 1 - builder, 2 - player
    permission_level: Mapped[int] = mapped_column(Integer)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Object This Soul Is Puppeting ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    bound_character: Mapped["CharacterDB"] = relationship(
        back_populates="soul", passive_deletes=True,
        foreign_keys="CharacterDB.soul_id",
        lazy="selectin"
    )
    puppeting: Mapped[Optional["GameObjectDB"]] = relationship(
        back_populates="puppeted_by",
        passive_deletes=True,
        foreign_keys="GameObjectDB.puppeted_by_id",
        lazy="selectin"
    )
    # -------------------------------------------------------------------------------------------- #


class TerrainType(E):
    """Simple Enum representing available Terrain Types in DB Tables"""

    SOIL = "soil"
    SAND = "sand"
    ROCK = "rock"
    WATER = "water"


class TerrainDB(BaseDB):
    """
    Class representing a table with each playable area in the game.
    """

    __tablename__ = "terrain"
    id: Mapped[int] = mapped_column(primary_key=True)

    # Spatial location as a 3D point in SRID 3857 (meteres, not really 3D)
    location: Mapped[str] = mapped_column(
        Geometry(geometry_type="POINTZ", srid=3857))

    # Type of terrain, like forest, desert, water, etc.
    type: Mapped[str] = mapped_column(Enum(TerrainType), default=TerrainType.SOIL)


class AreaDB(BaseDB):
    """
    Class representing a table of areas in the game.
    It's a helper class to use for example as building, or a room, or any other area that might
    need to query for all objects inside to interact with it in some way.
    It do not need Z, as it's main purpose is to do spatial queries.
    """

    __tablename__ = "areas"
    id: Mapped[int] = mapped_column(primary_key=True)

    polygon: Mapped[str] = mapped_column(
        Geometry(geometry_type="POLYGON", srid=3857))


class ObjectType(E):
    """Simple Enum representing available Object Types in DB Tables"""

    ITEM = "item"
    CHARACTER = "character"
    # NPC = "npc"


class GameObjectDB(BaseDB):
    """
    Representing a table of all game objects in the game, with position and attributes.
    """

    __tablename__ = "game_objects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(STANDARD_LENGTH))
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Object type for inheritance
    object_type: Mapped[ObjectType] = mapped_column(Enum(ObjectType))

    # Spatial location as a 3D point in SRID 3857 (meteres, not really 3D)
    location: Mapped[str] = mapped_column(
        Geometry(geometry_type="POINTZ", srid=3857))

    # JSONB column to store dynamic attributes
    attributes: Mapped[dict] = mapped_column(JSONB, default=dict)

    # ~~~~~~~~ Containment Relationship: One-to-many (one Object Can Contain Many Others) ~~~~~~~~ #
    container_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("game_objects.id", ondelete="SET NULL")
    )
    container: Mapped["GameObjectDB"] = relationship(
        back_populates="stored",
        remote_side=id,
        foreign_keys=[container_id],
        passive_deletes=True,
        lazy="selectin"
    )
    stored: Mapped[List["GameObjectDB"]] = relationship(
        back_populates="container",
        lazy="selectin"
    )
    # -------------------------------------------------------------------------------------------- #

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~ Reference To Soul Puppeting This Object ~~~~~~~~~~~~~~~~~~~~~~~~~ #
    puppeted_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("character_souls.id", ondelete="SET NULL")
    )
    puppeted_by: Mapped["CharacterSoulDB"] = relationship(
        back_populates="puppeting",
        lazy="selectin")
    # -------------------------------------------------------------------------------------------- #

    __table_args__ = (
        Index("idx_game_objects_location", "location", postgresql_using="gist"),
    )

    __mapper_args__ = {
        "polymorphic_on": object_type,
        "polymorphic_identity": ObjectType.ITEM,
    }


# ------------------------------------------------------------------------------------------------ #
class CharacterDB(GameObjectDB):
    """
    A table represents game objects that are playable characters. It is seperated from soul as if
    a CharacterSoul puppet something else that the Character itself should stay where it was before.
    """

    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(
        ForeignKey("game_objects.id"), primary_key=True)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Character Specific Fields ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    # Relationship to account. It is allowed for a Character to exist without soul. It does not
    # live, but still exists.
    soul_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("character_souls.id", ondelete="SET NULL")
    )
    soul: Mapped["CharacterSoulDB"] = relationship(
        back_populates="bound_character",
        lazy="selectin"
    )

    # Name inheritance
    name: Mapped[str] = column_property(GameObjectDB.name)

    # ------------------------------------------------------------------------------------------------ #

    __mapper_args__ = {
        "polymorphic_identity": ObjectType.CHARACTER,
        "inherit_condition": id == GameObjectDB.id,
    }
