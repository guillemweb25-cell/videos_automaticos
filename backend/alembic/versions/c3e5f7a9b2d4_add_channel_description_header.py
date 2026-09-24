"""add description_header to channels (bloque fijo arriba de la descripción)

Revision ID: c3e5f7a9b2d4
Revises: b2d4e6f8a1c3
Create Date: 2026-09-24 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e5f7a9b2d4'
down_revision: Union[str, None] = 'b2d4e6f8a1c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Texto fijo del canal que se antepone a la descripción de los vídeos nuevos
    # (típicamente el CTA + enlace de afiliado). Independiente del QR.
    op.add_column('channels', sa.Column('description_header', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('channels', 'description_header')
