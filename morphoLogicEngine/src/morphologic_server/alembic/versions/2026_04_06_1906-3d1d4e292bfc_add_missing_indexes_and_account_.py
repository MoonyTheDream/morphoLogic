"""add_missing_indexes_and_account_uniqueness

Revision ID: 3d1d4e292bfc
Revises: a1b2c3d4e5f6
Create Date: 2026-04-06 19:06:04.634811

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3d1d4e292bfc'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: autogenerate also proposed `op.drop_table('spatial_ref_sys')` and an
    # `op.create_unique_constraint(None, ...)` pair. `spatial_ref_sys` is a PostGIS
    # system table that must NOT be dropped, so those calls were removed. The
    # unique constraints are given explicit names so the downgrade can drop them.
    op.create_unique_constraint('uq_accounts_name', 'accounts', ['name'])
    op.create_unique_constraint('uq_accounts_email', 'accounts', ['email'])
    op.create_index('ix_character_souls_account_id', 'character_souls', ['account_id'], unique=False)
    op.create_index('ix_characters_soul_id', 'characters', ['soul_id'], unique=False)
    op.create_index('ix_game_objects_container_id', 'game_objects', ['container_id'], unique=False)
    op.create_index('ix_game_objects_puppeted_by_id', 'game_objects', ['puppeted_by_id'], unique=False)
    op.create_index(
        'idx_terrain_location_2d',
        'terrain',
        [sa.literal_column('ST_Force2D(location)')],
        unique=False,
        postgresql_using='gist',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_terrain_location_2d', table_name='terrain', postgresql_using='gist')
    op.drop_index('ix_game_objects_puppeted_by_id', table_name='game_objects')
    op.drop_index('ix_game_objects_container_id', table_name='game_objects')
    op.drop_index('ix_characters_soul_id', table_name='characters')
    op.drop_index('ix_character_souls_account_id', table_name='character_souls')
    op.drop_constraint('uq_accounts_email', 'accounts', type_='unique')
    op.drop_constraint('uq_accounts_name', 'accounts', type_='unique')
