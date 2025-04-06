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


# ------------------------------------------------------------------------------------------------ #
class Base(DeclarativeBase):
    pass


class Account(Base):
    """
    Class representing a table with player accounts.
    """

    __tablename__ = "accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(60))
    # password_hash: Mapped[str] = mapped_column(String(255))

    # Relationship to character souls
    character_souls: Mapped[Optional[List["CharacterSoul"]]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


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
        back_populates="character_souls",
        foreign_keys=account_id,
        )

    # Permissions: 0 - admin, 1 - builder, 2 - player
    permission_level: Mapped[int] = mapped_column(Integer)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Object This Soul Is Puppeting ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
    bound_character: Mapped["Character"] = relationship(
        back_populates="soul", passive_deletes=True,
        foreign_keys="Character.soul_id"
    )
    puppeting: Mapped[Optional["GameObject"]] = relationship(
        back_populates="puppeted_by",
        passive_deletes=True,
        foreign_keys="GameObject.puppeted_by_id"
    )
    # -------------------------------------------------------------------------------------------- #


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
    name: Mapped[str] = mapped_column(String(50))
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Object type for inheritance
    object_type: Mapped[ObjectType] = mapped_column(Enum(ObjectType))

    # Spatial location as a 3D point in SRID 3857 (meteres, not really 3D)
    location: Mapped[str] = mapped_column(Geometry(geometry_type="POINTZ", srid=3857))

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
    )
    stored: Mapped[List["GameObject"]] = relationship(
        back_populates="container",
    )
    # -------------------------------------------------------------------------------------------- #

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~ Reference To Soul Puppeting This Object ~~~~~~~~~~~~~~~~~~~~~~~~~ #
    puppeted_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("character_souls.id", ondelete="SET NULL")
    )
    puppeted_by: Mapped["CharacterSoul"] = relationship(back_populates="puppeting")
    # -------------------------------------------------------------------------------------------- #

    __table_args__ = (
        Index("idx_game_objects_location", "location", postgresql_using="gist"),
    )

    __mapper_args__ = {
        "polymorphic_on": object_type,
        "polymorphic_identity": ObjectType.ITEM,
    }


# ------------------------------------------------------------------------------------------------ #
class Character(GameObject):
    """
    A table represents game objects that are playable characters. It is seperated from soul as if
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
        back_populates="bound_character",
    )

    # Name inheritance
    name: Mapped[str] = column_property(GameObject.name)

    # ------------------------------------------------------------------------------------------------ #

    __mapper_args__ = {
        "polymorphic_identity": ObjectType.CHARACTER,
        "inherit_condition": id == GameObject.id,
    }
