"""add thumbnail LoRA fields to channels (LoRA de estilo para miniaturas)

Revision ID: d4f6a8c0e2b5
Revises: c3e5f7a9b2d4
Create Date: 2026-09-25 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f6a8c0e2b5'
down_revision: Union[str, None] = 'c3e5f7a9b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # LoRA SDXL de estilo aplicado SOLO a la miniatura (independiente de las LoRAs
    # de personaje que usan las imágenes del cuerpo).
    op.add_column('channels', sa.Column('thumbnail_lora_filename', sa.String(length=255), nullable=True))
    op.add_column('channels', sa.Column('thumbnail_lora_strength', sa.Float(), nullable=True))
    op.add_column('channels', sa.Column('thumbnail_lora_trigger', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('channels', 'thumbnail_lora_trigger')
    op.drop_column('channels', 'thumbnail_lora_strength')
    op.drop_column('channels', 'thumbnail_lora_filename')
