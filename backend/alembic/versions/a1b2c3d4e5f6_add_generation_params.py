"""add generation params

Revision ID: a1b2c3d4e5f6
Revises: 85522d7b89ab
Create Date: 2026-03-08 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '85522d7b89ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Check for column existence before adding
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('videos')]
    
    if 'voice' not in columns:
        op.add_column('videos', sa.Column('voice', sa.String(length=100), nullable=True))
    if 'style' not in columns:
        op.add_column('videos', sa.Column('style', sa.String(length=100), nullable=True))
    if 'max_images_per_paragraph' not in columns:
        op.add_column('videos', sa.Column('max_images_per_paragraph', sa.Integer(), nullable=True, server_default='2'))


def downgrade() -> None:
    op.drop_column('videos', 'max_images_per_paragraph')
    op.drop_column('videos', 'style')
    op.drop_column('videos', 'voice')
