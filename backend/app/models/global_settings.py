from sqlalchemy import Column, Integer, Boolean, DateTime
from sqlalchemy.sql import func

from app.models import Base


class GlobalSettings(Base):
    __tablename__ = "global_settings"

    id = Column(Integer, primary_key=True)
    registration_enabled = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
