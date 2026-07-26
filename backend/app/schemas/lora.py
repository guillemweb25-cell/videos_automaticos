from pydantic import BaseModel
from datetime import datetime


class LoraBase(BaseModel):
    label: str
    filename: str
    trigger_words: str | None = None
    model_strength: float = 1.0
    clip_strength: float = 1.0
    notes: str | None = None


class LoraCreate(LoraBase):
    pass


class LoraUpdate(BaseModel):
    label: str | None = None
    filename: str | None = None
    trigger_words: str | None = None
    model_strength: float | None = None
    clip_strength: float | None = None
    notes: str | None = None


class LoraResponse(LoraBase):
    id: int
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
