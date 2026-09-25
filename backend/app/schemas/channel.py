from pydantic import BaseModel
from datetime import datetime


class ChannelBase(BaseModel):
    name: str
    youtube_handle: str | None = None
    creds_dir: str | None = None
    image_style_prompt: str | None = None
    negative_prompt: str | None = None
    default_style: str | None = None
    default_workflow: str | None = None
    loras: list[int] | None = None
    affiliate_url: str | None = None
    affiliate_label: str | None = None
    description_header: str | None = None
    thumbnail_lora_filename: str | None = None
    thumbnail_lora_strength: float | None = None
    thumbnail_lora_trigger: str | None = None


class ChannelCreate(ChannelBase):
    pass


class ChannelUpdate(BaseModel):
    name: str | None = None
    youtube_handle: str | None = None
    creds_dir: str | None = None
    image_style_prompt: str | None = None
    negative_prompt: str | None = None
    default_style: str | None = None
    default_workflow: str | None = None
    loras: list[int] | None = None
    affiliate_url: str | None = None
    affiliate_label: str | None = None
    description_header: str | None = None
    thumbnail_lora_filename: str | None = None
    thumbnail_lora_strength: float | None = None
    thumbnail_lora_trigger: str | None = None


class ChannelResponse(ChannelBase):
    id: int
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
