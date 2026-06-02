"""container to holder and stored to holds

Revision ID: f1b6c6664590
Revises: 4c1925db9e4e
Create Date: 2026-05-12 09:26:18.377483

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f1b6c6664590'
down_revision: Union[str, None] = '4c1925db9e4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('game_objects', 'container_id', new_column_name='holder_id')
    op.execute('ALTER INDEX ix_game_objects_container_id RENAME TO ix_game_objects_holder_id')
    op.execute('ALTER TABLE game_objects RENAME CONSTRAINT game_objects_container_id_fkey TO game_objects_holder_id_fkey')


def downgrade() -> None:
    """Downgrade schema."""
    op.execute('ALTER TABLE game_objects RENAME CONSTRAINT game_objects_holder_id_fkey TO game_objects_container_id_fkey')
    op.execute('ALTER INDEX ix_game_objects_holder_id RENAME TO ix_game_objects_container_id')
    op.alter_column('game_objects', 'holder_id', new_column_name='container_id')
