from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.channel import Channel
from app.core.deps import get_current_user
from app.services.youtube_api import YouTubeService
from app.services.youtube_dl import YouTubeDLService
from app.services.seo_engine import SEOEngine
from app.models.video import Video
from pathlib import Path
import json
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/youtube", tags=["YouTube"])

class VideoUploadRequest(BaseModel):
    title: str
    description: str
    tags: str
    privacy_status: str
    publish_at: Optional[str] = None

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

@router.get("/{video_id}/metadata")
async def get_video_metadata(
    video_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    video = db.query(Video).join(Channel).filter(Video.id == video_id, Channel.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")
        
    return {
        "title": video.youtube_title or video.title,
        "description": video.youtube_description or "",
        "tags": video.youtube_tags or "",
        "thumbnail_url": f"/videos/{video.id}/thumbnail.png"
    }

@router.post("/{video_id}/upload")
async def upload_video_to_youtube(
    video_id: int,
    req: VideoUploadRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    video = db.query(Video).join(Channel).filter(Video.id == video_id, Channel.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")
    
    channel = video.channel
    if not channel or not channel.creds_dir:
        raise HTTPException(status_code=400, detail="El canal no tiene YouTube configurado")
        
    video_path = Path(video.base_dir) / "output" / "final_video.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=400, detail="El vídeo no ha sido renderizado aún")
    
    service = YouTubeService(channel.creds_dir)
    try:
        metadata = req.dict()
        response = service.upload_video(video_path, metadata)
        youtube_id = response.get("id")
        
        if youtube_id:
            video.youtube_video_id = youtube_id
            video.is_uploaded = True
            db.commit()
        
        # Upload thumbnail if exists
        thumb_path = Path(video.base_dir) / "output" / "thumbnail.png"
        if thumb_path.exists() and youtube_id:
            try:
                service.set_thumbnail(youtube_id, thumb_path)
            except Exception as e:
                print(f"Error uploading thumbnail: {e}")
                
        return {"status": "success", "youtube_id": youtube_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{video_id}/update-metadata")
async def update_youtube_metadata(
    video_id: int,
    req: VideoUploadRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    video = db.query(Video).join(Channel).filter(Video.id == video_id, Channel.user_id == current_user.id).first()
    if not video or not video.is_uploaded or not video.youtube_video_id:
        raise HTTPException(status_code=404, detail="Vídeo no encontrado o no ha sido subido a YouTube")
    
    channel = video.channel
    if not channel or not channel.creds_dir:
        raise HTTPException(status_code=400, detail="El canal no tiene YouTube configurado")
    
    service = YouTubeService(channel.creds_dir)
    try:
        metadata = req.dict()
        service.update_video_metadata(video.youtube_video_id, metadata)
        
        # Sync local metadata in DB
        video.youtube_title = req.title
        video.youtube_description = req.description
        video.youtube_tags = req.tags
        db.commit()

        # Update thumbnail if it exists
        thumb_path = Path(video.base_dir) / "output" / "thumbnail.png"
        if thumb_path.exists():
            try:
                service.set_thumbnail(video.youtube_video_id, thumb_path)
            except Exception as e:
                print(f"Error updating thumbnail: {e}")

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{video_id}/regenerate/title")
async def regenerate_youtube_title(
    video_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    video = db.query(Video).join(Channel).filter(Video.id == video_id, Channel.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")
        
    base_dir = Path(video.base_dir)
    plan_path = base_dir / "plan.json"
    if not plan_path.exists():
        raise HTTPException(status_code=400, detail="No se encontró el plan del vídeo")
        
    plan = json.loads(plan_path.read_text())
    script_snippet = "\n".join([item.get("spoken", "") for item in plan[:5]]) # First 5 paragraphs
    
    seo = SEOEngine()
    title = seo.generate_video_title(script_snippet)
    
    # Save to DB
    video.youtube_title = title
    db.commit()
    
    # Also update JSON for backward compatibility/reference
    base_dir = Path(video.base_dir)
    seo_dir = base_dir / "seo"
    seo_dir.mkdir(parents=True, exist_ok=True)
    seo_path = seo_dir / "metadata.json"
    
    data = {}
    if seo_path.exists():
        data = json.loads(seo_path.read_text())
    data["title"] = title
    seo_path.write_text(json.dumps(data, indent=4))
    
    return {"title": title}

@router.post("/{video_id}/regenerate/description")
async def regenerate_youtube_description(
    video_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    video = db.query(Video).join(Channel).filter(Video.id == video_id, Channel.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")
        
    base_dir = Path(video.base_dir)
    plan_path = base_dir / "plan.json"
    if not plan_path.exists():
        raise HTTPException(status_code=400, detail="No se encontró el plan del vídeo")
        
    plan = json.loads(plan_path.read_text())
    script_snippet = "\n".join([item.get("spoken", "") for item in plan])
    
    seo = SEOEngine()
    description = seo.generate_description(script_snippet[:4000])
    
    # Save to DB
    video.youtube_description = description
    db.commit()
    
    # Also update JSON
    base_dir = Path(video.base_dir)
    seo_dir = base_dir / "seo"
    seo_dir.mkdir(parents=True, exist_ok=True)
    seo_path = seo_dir / "metadata.json"
    
    data = {}
    if seo_path.exists():
        data = json.loads(seo_path.read_text())
    data["description"] = description
    seo_path.write_text(json.dumps(data, indent=4))
    
    return {"description": description}

@router.post("/{video_id}/regenerate/tags")
async def regenerate_youtube_tags(
    video_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    video = db.query(Video).join(Channel).filter(Video.id == video_id, Channel.user_id == current_user.id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")
        
    base_dir = Path(video.base_dir)
    plan_path = base_dir / "plan.json"
    if not plan_path.exists():
        raise HTTPException(status_code=400, detail="No se encontró el plan del vídeo")
        
    plan = json.loads(plan_path.read_text())
    script_snippet = "\n".join([item.get("spoken", "") for item in plan])
    
    seo = SEOEngine()
    tags = seo.generate_video_questions_tags(script_snippet[:4000])
    
    # Save to DB
    video.youtube_tags = tags
    db.commit()
    
    # Also update JSON
    base_dir = Path(video.base_dir)
    seo_dir = base_dir / "seo"
    seo_dir.mkdir(parents=True, exist_ok=True)
    seo_path = seo_dir / "metadata.json"
    
    data = {}
    if seo_path.exists():
        data = json.loads(seo_path.read_text())
    data["tags"] = tags
    seo_path.write_text(json.dumps(data, indent=4))
    
    return {"tags": tags}
