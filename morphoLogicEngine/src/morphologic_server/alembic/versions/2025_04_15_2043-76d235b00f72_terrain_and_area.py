"""terrain and area

Revision ID: 76d235b00f72
Revises: 00014265fde1
Create Date: 2025-04-15 20:43:04.853397

"""
import geoalchemy2

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '76d235b00f72'
down_revision: Union[str, None] = '00014265fde1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('areas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('polygon', geoalchemy2.types.Geometry(geometry_type='POLYGON', srid=3857, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    # op.create_index('idx_areas_polygon', 'areas', ['polygon'], unique=False, postgresql_using='gist')
    op.create_table('terrain',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('location', geoalchemy2.types.Geometry(geometry_type='POINTZ', srid=3857, from_text='ST_GeomFromEWKT', name='geometry', nullable=False), nullable=False),
    sa.Column('type', sa.Enum('SOIL', 'SAND', 'ROCK', 'WATER', name='terraintype'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    # op.create_index('idx_terrain_location', 'terrain', ['location'], unique=False, postgresql_using='gist')
    op.alter_column('accounts', 'name',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.String(length=60),
               existing_nullable=False)
    op.alter_column('game_objects', 'name',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.String(length=60),
               existing_nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('game_objects', 'name',
               existing_type=sa.String(length=60),
               type_=sa.VARCHAR(length=50),
               existing_nullable=False)
    op.alter_column('accounts', 'name',
               existing_type=sa.String(length=60),
               type_=sa.VARCHAR(length=50),
               existing_nullable=False)
    op.drop_index('idx_terrain_location', table_name='terrain', postgresql_using='gist')
    op.drop_table('terrain')
    op.drop_index('idx_areas_polygon', table_name='areas', postgresql_using='gist')
    op.drop_table('areas')
    # ### end Alembic commands ###
