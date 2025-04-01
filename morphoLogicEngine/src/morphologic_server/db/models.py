"Database Models with Spacial Data"
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import  String, Integer, Index, ForeignKey, Table, Column
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
# ------------------------------------------------------------------------------------------------ #
class Base(DeclarativeBase):
    pass

# Object containment association table
object_containment = Table(
    'object_containment',
    Base.metadata,
    Column('container_id', Integer, ForeignKey('game_objects.id')),
    Column('contained_id', Integer, ForeignKey('game_objects.id'))
)

class Account(Base):
    __tablename__ = 'account'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(60))
    # password_hash: Mapped[str] = mapped_column(String(255))

    # Relationship to characters
    characters = relationship("Character", back_populates="account")
    
class GameObject(Base):
    __tablename__ = 'game_objects'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(String(1600))
    
    # Object type for inheritance
    object_type: Mapped[str] = mapped_column(String(50))
    
    # Spatial location as a 3D point in SRID 3857 (meteres, not really 3D)
    location: Mapped[str] = mapped_column(Geometry(geometry_type="POINTZ", srid=3857))
    
    # JSONB column to store dynamic attributes
    attributes: Mapped[dict] = mapped_column(JSONB)
    
    # Relationship for contained objects
    contained_objects = relationship(
        "GameObject",
        secondary=object_containment,
        priparyjoin=(id == object_containment.c.container_id),
        secondaryjoin=(id == object_containment.c.contained_id),
        backref="containers"
    )
    
    # Reference to character puppeting this object
    puppeted_by: Mapped[int] = mapped_column(Integer, ForeignKey("characters.id"), nullable=True)
    
    
    __table_args__ =(   
        Index("ix_game_objects_location", "location", postgresql_using="gist"),
    )

    __mapper_args__ = {
        "polymorphic_on": object_type,
        "polymorphic_identity": "game_object"
    }
    
class Character(GameObject):
    __tablename__ = 'characters'
    
    id: Mapped[int] = mapped_column(ForeignKey("game_objects.id"), primary_key=True)
    
    # Character specific fields
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("account.id"))
    level: Mapped[int] = mapped_column(Integer)
    
    # Relationship to account
    account = relationship("Account", back_populates="characters")
    # Object this character is puppeting
    puppeting = relationship("GameObject", foreign_keys=[GameObject.puppeted_by])
    
    __mapper_args__ = {
        "polymorphic_identity": "character"
    }