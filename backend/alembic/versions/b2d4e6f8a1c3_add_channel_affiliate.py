"""add affiliate_url and affiliate_label to channels (QR de afiliado)

Revision ID: b2d4e6f8a1c3
Revises: a7b8c9d0e1f2
Create Date: 2026-09-24 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2d4e6f8a1c3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enlace que codifica el QR (link de afiliado del libro del canal, etc.)
    op.add_column('channels', sa.Column('affiliate_url', sa.String(length=500), nullable=True))
    # Etiqueta que se muestra sobre el QR (p.ej. "Compra el libro 📖\nbit.ly/pilar-libro")
    op.add_column('channels', sa.Column('affiliate_label', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('channels', 'affiliate_label')
    op.drop_column('channels', 'affiliate_url')
