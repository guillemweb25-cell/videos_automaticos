from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.channel import Channel
from app.core.deps import get_current_user
from app.services.youtube_api import YouTubeService
from app.services.youtube_dl import YouTubeDLService

router = APIRouter(prefix="/youtube", tags=["YouTube"])

@router.get("/channel/{channel_id}")
async def get_youtube_channel_info(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    channel = db.query(Channel).filter(Channel.id == channel_id, Channel.user_id == current_user.id).first()
    if not channel or not channel.creds_dir:
        raise HTTPException(status_code=404, detail="Canal no encontrado o sin credenciales configuradas")
    
    service = YouTubeService(channel.creds_dir)
    info = await service.get_channel_info()
    if not info:
        raise HTTPException(status_code=401, detail="No se pudo autenticar con YouTube. El token puede haber caducado.")
    
    return info

@router.get("/videos/{channel_id}")
async def get_youtube_videos(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    channel = db.query(Channel).filter(Channel.id == channel_id, Channel.user_id == current_user.id).first()
    if not channel or not channel.creds_dir:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    
    service = YouTubeService(channel.creds_dir)
    videos = await service.get_videos()
    # Regular videos: more than 120s
    return [v for v in videos if v["duration_seconds"] > 120]

@router.get("/shorts/{channel_id}")
async def get_youtube_shorts(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    # For YouTube API, shorts ARE videos. We can try to filter by duration or just use the same method for now.
    # A common trick is to search filtering by 'type=video' and 'videoDuration=short' (< 4 mins, but shorts are < 1 min)
    # For now let's reuse the logic but maybe in the future we use a specialized search call.
    channel = db.query(Channel).filter(Channel.id == channel_id, Channel.user_id == current_user.id).first()
    if not channel or not channel.creds_dir:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    
    service = YouTubeService(channel.creds_dir)
    videos = await service.get_videos()
    # Shorts: 120s or less
    return [v for v in videos if v["duration_seconds"] <= 120]

@router.post("/download/{channel_id}")
async def download_youtube_audio(
    channel_id: int,
    url: str = Query(..., description="URL del vídeo de YouTube"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    channel = db.query(Channel).filter(Channel.id == channel_id, Channel.user_id == current_user.id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    
    try:
        path = YouTubeDLService.download_audio(url, channel.name)
        return {"status": "success", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/downloads/{channel_id}")
async def list_channel_downloads(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    channel = db.query(Channel).filter(Channel.id == channel_id, Channel.user_id == current_user.id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    
    files = YouTubeDLService.list_downloads(channel.name)
    return files
