"Database Models with Spacial Data"
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Column, Integer, String, Float, Boolean, Index
from geoalchemy2 import Geometry
# ------------------------------------------------------------------------------------------------ #

class GameObject(DeclarativeBase):
    __tablename__ = 'game_objects'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    
    # Spatial location as a 3D point in SRID 3857 (meteres, not really 3D)
    location: Mapped[str] = mapped_column(Geometry(geometry_type="POINTZ", srid=3857))
    
    # Test additional atributes:
    flammable: Mapped[str] = mapped_column(Boolean)
    material: Mapped[str] = mapped_column(String(50)))
    weight: Mapped[float] = mapped_column(Float)
    
    __table_args__ =(
        Index("ix_game_objects_location", "location", postgresql_using="gist"),
    )
