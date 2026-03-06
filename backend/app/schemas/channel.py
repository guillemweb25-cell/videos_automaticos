from pydantic import BaseModel
from datetime import datetime


class ChannelBase(BaseModel):
    name: str
    youtube_handle: str | None = None
    creds_dir: str | None = None


class ChannelCreate(ChannelBase):
    pass


class ChannelUpdate(BaseModel):
    name: str | None = None
    youtube_handle: str | None = None
    creds_dir: str | None = None


class ChannelResponse(ChannelBase):
    id: int
    user_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
