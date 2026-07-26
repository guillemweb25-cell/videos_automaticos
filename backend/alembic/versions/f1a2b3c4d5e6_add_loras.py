"""add loras registry table and channels.loras assignment

Revision ID: f1a2b3c4d5e6
Revises: c4f9a2b1e3d5
Create Date: 2026-07-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'c4f9a2b1e3d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'loras',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('filename', sa.String(length=500), nullable=False),
        sa.Column('trigger_words', sa.Text(), nullable=True),
        sa.Column('model_strength', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('clip_strength', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.add_column('channels', sa.Column('loras', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('channels', 'loras')
    op.drop_table('loras')
