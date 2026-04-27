from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship

from app.models import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    openai_api_key = Column(String(255), nullable=True)
    grok_api_key = Column(String(255), nullable=True)
    leonardo_api_key = Column(String(255), nullable=True)
    assemblyai_api_key = Column(String(255), nullable=True)
    elevenlabs_api_key = Column(String(255), nullable=True)

    user = relationship("User", back_populates="settings")
