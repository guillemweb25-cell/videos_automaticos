from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Float, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models import Base

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    status = Column(String(50), default="draft") # draft, generating, ready, failed
    base_dir = Column(String(500), nullable=True) # Path to local working directory
    is_short = Column(Boolean, default=False)
    width = Column(Integer, default=1024)
    height = Column(Integer, default=1792)
    duration_seconds = Column(Float, nullable=True)
    last_error = Column(String(1000), nullable=True)
    
    # Generation Parameters Persistence
    voice = Column(String(100), nullable=True)
    style = Column(String(100), nullable=True)
    max_images_per_paragraph = Column(Integer, default=2)
    
    # YouTube SEO Persistence
    youtube_title = Column(String(100), nullable=True)
    youtube_description = Column(Text, nullable=True)
    youtube_tags = Column(String(500), nullable=True)
    
    youtube_video_id = Column(String(100), nullable=True)
    is_uploaded = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    channel = relationship("Channel", back_populates="videos")
