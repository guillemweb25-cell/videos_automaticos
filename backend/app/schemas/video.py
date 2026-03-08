from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class VideoBase(BaseModel):
    channel_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    is_short: bool = False
    width: int = 1024
    height: int = 1792
    youtube_title: Optional[str] = None
    youtube_description: Optional[str] = None
    youtube_tags: Optional[str] = None

class VideoCreate(VideoBase):
    pass

class VideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    duration_seconds: Optional[float] = None

class VideoResponse(VideoBase):
    id: int
    status: str
    base_dir: Optional[str] = None
    duration_seconds: Optional[float] = None
    last_error: Optional[str] = None
    youtube_video_id: Optional[str] = None
    is_uploaded: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ParagraphDurations(BaseModel):
    id: int
    extract: str
    seconds: float
    file: str
