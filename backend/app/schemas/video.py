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
    voice: Optional[str] = None
    style: Optional[str] = None
    max_images_per_paragraph: int = 2
    llm_provider: str = "openai"

class VideoCreate(VideoBase):
    pass

class VideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    duration_seconds: Optional[float] = None
    voice: Optional[str] = None
    style: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    max_images_per_paragraph: Optional[int] = None
    llm_provider: Optional[str] = None

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

class ImageGenerationRequest(BaseModel):
    style_name: str = "realistic"
    max_images_per_paragraph: int = 2
    model_id: Optional[str] = None
    generation_mode: str = "QUALITY"
    workflow_name: Optional[str] = None

class RegenerateImageRequest(BaseModel):
    paragraph_id: int
    image_id: int
    custom_prompt: Optional[str] = None
    model_id: Optional[str] = None
    generation_mode: str = "QUALITY"
    workflow_name: Optional[str] = None
    seed: Optional[int] = None

class AddImageRequest(BaseModel):
    paragraph_id: int
    style_name: Optional[str] = None
    model_id: Optional[str] = None
    generation_mode: str = "QUALITY"
    workflow_name: Optional[str] = None

class ThumbnailGenerationRequest(BaseModel):
    hook: Optional[str] = None
    visual_prompt: Optional[str] = None
    model_id: Optional[str] = None
    generation_mode: Optional[str] = "QUALITY"

class ConvertToVideoRequest(BaseModel):
    paragraph_id: int
    image_id: int
    duration: int = 8
    model_id: str = "VEO3FAST" # Leonardo: "VEO3" or "VEO3FAST". Ignored if provider=="grok".
    custom_prompt: Optional[str] = None
    provider: str = "leonardo" # "leonardo" or "grok"
