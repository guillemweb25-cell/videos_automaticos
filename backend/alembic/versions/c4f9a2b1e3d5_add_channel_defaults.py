"""add default_workflow and default_style to channels

Revision ID: c4f9a2b1e3d5
Revises: 427f441af29c
Create Date: 2026-05-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4f9a2b1e3d5'
down_revision: Union[str, None] = '427f441af29c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('channels', sa.Column('default_style', sa.String(length=100), nullable=True))
    op.add_column('channels', sa.Column('default_workflow', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('channels', 'default_workflow')
    op.drop_column('channels', 'default_style')
