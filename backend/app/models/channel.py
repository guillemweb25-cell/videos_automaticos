from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.models import Base


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    youtube_handle = Column(String(255), nullable=True)  # Ej: @MiCanal
    creds_dir = Column(String(255), nullable=True)  # Carpeta en /app/youtube_creds
    image_style_prompt = Column(Text, nullable=True)  # Custom style for image generation
    negative_prompt = Column(Text, nullable=True)  # Custom negative prompt
    default_style = Column(String(100), nullable=True)  # Alias del estilo por defecto (epic, onirico, ...)
    default_workflow = Column(String(255), nullable=True)  # Workflow ComfyUI .json por defecto
    loras = Column(JSON, nullable=True)  # Lista ordenada de ids de LoRA a inyectar (registro `loras`)
    affiliate_url = Column(String(500), nullable=True)   # Link que codifica el QR de afiliado (libro del canal, etc.)
    affiliate_label = Column(String(255), nullable=True)  # Texto sobre el QR (p.ej. "Compra el libro 📖\nbit.ly/pilar-libro")
    description_header = Column(Text, nullable=True)      # Bloque fijo que se antepone a la descripción de los vídeos nuevos
    thumbnail_lora_filename = Column(String(255), nullable=True)  # LoRA SDXL de estilo SOLO para la miniatura
    thumbnail_lora_strength = Column(Float, nullable=True)        # Fuerza del LoRA de miniatura (0.4-0.7 recomendado)
    thumbnail_lora_trigger = Column(String(255), nullable=True)   # Trigger words del LoRA de miniatura (opcional)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relación con el usuario
    owner = relationship("User", back_populates="channels")
    videos = relationship("Video", back_populates="channel", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Channel(id={self.id}, name={self.name})>"

