from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
import os
import shutil
from pathlib import Path
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.channel import Channel
from app.models.user import User
from app.schemas.channel import ChannelCreate, ChannelResponse, ChannelUpdate
from app.core.deps import get_current_user

router = APIRouter(prefix="/channels", tags=["channels"])


@router.post("/", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
def create_channel(
    channel_data: ChannelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Crea un nuevo canal para el usuario actual."""
    channel = Channel(
        **channel_data.model_dump(),
        user_id=current_user.id
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


@router.get("/", response_model=List[ChannelResponse])
def get_channels(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene todos los canales del usuario actual."""
    return db.query(Channel).filter(Channel.user_id == current_user.id).all()


@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Elimina un canal."""
    channel = db.query(Channel).filter(
        Channel.id == channel_id, 
        Channel.user_id == current_user.id
    ).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    
    db.delete(channel)
    db.commit()
    return None

@router.patch("/{channel_id}", response_model=ChannelResponse)
def update_channel(
    channel_id: int,
    channel_update: ChannelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualiza un canal del usuario actual."""
    channel = db.query(Channel).filter(
        Channel.id == channel_id, 
        Channel.user_id == current_user.id
    ).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    
    update_data = channel_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(channel, key, value)
    
    db.commit()
    db.refresh(channel)
    return channel

def _get_channel_base_dir(channel: Channel, current_user: User) -> Path:
    from app.core.utils import slugify
    ch_slug = f"{channel.id:04d}-{slugify(channel.name)}"
    base = Path(f"cache/user_{current_user.id:04d}/{ch_slug}")
    return base

def _get_channel_music_dir(channel: Channel, current_user: User) -> Path:
    return _get_channel_base_dir(channel, current_user) / "music"

@router.get("/{channel_id}/music", response_model=List[str])
def get_channel_music(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    channel = db.query(Channel).filter(Channel.id == channel_id, Channel.user_id == current_user.id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
        
    music_dir = _get_channel_music_dir(channel, current_user)
    if not music_dir.exists():
        return []
    
    mp3s = []
    for f in music_dir.glob("*.mp3"):
        mp3s.append(f.name)
    return sorted(mp3s)

@router.post("/{channel_id}/music")
async def upload_channel_music(
    channel_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    channel = db.query(Channel).filter(Channel.id == channel_id, Channel.user_id == current_user.id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    
    if not file.filename.lower().endswith(".mp3"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos .mp3")
        
    music_dir = _get_channel_music_dir(channel, current_user)
    music_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = music_dir / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"ok": True, "filename": file.filename}

@router.delete("/{channel_id}/music/{filename}")
def delete_channel_music(
    channel_id: int,
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    channel = db.query(Channel).filter(Channel.id == channel_id, Channel.user_id == current_user.id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
        
    music_dir = _get_channel_music_dir(channel, current_user)
    file_path = music_dir / filename
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
        
    try:
        file_path.unlink()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{channel_id}/music/{filename}")
def download_channel_music(
    channel_id: int,
    filename: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    channel = db.query(Channel).filter(Channel.id == channel_id, Channel.user_id == current_user.id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
        
    music_dir = _get_channel_music_dir(channel, current_user)
    file_path = music_dir / filename
    
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
        
    return FileResponse(path=file_path, filename=filename, media_type="audio/mpeg")

@router.get("/{channel_id}/style-guide")
def get_style_guide_status(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    channel = db.query(Channel).filter(Channel.id == channel_id, Channel.user_id == current_user.id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    
    base_dir = _get_channel_base_dir(channel, current_user)
    file_path = base_dir / "style-guide.md"
    
    return {"exists": file_path.exists()}

@router.post("/{channel_id}/style-guide")
async def upload_style_guide(
    channel_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    channel = db.query(Channel).filter(Channel.id == channel_id, Channel.user_id == current_user.id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    
    base_dir = _get_channel_base_dir(channel, current_user)
    base_dir.mkdir(parents=True, exist_ok=True)
    file_path = base_dir / "style-guide.md"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"ok": True, "filename": "style-guide.md"}

@router.delete("/{channel_id}/style-guide")
def delete_style_guide(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    channel = db.query(Channel).filter(Channel.id == channel_id, Channel.user_id == current_user.id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
        
    base_dir = _get_channel_base_dir(channel, current_user)
    file_path = base_dir / "style-guide.md"
    
    if file_path.exists():
        try:
            file_path.unlink()
            return {"ok": True}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    return {"ok": True}
