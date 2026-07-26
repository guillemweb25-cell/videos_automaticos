from sqlalchemy import Column, Integer, String, Text, Float, ForeignKey, DateTime
from sqlalchemy.sql import func

from app.models import Base


class Lora(Base):
    """A registered LoRA the user can attach to channels.

    `filename` is the EXACT string ComfyUI expects in a LoraLoader node's
    `lora_name` input (it may include a subfolder with a backslash, e.g.
    'sdxl\\DUSK_XL_TAROTCARD.safetensors'). `trigger_words` is prepended to the
    positive prompt when the LoRA is active.
    """
    __tablename__ = "loras"

    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String(255), nullable=False)          # friendly display name
    filename = Column(String(500), nullable=False)        # exact ComfyUI lora_name
    trigger_words = Column(Text, nullable=True)           # injected into the positive prompt
    model_strength = Column(Float, nullable=False, default=1.0)
    clip_strength = Column(Float, nullable=False, default=1.0)
    notes = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Lora(id={self.id}, label={self.label})>"
