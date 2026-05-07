from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, UploadFile, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
import json
import os
import json
import logging
import asyncio
import random
import math
from datetime import datetime
from typing import List, Optional
import requests

from app.database import get_db
from app.models.video import Video
from app.models.channel import Channel
from app.schemas.video import (
    VideoCreate, VideoResponse, VideoUpdate, 
    ImageGenerationRequest, RegenerateImageRequest, 
    AddImageRequest, ThumbnailGenerationRequest, ConvertToVideoRequest
)

from app.config import get_settings

from app.services.audio_engine import AudioEngine
from app.services.image_engine import ImageEngine
from app.services.rendering_engine import RenderingEngine
from app.services.seo_engine import SEOEngine
from app.services.style_service import StyleService
from app.services.elevenlabs_voices import ELEVEN_VOICES
from app.services.style_service import ALIASES
from app.core.utils import slugify

from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(dependencies=[Depends(get_current_user)])
public_router = APIRouter()

def get_user_settings_for_video(video: Video, db: Session):
    channel = db.query(Channel).filter(Channel.id == video.channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    user = db.query(User).filter(User.id == channel.user_id).first()
    if not user or not user.settings:
        raise HTTPException(status_code=400, detail="Faltan API Keys. Ve a la pantalla de Ajustes.")
    return user.settings

@router.get("/overlays")
def get_available_overlays():
    overlay_dir = Path("/app/overlay")
    if not overlay_dir.exists():
        return {"overlays": []}
    
    files = []
    for ext in ["*.mp4", "*.mov", "*.webm"]:
        for f in overlay_dir.glob(ext):
            files.append(f.name)
            
    return {"overlays": sorted(files)}

@router.get("/config")
def get_available_config():
    # TikTok voices
    tiktok_voices = [
        {"id": "es_mx_002", "name": "Español MX (Hombre)"},
        {"id": "es_002", "name": "Español (Hombre)"},
        {"id": "en_us_001", "name": "English US (Female)"},
        {"id": "en_us_006", "name": "English US (Male)"},
        {"id": "br_003", "name": "Portugués BR (Mujer)"},
    ]
    
    # ElevenLabs voices
    eleven_voices = [{"id": name, "name": name} for name in ELEVEN_VOICES.keys()]
    
    # Styles
    styles = []
    seen_names = set()
    from app.services.style_service import ALIASES, STYLES
    for alias, style_key in ALIASES.items():
        style_info = STYLES.get(style_key, {})
        display_name = style_info.get("display_name", alias.replace("_", " ").capitalize())
        if display_name not in seen_names:
            styles.append({"id": alias, "name": display_name})
            seen_names.add(display_name)
    
    # Sort styles by name
    styles.sort(key=lambda x: x["name"])


    # Leonardo Models
    leonardo_models = [
        {"id": "7b592283-e8a7-4c5a-9ba6-d18c31f258b9", "name": "Lucid Origin (Economic/Great Text)"},
        {"id": "b24e16ff-06e3-43eb-8d33-4416c2d75876", "name": "Leonardo Vision XL (Fast)"},
        {"id": "gpt-image-1.5", "name": "GPT Image-1.5 (High Quality/Expensive)"},
        {"id": "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3", "name": "Phoenix 1.0 (Best for Text)"},
        {"id": "e316348f-7773-490e-adcd-46757c738eb7", "name": "Absolute Reality v1.6"},
        {"id": "gemini-image-2", "name": "Nano Banana Pro"},
    ]
    
    # Generation Modes
    generation_modes = [
        {"id": "FAST", "name": "Modo Rápido ($0.012)", "cost": 0.012},
        {"id": "QUALITY", "name": "Modo Calidad ($0.0852)", "cost": 0.0852},
        {"id": "COMFYUI", "name": "ComfyUI (Local/Gratis)", "cost": 0.0},
    ]
    
    # Local XTTS Voices from the separate API
    local_xtts_voices = []
    try:
        settings = get_settings()
        url = getattr(settings, "LOCAL_TTS_URL", "http://192.168.1.46:8022") 
        r = requests.get(f"{url}/voices", timeout=2)
        if r.ok:
            local_xtts_voices = r.json().get("voices", [])
    except Exception as e:
        print(f"Warning: Could not fetch local_xtts voices: {e}")
                
    return {
        "voices": {
            "tiktok": tiktok_voices,
            "elevenlabs": eleven_voices,
            "local_xtts": sorted(local_xtts_voices)
        },
        "styles": styles,
        "leonardo_models": leonardo_models,
        "generation_modes": generation_modes
    }

@router.get("/workflows")
def get_available_workflows():
    workflow_dir = Path("/app/workflows")
    if not workflow_dir.exists():
        return {"workflows": []}
    
    files = []
    for f in workflow_dir.glob("*.json"):
        files.append(f.name)
            
    return {"workflows": sorted(files)}

@router.post("/", response_model=VideoResponse)
def create_video(video_in: VideoCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.config import get_settings
    settings = get_settings()

    # 2. Check channel exists
    channel = db.query(Channel).filter(Channel.id == video_in.channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # 4. Create DB record
    video = Video(**video_in.model_dump())
    db.add(video)
    db.commit()
    db.refresh(video)

    # 3. Initialize directory (Cache structure: cache/user_0001/0001-channel-name/YYYY-MM-DD-video-title)
    user_slug = f"user_{channel.user_id:04d}"
    channel_slug = f"{channel.id:04d}-{slugify(channel.name)}"
    date_str = datetime.now().strftime("%Y-%m-%d")
    video_title_slug = slugify(video.title or "untitled")
    video_slug = f"{date_str}-{video_title_slug}"
    
    base_dir = Path("cache") / user_slug / channel_slug / video_slug
    base_dir.mkdir(parents=True, exist_ok=True)
    
    (base_dir / "audio/chunks").mkdir(parents=True, exist_ok=True)
    (base_dir / "audio_seed").mkdir(parents=True, exist_ok=True)
    (base_dir / "images").mkdir(parents=True, exist_ok=True)
    (base_dir / "output").mkdir(parents=True, exist_ok=True)
    (base_dir / "seo").mkdir(parents=True, exist_ok=True)

    video.base_dir = str(base_dir)
    db.commit()
    db.refresh(video)
    
    return video

@router.patch("/{video_id}", response_model=VideoResponse)
def update_video(video_id: int, video_in: VideoUpdate, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    update_data = video_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(video, field, value)
    
    db.commit()
    db.refresh(video)
    return video

@router.get("/channel/{channel_id}", response_model=List[VideoResponse])
def get_channel_videos(channel_id: int, db: Session = Depends(get_db)):
    return db.query(Video).filter(Video.channel_id == channel_id).order_by(Video.created_at.desc()).all()

@public_router.get("/{video_id}/thumbnail.png")
def get_video_thumbnail(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    thumb_path = Path(video.base_dir) / "output" / "thumbnail.png"
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    
    return FileResponse(thumb_path)

@router.delete("/{video_id}")
def delete_video(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Optionally delete files here, but for now just DB record as per plan
    db.delete(video)
    db.commit()
    return {"ok": True}


@router.get("/orphans")
def list_orphan_videos(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns all videos belonging to the current user that have NOT been uploaded
    to YouTube, with metadata and on-disk cache size for cleanup management.
    """
    import shutil
    rows = (
        db.query(Video, Channel)
        .join(Channel, Video.channel_id == Channel.id)
        .filter(Channel.user_id == current_user.id)
        .filter(Video.is_uploaded == False)  # noqa: E712
        .order_by(Video.created_at.desc())
        .all()
    )

    out = []
    for v, ch in rows:
        size_bytes = 0
        if v.base_dir:
            base_path = Path(v.base_dir)
            if base_path.exists():
                try:
                    for f in base_path.rglob("*"):
                        if f.is_file():
                            size_bytes += f.stat().st_size
                except Exception:
                    pass
        out.append({
            "id": v.id,
            "title": v.title,
            "status": v.status,
            "last_error": v.last_error,
            "duration_seconds": v.duration_seconds,
            "is_short": v.is_short,
            "width": v.width,
            "height": v.height,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "base_dir": v.base_dir,
            "cache_size_bytes": size_bytes,
            "channel_id": ch.id,
            "channel_name": ch.name,
        })
    return out


@router.delete("/{video_id}/purge")
def purge_video(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fully removes a video: DB record + entire cache folder on disk.
    Only allowed for videos owned by the current user that are NOT uploaded to YouTube
    (to avoid accidentally losing the source files of published content).
    """
    import shutil
    video = (
        db.query(Video)
        .join(Channel, Video.channel_id == Channel.id)
        .filter(Video.id == video_id, Channel.user_id == current_user.id)
        .first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found or not owned by user")

    if video.is_uploaded:
        raise HTTPException(status_code=400, detail="Vídeo subido a YouTube. No se purga para preservar los assets de origen. Si quieres borrarlo, primero quita la marca de subido.")

    deleted_size = 0
    if video.base_dir:
        base_path = Path(video.base_dir)
        if base_path.exists():
            try:
                for f in base_path.rglob("*"):
                    if f.is_file():
                        deleted_size += f.stat().st_size
                shutil.rmtree(base_path)
            except Exception as e:
                print(f"[purge] WARNING: could not delete folder {base_path}: {e}", flush=True)

    db.delete(video)
    db.commit()
    return {"ok": True, "id": video_id, "deleted_size_bytes": deleted_size}


@router.post("/{video_id}/mark-uploaded")
def mark_video_uploaded(
    video_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually flags a video as uploaded to YouTube.

    Used when the user already uploaded by hand (or the upload finished but the
    flag was lost) and the video shouldn't appear in the orphans list anymore.
    """
    video = (
        db.query(Video)
        .join(Channel, Video.channel_id == Channel.id)
        .filter(Video.id == video_id, Channel.user_id == current_user.id)
        .first()
    )
    if not video:
        raise HTTPException(status_code=404, detail="Video not found or not owned by user")
    video.is_uploaded = True
    db.commit()
    return {"ok": True, "id": video_id}


@router.post("/bulk-purge")
def bulk_purge_videos(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk delete: takes {ids: [int, ...]}. Returns per-id status."""
    import shutil
    ids = payload.get("ids", [])
    if not isinstance(ids, list) or not ids:
        raise HTTPException(status_code=400, detail="Missing or invalid 'ids' array")

    results = []
    total_size = 0

    for vid_id in ids:
        try:
            video = (
                db.query(Video)
                .join(Channel, Video.channel_id == Channel.id)
                .filter(Video.id == vid_id, Channel.user_id == current_user.id)
                .first()
            )
            if not video:
                results.append({"id": vid_id, "ok": False, "error": "not found or not owned"})
                continue
            if video.is_uploaded:
                results.append({"id": vid_id, "ok": False, "error": "uploaded to YouTube, skipped"})
                continue

            size = 0
            if video.base_dir:
                base_path = Path(video.base_dir)
                if base_path.exists():
                    try:
                        for f in base_path.rglob("*"):
                            if f.is_file():
                                size += f.stat().st_size
                        shutil.rmtree(base_path)
                    except Exception as e:
                        print(f"[bulk-purge] WARNING: {base_path}: {e}", flush=True)
            db.delete(video)
            total_size += size
            results.append({"id": vid_id, "ok": True, "size_bytes": size})
        except Exception as e:
            results.append({"id": vid_id, "ok": False, "error": str(e)})

    db.commit()
    return {"ok": True, "results": results, "total_deleted_bytes": total_size}

@router.post("/{video_id}/script")
async def upload_script(video_id: int, request: Request, script: str = None, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Support both query parameter (short scripts) and JSON body (long scripts)
    script_text = script
    if not script_text:
        try:
            body = await request.json()
            script_text = body.get("script", "")
        except:
            pass
    
    if not script_text:
        raise HTTPException(status_code=400, detail="No script provided")
    
    base_dir = Path(video.base_dir)
    (base_dir / "script.txt").write_text(script_text, encoding="utf-8")
    
    settings = get_user_settings_for_video(video, db)
    engine = ImageEngine(
        openai_api_key=settings.openai_api_key, 
        leonardo_api_key=settings.leonardo_api_key,
        grok_api_key=settings.grok_api_key,
        provider=video.llm_provider
    )
    
    paragraphs = [p.strip() for p in script_text.split("\n\n") if p.strip()]
    (base_dir / "plan.json").write_text(json.dumps([{"idx": i+1, "spoken": p} for i, p in enumerate(paragraphs)], indent=2), encoding="utf-8")
    
    return {"ok": True, "paragraphs": len(paragraphs)}

@router.get("/{video_id}/script")
def get_script(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    script_path = Path(video.base_dir) / "script.txt"
    if not script_path.exists():
        return {"script": ""}
    
    return {"script": script_path.read_text(encoding="utf-8")}

@router.post("/{video_id}/audio")
async def generate_audio(
    video_id: int,
    voice: str = "es_mx_002",
    provider: str = "tiktok",
    db: Session = Depends(get_db)
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    base_dir = Path(video.base_dir)
    plan_path = base_dir / "plan.json"
    if not plan_path.exists():
        raise HTTPException(status_code=400, detail="Script not uploaded")

    # Pre-validate ElevenLabs key here (sync) so we fail fast before kicking off bg task
    if provider.lower() == "elevenlabs":
        settings = get_user_settings_for_video(video, db)
        if not settings or not settings.elevenlabs_api_key:
            raise HTTPException(status_code=400, detail="No has configurado tu API Key de ElevenLabs en Ajustes.")

    # Reset progress file
    progress_file = base_dir / "audio_progress.txt"
    progress_file.parent.mkdir(parents=True, exist_ok=True)
    progress_file.write_text("0")

    video.status = "generating_audio"
    video.voice = voice
    video.last_error = None
    db.commit()

    def _do_audio_sync(vid_id: int, vc: str, prov: str):
        """Runs in a thread executor so the event loop stays responsive."""
        from app.database import SessionLocal
        db_bg = SessionLocal()
        try:
            vid = db_bg.query(Video).filter(Video.id == vid_id).first()
            if not vid:
                return
            base_dir_bg = Path(vid.base_dir)
            plan = json.loads((base_dir_bg / "plan.json").read_text())
            results = []
            total_sec = 0
            total_chunks = max(1, len(plan))

            for i, item in enumerate(plan):
                idx = item["idx"]
                text = item["spoken"]
                out_path = base_dir_bg / "audio/chunks" / f"{idx:03d}.mp3"

                if not out_path.exists():
                    if prov.lower() == "elevenlabs":
                        s = get_user_settings_for_video(vid, db_bg)
                        AudioEngine.synthesize_elevenlabs(text, vc, out_path, api_key=s.elevenlabs_api_key)
                    elif prov.lower() == "local_xtts":
                        AudioEngine.synthesize_local_xtts(text, vc, out_path)
                    else:
                        AudioEngine.synthesize_tiktok(text, vc, out_path)

                dur = AudioEngine.get_duration(out_path)
                total_sec += dur
                results.append({"id": idx, "seconds": dur, "file": out_path.name})

                pct = int((i + 1) * 100 / total_chunks)
                try:
                    (base_dir_bg / "audio_progress.txt").write_text(str(pct))
                except Exception:
                    pass
                print(f"[audio] Progress: {pct}% ({i + 1}/{total_chunks})", flush=True)

            (base_dir_bg / "paragraphs_durations.json").write_text(json.dumps(results, indent=2))

            vid.duration_seconds = total_sec
            vid.status = "audio_ready"
            db_bg.commit()
        except Exception as e:
            print(f"[BG audio] FAILED for video {vid_id}: {e}", flush=True)
            import traceback
            traceback.print_exc()
            vid = db_bg.query(Video).filter(Video.id == vid_id).first()
            if vid:
                vid.status = "failed"
                vid.last_error = str(e)
                db_bg.commit()
        finally:
            db_bg.close()

    # Run the sync TTS work in a thread so the event loop keeps serving /audio-progress
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _do_audio_sync, video_id, voice, provider)

    return {"ok": True, "background": True, "status": "generating_audio"}


@router.get("/{video_id}/audio-progress")
def get_audio_progress(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    progress = 0
    if video.base_dir:
        progress_file = Path(video.base_dir) / "audio_progress.txt"
        if progress_file.exists():
            try:
                progress = int(progress_file.read_text().strip() or 0)
            except Exception:
                progress = 0

    return {
        "progress": progress,
        "status": video.status,
        "last_error": video.last_error,
    }


@router.get("/{video_id}/images-progress")
def get_images_progress(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    progress = 0
    paragraphs_done = 0
    total_paragraphs = 0
    total_images = 0
    if video.base_dir:
        base_dir = Path(video.base_dir)
        pf = base_dir / "images_progress.txt"
        if pf.exists():
            try:
                progress = int(pf.read_text().strip() or 0)
            except Exception:
                progress = 0
        # Pull rich detail from the JSON state if present
        meta_path = base_dir / "image_prompts_all.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                paragraphs_done = int(meta.get("processed_paragraphs", 0))
                total_paragraphs = int(meta.get("total_paragraphs", 0))
                total_images = int(meta.get("total_images", 0))
            except Exception:
                pass

    return {
        "progress": progress,
        "paragraphs_done": paragraphs_done,
        "total_paragraphs": total_paragraphs,
        "total_images": total_images,
        "status": video.status,
        "last_error": video.last_error,
    }

@router.post("/{video_id}/auto-advance")
async def auto_advance(video_id: int, db: Session = Depends(get_db)):
    """Reanuda un vídeo desde audio_ready hacia images_ready con defaults sensatos.

    Útil para vídeos que se quedaron a medio camino y quieres recuperarlos sin
    pasar por el formulario de creación. Solo mueve el pipeline hasta dejar las
    imágenes listas para revisión visual; nunca renderiza automáticamente.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # Already past target, nothing to do
    if video.status in ["images_ready", "generating_images", "seo", "rendering", "ready", "completed"]:
        return {"ok": True, "message": f"Ya está en {video.status}, no hace falta avanzar."}

    if video.status != "audio_ready":
        raise HTTPException(
            status_code=400,
            detail=f"No puedo auto-avanzar desde '{video.status}'. Necesita estar en audio_ready (audio generado).",
        )

    # Read channel defaults to fill in style/workflow when not stored on the video
    channel = db.query(Channel).filter(Channel.id == video.channel_id).first()
    default_style = (channel.default_style if channel else None) or "stock_photo"
    default_workflow = channel.default_workflow if channel else None

    req = ImageGenerationRequest(
        style_name=video.style or default_style,
        max_images_per_paragraph=video.max_images_per_paragraph if video.max_images_per_paragraph is not None else 0,
        model_id="gpt-image-1.5",
        generation_mode="COMFYUI",
        workflow_name=default_workflow,
    )

    return await generate_images(video_id, req, db)


@router.post("/{video_id}/reset-images")
async def reset_images(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    # Reset status
    if video.status in ["images_ready", "seo", "rendering", "ready", "completed", "error", "failed"]:
        video.status = "audio_ready"
        video.last_error = None
        db.commit()
        
    # Delete image prompts cache and existing images
    import shutil
    base_dir = Path(video.base_dir)
    images_dir = base_dir / "images"
    prompts_cache = base_dir / "image_prompts_all.json"
    
    if prompts_cache.exists():
        prompts_cache.unlink()
        
    if images_dir.exists():
        for f in images_dir.glob("*.png"):
            f.unlink()
            
    return {"ok": True, "message": "Imágenes borradas. Estado reiniciado a audio_ready."}


@router.post("/{video_id}/paragraphs/{paragraph_id}/regenerate")
async def regenerate_paragraph(video_id: int, paragraph_id: int, db: Session = Depends(get_db)):
    """Regenerates prompts AND images for a single paragraph.

    Drops paragraph N from `image_prompts_all.json`, deletes its `p{N:03d}_*.png`
    files, and reuses the standard image-generation flow. The per-paragraph cache
    inside that flow short-circuits every other paragraph (cached prompts + image
    file already on disk), so only the deleted paragraph actually goes through the
    LLM and SDXL again.
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    base_dir = Path(video.base_dir)
    prompts_path = base_dir / "image_prompts_all.json"
    if not prompts_path.exists():
        raise HTTPException(
            status_code=400,
            detail="No previous generation found. Run full image generation first.",
        )

    data = json.loads(prompts_path.read_text())
    items = data.get("items", [])
    target = next((it for it in items if it.get("paragraph_id") == paragraph_id), None)
    if not target:
        raise HTTPException(
            status_code=404,
            detail=f"Paragraph {paragraph_id} not found in image_prompts_all.json",
        )

    n_imgs = len(target.get("prompts", []))

    # Delete the paragraph's image files on disk so the generation flow regenerates them.
    images_dir = base_dir / "images"
    if images_dir.exists():
        for f in images_dir.glob(f"p{paragraph_id:03d}_*.png"):
            f.unlink()

    # Drop paragraph N from items + adjust counters so the flow regenerates fresh prompts.
    data["items"] = [it for it in items if it.get("paragraph_id") != paragraph_id]
    data["processed_paragraphs"] = max(0, int(data.get("processed_paragraphs", 0)) - 1)
    data["total_images"] = max(0, int(data.get("total_images", 0)) - n_imgs)
    prompts_path.write_text(json.dumps(data, indent=2))

    # Reuse the same params the original full generation used; the standard /images flow
    # iterates over all paragraphs but its cache logic skips everything that still has
    # both a cached prompt and an image file on disk.
    channel = db.query(Channel).filter(Channel.id == video.channel_id).first()
    default_workflow = channel.default_workflow if channel else None
    req = ImageGenerationRequest(
        style_name=data.get("style") or video.style or (
            (channel.default_style if channel else None) or "stock_photo"
        ),
        max_images_per_paragraph=int(
            data.get("max_images_per_paragraph",
                     video.max_images_per_paragraph if video.max_images_per_paragraph is not None else 0)
        ),
        model_id=data.get("model_id") or "gpt-image-1.5",
        generation_mode=data.get("generation_mode") or "COMFYUI",
        workflow_name=data.get("workflow_name") or default_workflow,
    )

    result = await generate_images(video_id, req, db)
    return {
        "ok": True,
        "paragraph_id": paragraph_id,
        "deleted_images": n_imgs,
        "background": result.get("background", True),
    }


@router.post("/{video_id}/images")
async def generate_images(video_id: int, req: ImageGenerationRequest, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video.status = "generating_images"
    video.style = req.style_name
    video.max_images_per_paragraph = req.max_images_per_paragraph
    video.last_error = None
    db.commit()

    # Reset progress file
    if video.base_dir:
        try:
            progress_file = Path(video.base_dir) / "images_progress.txt"
            progress_file.parent.mkdir(parents=True, exist_ok=True)
            progress_file.write_text("0")
        except Exception:
            pass

    settings = get_user_settings_for_video(video, db)

    # Extract keys to pass to thread
    openai_key = settings.openai_api_key
    grok_key = settings.grok_api_key
    leonardo_key = settings.leonardo_api_key
    assemblyai_key = settings.assemblyai_api_key
    llm_p = video.llm_provider
    wf_name = req.workflow_name # New field

    # Run image generation in background thread to avoid proxy timeouts
    import threading
    from app.database import SessionLocal

    async def _generate_images_background(vid_id, sty, max_imgs, m_id, gen_mode, openai_k, leonardo_k, grok_k, llm_prov, wf_n, assemblyai_k):

        db_bg = SessionLocal()
        try:
            vid = db_bg.query(Video).filter(Video.id == vid_id).first()
            if not vid:
                return
            
            base_dir = Path(vid.base_dir)
            plan_path = base_dir / "plan.json"
            if not plan_path.exists():
                vid.status = "failed"
                vid.last_error = "Script not uploaded"
                db_bg.commit()
                return
            
            durations_path = base_dir / "paragraphs_durations.json"
            durations = []
            if durations_path.exists():
                durations = json.loads(durations_path.read_text())
            dur_map = {d["id"]: d["seconds"] for d in durations}
            file_map = {d["id"]: d.get("file") for d in durations}

            plan = json.loads(plan_path.read_text())
            engine = ImageEngine(openai_api_key=openai_k, leonardo_api_key=leonardo_k, grok_api_key=grok_k, provider=llm_prov)
            seo = SEOEngine(api_key=(grok_k if llm_prov == "grok" else openai_k), provider=llm_prov)

            # Word-level transcription per paragraph (lazy, cached on disk).
            # Used to slice the exact phrase being spoken at each image's time window
            # so prompts visualize what the audio is saying at that moment instead of
            # N variations of the whole paragraph.
            from app.services.subtitle_engine import SubtitleEngine
            from app.services.phrase_slicer import get_or_create_paragraph_words, slice_phrase_for_image
            subtitle_engine = SubtitleEngine(api_key=assemblyai_k) if assemblyai_k else None
            transcripts_dir = base_dir / "transcripts"
            audio_chunks_dir = base_dir / "audio" / "chunks"
            
            # Load channel for custom style
            channel = db_bg.query(Channel).filter(Channel.id == vid.channel_id).first()
            
            seconds_per_image = 10.0
            all_prompts_data = {
                "video_id": vid_id,
                "style": sty,
                "workflow_name": wf_n, # Store workflow name in metadata
                "model": "gpt-4o-mini",
                "seconds_per_image": seconds_per_image,
                "max_images_per_paragraph": max_imgs,
                "total_paragraphs": len(plan),
                "processed_paragraphs": 0,
                "total_images": 0,
                "items": [],
                "generation_mode": gen_mode,
                "model_id": m_id
            }

            # Caching: Load existing prompts if possible
            existing_prompts_all = {}
            all_prompts_all_path = base_dir / "image_prompts_all.json"
            if all_prompts_all_path.exists():
                try:
                    old_data = json.loads(all_prompts_all_path.read_text())
                    # Only reuse if style, max_images AND workflow match
                    if old_data.get("style") == sty and \
                       old_data.get("max_images_per_paragraph") == max_imgs and \
                       old_data.get("workflow_name") == wf_n and \
                       old_data.get("model_id") == m_id:
                        for item in old_data.get("items", []):
                            existing_prompts_all[item["paragraph_id"]] = {
                                "prompts": item["prompts"],
                                "spoken": item.get("spoken", "")
                            }
                except:
                    pass

            script_full = "\n".join([item.get("spoken", "") for item in plan])
            total_images = 0
            recent_prompts = []
            
            # Fetch custom niche rules from style-guide.md
            custom_niche_rules = StyleService.get_custom_niche_rules(base_dir)
            
            for item in plan:
                idx = item["idx"]
                text = item["spoken"]
                duration = dur_map.get(idx, 0)
                
                if duration < seconds_per_image:
                    images_count = 1
                elif max_imgs == 0:
                    # Dynamic mode: 1 image per 10s (approx)
                    # 15s -> 2, 25s -> 3, etc.
                    import math
                    images_count = math.ceil(duration / seconds_per_image)
                    # Hard cap at 10 images per paragraph to avoid API abuse/timeouts
                    images_count = min(10, images_count)
                else:
                    import math
                    images_count = min(max_imgs, math.ceil(duration / seconds_per_image))
                
                # 1. Word-level transcription for this paragraph (lazy, cached).
                # Falls back gracefully to None if AssemblyAI key missing or transcription
                # fails — in that case we use the legacy paragraph-based prompt.
                words = []
                if subtitle_engine and file_map.get(idx):
                    para_audio = audio_chunks_dir / file_map[idx]
                    transcript_cache = transcripts_dir / f"p{idx:03d}.json"
                    if para_audio.exists():
                        try:
                            words = await asyncio.to_thread(
                                get_or_create_paragraph_words,
                                para_audio, transcript_cache, subtitle_engine,
                            )
                        except Exception as e:
                            print(f"[images] WARN: failed to transcribe paragraph {idx}: {e}", flush=True)
                            words = []

                # Cached prompts from a previous run with same params: reuse only if
                # everything matches — count, spoken text, and (if we have phrases now)
                # the per-image phrase too.
                cached = existing_prompts_all.get(idx)
                cached_by_id = {p["id"]: p for p in cached["prompts"]} if cached else {}
                can_reuse_paragraph = bool(
                    cached and cached["spoken"] == text and len(cached["prompts"]) == images_count
                )

                channel_style = StyleService.get_channel_style(channel, sty)
                style = channel_style
                neg = style.get("negative_prompt")

                paragraph_item = {
                    "paragraph_id": idx,
                    "seconds": duration,
                    "spoken": text,
                    "images_count": images_count,
                    "seconds_per_image": duration / images_count if images_count else 0,
                    "prompts": []
                }

                # 2. One iteration per image: slice phrase → generate prompt → generate image.
                for i in range(images_count):
                    img_idx = i + 1

                    # Slice the spoken phrase covering this image's time window.
                    phrase, t_start, t_end = ("", 0.0, 0.0)
                    if words:
                        phrase, t_start, t_end = slice_phrase_for_image(words, img_idx, images_count, duration)
                    else:
                        # No transcript available: even in fallback we record the time window
                        # so the JSON shape is consistent and the reviewer can show it.
                        if images_count > 0 and duration > 0:
                            window = duration / images_count
                            t_start = i * window
                            t_end = (i + 1) * window

                    # Decide whether we can reuse a previously generated prompt for this slot.
                    cached_p = cached_by_id.get(img_idx) if can_reuse_paragraph else None
                    reuse_prompt = bool(cached_p and cached_p.get("phrase") == phrase) or (
                        cached_p is not None and not phrase
                    )
                    if reuse_prompt:
                        p_text = cached_p["prompt"]
                    else:
                        prompts = await asyncio.to_thread(
                            engine.generate_prompts,
                            text, sty,
                            n=1,
                            full_context=script_full,
                            style_override=channel_style,
                            recent_history=recent_prompts[-8:],
                            custom_rules=custom_niche_rules,
                            phrase=phrase or None,
                        )
                        if not prompts:
                            continue
                        p_text = prompts[0]
                    recent_prompts.append(p_text)

                    out_path = base_dir / "images" / f"p{idx:03d}_{img_idx:02d}.png"
                    cost_info = None
                    seed_val = None

                    if not out_path.exists():
                        init_image_id = None
                        if i > 0:
                            prev_img_path = base_dir / "images" / f"p{idx:03d}_{i:02d}.png"
                            if prev_img_path.exists():
                                try:
                                    init_image_id = await asyncio.to_thread(engine.upload_init_image, prev_img_path)
                                except Exception as e:
                                    print(f"Warning: Failed to upload reference image for paragraph {idx} image {img_idx}: {e}")

                        if gen_mode.upper() == "COMFYUI":
                            current_wf = wf_n or (channel.default_workflow if channel else None)
                            if not current_wf:
                                if "ultra" in sty.lower():
                                    current_wf = "Cinematic-Horror-Ultra.json"
                                elif "cinematico" in sty.lower() or "realismo" in sty.lower():
                                    current_wf = "Cinematic-Horror.json"
                                elif "onirico" in sty.lower() or "suenos" in sty.lower():
                                    current_wf = "Dreamy-Oniric.json"
                                else:
                                    current_wf = "Comic-Horror.json"

                            result = await engine.generate_comfy_image(
                                p_text, out_path,
                                size=f"{vid.width}x{vid.height}",
                                negative_prompt=neg,
                                workflow_name=current_wf,
                            )
                            cost_info = result
                        else:
                            cost_info = await engine.generate_leonardo_image(
                                p_text, out_path, size=f"{vid.width}x{vid.height}",
                                negative_prompt=neg, init_image_id=init_image_id, model_id=m_id, mode=gen_mode,
                            )
                    else:
                        # Image exists on disk. Preserve cost/seed metadata if we had it.
                        if cached_p:
                            cost_info = cached_p.get("cost")
                            seed_val = cached_p.get("seed")

                    p_info_entry = {
                        "id": img_idx,
                        "prompt": p_text,
                        "phrase": phrase,
                        "time_start": round(t_start, 3),
                        "time_end": round(t_end, 3),
                    }
                    if cost_info and isinstance(cost_info, dict):
                        if "amount" in cost_info:
                            p_info_entry["cost"] = cost_info
                        if "seed" in cost_info:
                            p_info_entry["seed"] = cost_info["seed"]
                    if seed_val is not None and "seed" not in p_info_entry:
                        p_info_entry["seed"] = seed_val

                    paragraph_item["prompts"].append(p_info_entry)
                    total_images += 1
                
                all_prompts_data["items"].append(paragraph_item)
                all_prompts_data["processed_paragraphs"] += 1
                # Save progress after each paragraph
                all_prompts_data["total_images"] = total_images
                all_prompts_all_path.write_text(json.dumps(all_prompts_data, indent=2))

                # Write progress file (paragraph-level progress)
                images_pct = int(all_prompts_data["processed_paragraphs"] * 100 / max(1, all_prompts_data["total_paragraphs"]))
                try:
                    (base_dir / "images_progress.txt").write_text(str(images_pct))
                except Exception:
                    pass
                print(f"[images] Progress: {images_pct}% ({all_prompts_data['processed_paragraphs']}/{all_prompts_data['total_paragraphs']} párrafos, {total_images} imágenes)", flush=True)
            
            all_prompts_data["total_images"] = total_images
            all_prompts_all_path.write_text(json.dumps(all_prompts_data, indent=2))
            
            # 3. Generate Thumbnail with Hook
            thumbnail_path = base_dir / "output" / "thumbnail.png"
            if not thumbnail_path.exists():
                try:
                    seo = SEOEngine(api_key=(grok_k if llm_prov == "grok" else openai_k), provider=llm_prov)
                    script_snippet = "\n".join([item.get("spoken", "") for item in plan])
                    # NEW: use custom rules from guide for hook
                    custom_title_rules = StyleService.get_custom_title_rules(base_dir)
                    hook = await asyncio.to_thread(seo.generate_thumbnail_hook, script_full, custom_rules=custom_title_rules)

                    # Look for custom thumbnail rules in style-guide.md
                    custom_thumb_rules = StyleService.get_custom_thumbnail_rules(base_dir)
                    visual_prompt = await asyncio.to_thread(
                        seo.generate_thumbnail_visual_prompt,
                        script_full, sty,
                        thumbnail_hook=hook,
                        custom_rules=custom_thumb_rules,
                    )
                    
                    if "thumbnail" not in all_prompts_data:
                        all_prompts_data["thumbnail"] = {}
                    all_prompts_data["thumbnail"]["hook"] = hook
                    all_prompts_data["thumbnail"]["visual_prompt"] = visual_prompt
                    
                    await engine.generate_thumbnail(
                        hook, visual_prompt, thumbnail_path,
                        size=f"{vid.width}x{vid.height}",
                        channel_name=channel.name,
                        workflow_name=getattr(vid, "workflow_name", None) or wf_n
                    )
                except Exception as e:
                    import traceback
                    print(f"[thumbnail] FAILED for video {vid.id} ({vid.width}x{vid.height}): {e}", flush=True)
                    traceback.print_exc()

            vid.status = "images_ready"
            db_bg.commit()
            print(f"[BG] Image generation complete for video {vid_id}. Total images: {total_images}")
        except Exception as e:
            print(f"[BG] Image generation FAILED for video {vid_id}: {e}")
            vid = db_bg.query(Video).filter(Video.id == vid_id).first()
            if vid:
                vid.status = "failed"
                vid.last_error = str(e)
                db_bg.commit()
        finally:
            db_bg.close()
    
    # Use asyncio.create_task instead of threading.Thread for async background task
    asyncio.create_task(_generate_images_background(video_id, req.style_name, req.max_images_per_paragraph, req.model_id, req.generation_mode, openai_key, leonardo_key, grok_key, llm_p, wf_name, assemblyai_key))
    
    return {"ok": True, "background": True, "count": 0}

@router.get("/{video_id}/status")
def get_video_status(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"status": video.status, "last_error": video.last_error}

@router.get("/{video_id}/images_data")
def get_images_data(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    base_dir = Path(video.base_dir)
    images_json = base_dir / "image_prompts_all.json"
    if not images_json.exists():
        return {"items": []}
    
    data = json.loads(images_json.read_text())
    
    # Add metadata from database
    data["width"] = video.width
    data["height"] = video.height
    data["orientation"] = "horizontal" if video.width > video.height else "vertical"
    data["is_short"] = video.is_short

    # Add relative path for frontend access via /cache.
    # Self-heal: si el JSON dice is_video=true pero el .mp4 ya no existe en disco
    # (el usuario lo borró), volvemos a apuntar al .png si existe y reseteamos el flag.
    images_dir = base_dir / "images"
    json_changed = False
    for item in data.get("items", []):
        p_idx = item["paragraph_id"]
        item["audio_url"] = f"/{video.base_dir}/audio/chunks/{p_idx:03d}.mp3"
        for p_info in item.get("prompts", []):
            img_idx = p_info["id"]
            mp4_path = images_dir / f"p{p_idx:03d}_{img_idx:02d}.mp4"
            png_path = images_dir / f"p{p_idx:03d}_{img_idx:02d}.png"

            if p_info.get("is_video"):
                if mp4_path.exists():
                    p_info["url"] = f"/{video.base_dir}/images/{mp4_path.name}"
                else:
                    # mp4 missing → fall back to png and unset video flag
                    p_info["is_video"] = False
                    p_info.pop("video_model", None)
                    json_changed = True
                    p_info["url"] = f"/{video.base_dir}/images/{png_path.name}"
            else:
                p_info["url"] = f"/{video.base_dir}/images/{png_path.name}"

    if json_changed:
        try:
            images_json.write_text(json.dumps(data, indent=2))
        except Exception:
            pass
    
    # Add thumbnail info if exists
    thumb_path = base_dir / "output" / "thumbnail.png"
    if thumb_path.exists():
        data["thumbnail_url"] = f"/{video.base_dir}/output/thumbnail.png?t={int(datetime.now().timestamp())}"
    
    # Ensure thumbnail info exists in data
    if "thumbnail" not in data:
        data["thumbnail"] = {"hook": "", "visual_prompt": ""}
    
    return data

@router.post("/{video_id}/regenerate-image")
async def regenerate_image(
    video_id: int, 
    req: RegenerateImageRequest,
    db: Session = Depends(get_db)
):
    paragraph_id = req.paragraph_id
    image_id = req.image_id
    custom_prompt = req.custom_prompt
    model_id = req.model_id
    generation_mode = req.generation_mode
    workflow_name = req.workflow_name

    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    base_dir = Path(video.base_dir)
    images_json = base_dir / "image_prompts_all.json"
    if not images_json.exists():
        raise HTTPException(status_code=400, detail="Images not yet generated")
    
    data = json.loads(images_json.read_text())
    found = False
    target_prompt = ""
    
    for item in data.get("items", []):
        if item["paragraph_id"] == paragraph_id:
            for p_info in item.get("prompts", []):
                if p_info["id"] == image_id:
                    if custom_prompt:
                        p_info["prompt"] = custom_prompt
                    target_prompt = p_info["prompt"]
                    found = True
                    break
        if found: break
    
    if not found:
        raise HTTPException(status_code=404, detail="Image info not found in json")

    # Update json if prompt or settings changed
    changed = False
    if custom_prompt:
        changed = True
    if generation_mode and generation_mode != data.get("generation_mode"):
        data["generation_mode"] = generation_mode
        changed = True
    if workflow_name and workflow_name != data.get("workflow_name"):
        data["workflow_name"] = workflow_name
        changed = True
    if model_id and model_id != data.get("model_id"):
        data["model_id"] = model_id
        changed = True

    if changed:
        images_json.write_text(json.dumps(data, indent=2))

    # Delete old image so Leonardo generates a new one (or just overwrite it)
    out_path = base_dir / "images" / f"p{paragraph_id:03d}_{image_id:02d}.png"
    if out_path.exists():
        out_path.unlink()
    
    settings = get_user_settings_for_video(video, db)
    engine = ImageEngine(
        openai_api_key=settings.openai_api_key, 
        leonardo_api_key=settings.leonardo_api_key,
        grok_api_key=settings.grok_api_key,
        provider=video.llm_provider
    )
    style_name = data.get("style", "stocksenior")
    # New: get workflow from request or json
    wf_name = req.workflow_name or data.get("workflow_name")
    
    channel = db.query(Channel).filter(Channel.id == video.channel_id).first()
    style = StyleService.get_channel_style(channel, style_name)
    neg = style.get("negative_prompt")
    
    # Check if a specific model was requested (passed as a query param or from somewhere)
    # For now, we'll allow an optional model_id in the regenerate call too if we want
    if generation_mode.upper() == "COMFYUI":
        if not wf_name:
            if "ultra" in style_name.lower():
                wf_name = "Cinematic-Horror-Ultra.json"
            elif "cinematico" in style_name.lower() or "realismo" in style_name.lower():
                wf_name = "Cinematic-Horror.json"
            elif "onirico" in style_name.lower() or "suenos" in style_name.lower():
                wf_name = "Dreamy-Oniric.json"
            else:
                wf_name = "Comic-Horror.json"

        result = await engine.generate_comfy_image(target_prompt, out_path, size=f"{video.width}x{video.height}", negative_prompt=neg, workflow_name=wf_name, seed=req.seed)
        cost_info = result
    else:
        cost_info = await engine.generate_leonardo_image(target_prompt, out_path, size=f"{video.width}x{video.height}", negative_prompt=neg, model_id=model_id, mode=generation_mode)
    
    # Update cost and seed in JSON
    for item in data.get("items", []):
        if item["paragraph_id"] == paragraph_id:
            for p_info in item.get("prompts", []):
                if p_info["id"] == image_id:
                    if cost_info:
                        if "amount" in cost_info: p_info["cost"] = cost_info
                        if "seed" in cost_info: p_info["seed"] = cost_info["seed"]
                    break
    
    # Save JSON with prompt and cost update
    images_json.write_text(json.dumps(data, indent=2))
    
    return {
        "ok": True, 
        "url": f"/{video.base_dir}/images/{out_path.name}?t={int(datetime.now().timestamp())}",
        "seed": cost_info.get("seed") if cost_info else None
    }

@router.post("/{video_id}/add-image")
async def add_image(video_id: int, req: AddImageRequest, db: Session = Depends(get_db)):
    paragraph_id = req.paragraph_id
    style_name = req.style_name
    model_id = req.model_id
    generation_mode = req.generation_mode
    workflow_name = req.workflow_name

    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    base_dir = Path(video.base_dir)
    images_json = base_dir / "image_prompts_all.json"
    if not images_json.exists():
        raise HTTPException(status_code=400, detail="Images not yet generated")
    
    data = json.loads(images_json.read_text())
    target_para = None
    for item in data.get("items", []):
        if item["paragraph_id"] == paragraph_id:
            target_para = item
            break
    
    if not target_para:
        raise HTTPException(status_code=404, detail="Paragraph not found in JSON")

    # Update metadata if settings changed
    changed = False
    if generation_mode and generation_mode != data.get("generation_mode"):
        data["generation_mode"] = generation_mode
        changed = True
    if workflow_name and workflow_name != data.get("workflow_name"):
        data["workflow_name"] = workflow_name
        changed = True
    if model_id and model_id != data.get("model_id"):
        data["model_id"] = model_id
        changed = True
    if changed:
        images_json.write_text(json.dumps(data, indent=2))

    # 1. Get reference image and prompt
    last_p = target_para["prompts"][-1]
    last_img_id = last_p["id"]
    last_prompt = last_p["prompt"]
    last_img_path = base_dir / "images" / f"p{paragraph_id:03d}_{last_img_id:02d}.png"

    # 2. Logic for continuity
    settings = get_user_settings_for_video(video, db)
    engine = ImageEngine(
        openai_api_key=settings.openai_api_key,
        leonardo_api_key=settings.leonardo_api_key,
        grok_api_key=settings.grok_api_key,
        provider=video.llm_provider
    )
    init_image_id = None
    if last_img_path.exists():
        try:
            init_image_id = engine.upload_init_image(last_img_path)
        except Exception as e:
            print(f"Warning: Failed to upload init image for guidance: {e}")

    # Use style_name if provided, else fall back to JSON
    effective_style = style_name or data.get("style", "stocksenior")
    channel = db.query(Channel).filter(Channel.id == video.channel_id).first()
    channel_style = StyleService.get_channel_style(channel, effective_style)

    # NEW: Load custom niche rules for continuity
    custom_niche_rules = StyleService.get_custom_niche_rules(base_dir)

    # Phrase-targeted prompt: load (or build) word-level transcript for this
    # paragraph, then slice the phrase covering this image's new time window
    # (the paragraph is now split into N+1 windows after adding this image).
    new_img_id = last_img_id + 1
    new_total = len(target_para["prompts"]) + 1
    image_phrase = None
    new_t_start = 0.0
    new_t_end = 0.0
    try:
        from app.services.subtitle_engine import SubtitleEngine
        from app.services.phrase_slicer import get_or_create_paragraph_words, slice_phrase_for_image
        # find audio chunk
        durations_path = base_dir / "paragraphs_durations.json"
        para_audio = None
        if durations_path.exists():
            for d in json.loads(durations_path.read_text()):
                if d["id"] == paragraph_id:
                    para_audio = base_dir / "audio" / "chunks" / d.get("file", "")
                    break
        if settings.assemblyai_api_key and para_audio and para_audio.exists():
            sub_engine = SubtitleEngine(api_key=settings.assemblyai_api_key)
            transcript_cache = base_dir / "transcripts" / f"p{paragraph_id:03d}.json"
            words = get_or_create_paragraph_words(para_audio, transcript_cache, sub_engine)
            image_phrase, new_t_start, new_t_end = slice_phrase_for_image(
                words, new_img_id, new_total, target_para.get("seconds", 0.0)
            )
    except Exception as e:
        print(f"[add_image] WARN: could not compute phrase for p{paragraph_id} img{new_img_id}: {e}", flush=True)

    if image_phrase:
        # Phrase-targeted: produce a prompt that depicts what is being said
        # at this exact slice of audio. Visual continuity comes from init_image_id.
        script_full_for_ctx = target_para.get("spoken", "")
        try:
            plan_for_ctx_path = base_dir / "plan.json"
            if plan_for_ctx_path.exists():
                plan_for_ctx = json.loads(plan_for_ctx_path.read_text())
                script_full_for_ctx = "\n".join(it.get("spoken", "") for it in plan_for_ctx)
        except Exception:
            pass
        prompts = engine.generate_prompts(
            target_para["spoken"], effective_style,
            n=1,
            full_context=script_full_for_ctx,
            style_override=channel_style,
            custom_rules=custom_niche_rules,
            phrase=image_phrase,
        )
        new_prompt = prompts[0] if prompts else last_prompt
    else:
        new_prompt = engine.generate_continuation_prompt(
            target_para["spoken"],
            last_prompt,
            effective_style,
            style_override=channel_style,
            custom_rules=custom_niche_rules,
        )
    
    # NEW: get workflow from request or json
    wf_name = req.workflow_name or data.get("workflow_name")
    
    # 3. Generate New Image
    out_path = base_dir / "images" / f"p{paragraph_id:03d}_{new_img_id:02d}.png"
    
    style = StyleService.get_channel_style(channel, effective_style)
    neg = style.get("negative_prompt")
    
    if generation_mode.upper() == "COMFYUI":
        if not wf_name:
            if "ultra" in style_name.lower():
                wf_name = "Cinematic-Horror-Ultra.json"
            elif "cinematico" in style_name.lower() or "realismo" in style_name.lower():
                wf_name = "Cinematic-Horror.json"
            elif "onirico" in style_name.lower() or "suenos" in style_name.lower():
                wf_name = "Dreamy-Oniric.json"
            else:
                wf_name = "Comic-Horror.json"

        cost_info = await engine.generate_comfy_image(new_prompt, out_path, size=f"{video.width}x{video.height}", negative_prompt=neg, workflow_name=wf_name)
    else:
        cost_info = await engine.generate_leonardo_image(new_prompt, out_path, size=f"{video.width}x{video.height}", negative_prompt=neg, init_image_id=init_image_id, model_id=model_id, mode=generation_mode)

    # 4. Update JSON
    new_entry = {
        "id": new_img_id,
        "prompt": new_prompt,
        "url": f"/{video.base_dir}/images/p{paragraph_id:03d}_{new_img_id:02d}.png",
        "phrase": image_phrase or "",
        "time_start": round(new_t_start, 3),
        "time_end": round(new_t_end, 3),
    }
    if cost_info:
        new_entry["cost"] = cost_info

    target_para["prompts"].append(new_entry)
    target_para["images_count"] = len(target_para["prompts"])
    target_para["seconds_per_image"] = target_para["seconds"] / target_para["images_count"]
    data["total_images"] += 1

    # 5. Re-distribute phrases across all images now that N changed.
    # The actual image files don't change; only their metadata (phrase, time_start,
    # time_end) gets refreshed so a future regenerate-prompt uses the right slice.
    try:
        if settings.assemblyai_api_key:
            from app.services.subtitle_engine import SubtitleEngine
            from app.services.phrase_slicer import get_or_create_paragraph_words, slice_phrase_for_image
            durations_path = base_dir / "paragraphs_durations.json"
            para_audio = None
            if durations_path.exists():
                for d in json.loads(durations_path.read_text()):
                    if d["id"] == paragraph_id:
                        para_audio = base_dir / "audio" / "chunks" / d.get("file", "")
                        break
            if para_audio and para_audio.exists():
                sub_engine = SubtitleEngine(api_key=settings.assemblyai_api_key)
                transcript_cache = base_dir / "transcripts" / f"p{paragraph_id:03d}.json"
                words = get_or_create_paragraph_words(para_audio, transcript_cache, sub_engine)
                total_now = len(target_para["prompts"])
                duration_now = target_para.get("seconds", 0.0)
                for entry in target_para["prompts"]:
                    ph, ts, te = slice_phrase_for_image(words, entry["id"], total_now, duration_now)
                    entry["phrase"] = ph
                    entry["time_start"] = round(ts, 3)
                    entry["time_end"] = round(te, 3)
    except Exception as e:
        print(f"[add_image] WARN: could not re-distribute phrases for p{paragraph_id}: {e}", flush=True)

    images_json.write_text(json.dumps(data, indent=2))

    return {"ok": True, "image": target_para["prompts"][-1]}

@router.post("/{video_id}/auto-fill-images/{paragraph_id}")
async def auto_fill_images(
    video_id: int,
    paragraph_id: int,
    style_name: Optional[str] = None,
    workflow_name: Optional[str] = None,
    model_id: Optional[str] = None,
    generation_mode: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Generates images one by one in this paragraph until reaching the target
    count derived from its duration (1 image per ~10s, capped at 10).
    Useful when the LLM produced fewer images than the audio length deserves.
    """
    import math

    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    base_dir = Path(video.base_dir)
    images_json = base_dir / "image_prompts_all.json"
    if not images_json.exists():
        raise HTTPException(status_code=400, detail="Images not yet generated")

    data = json.loads(images_json.read_text())
    target_para = None
    for item in data.get("items", []):
        if item["paragraph_id"] == paragraph_id:
            target_para = item
            break
    if not target_para:
        raise HTTPException(status_code=404, detail="Paragraph not found in JSON")

    duration = float(target_para.get("seconds") or 0.0)
    seconds_per_image = 10.0
    target_count = max(1, min(10, math.ceil(duration / seconds_per_image))) if duration > 0 else 1
    current_count = len(target_para.get("prompts", []))
    to_add = max(0, target_count - current_count)
    if to_add == 0:
        return {"ok": True, "added": 0, "current": current_count, "target": target_count, "message": "Ya tiene el número óptimo de imágenes."}

    added = []
    for _ in range(to_add):
        req = AddImageRequest(
            paragraph_id=paragraph_id,
            style_name=style_name,
            model_id=model_id,
            generation_mode=generation_mode or data.get("generation_mode") or "COMFYUI",
            workflow_name=workflow_name,
        )
        try:
            result = await add_image(video_id, req, db)
            added.append(result.get("image"))
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Falló al añadir imagen {len(added)+1}/{to_add}: {e}")

    return {"ok": True, "added": len(added), "current": current_count + len(added), "target": target_count, "images": added}


@router.delete("/{video_id}/remove-image")
async def remove_image(video_id: int, paragraph_id: int, image_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    base_dir = Path(video.base_dir)
    images_json = base_dir / "image_prompts_all.json"
    if not images_json.exists():
        raise HTTPException(status_code=400, detail="Images not yet generated")
    
    data = json.loads(images_json.read_text())
    target_para = None
    for item in data.get("items", []):
        if item["paragraph_id"] == paragraph_id:
            target_para = item
            break
    
    if not target_para:
        raise HTTPException(status_code=404, detail="Paragraph not found in JSON")
    
    if len(target_para["prompts"]) <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove the last image of a paragraph")

    # 1. Remove from JSON
    target_para["prompts"] = [p for p in target_para["prompts"] if p["id"] != image_id]
    
    # 2. Resequence Files and IDs
    import shutil
    old_images = sorted(list((base_dir / "images").glob(f"p{paragraph_id:03d}_*.png")))
    
    # Delete the target file
    target_file = base_dir / "images" / f"p{paragraph_id:03d}_{image_id:02d}.png"
    if target_file.exists():
        target_file.unlink()

    # Re-list and rename remaining
    remaining_files = sorted(list((base_dir / "images").glob(f"p{paragraph_id:03d}_*.png")))
    new_prompts = []
    for i, f_path in enumerate(remaining_files):
        new_id = i + 1
        new_name = f"p{paragraph_id:03d}_{new_id:02d}.png"
        new_path = base_dir / "images" / new_name
        if f_path != new_path:
            shutil.move(str(f_path), str(new_path))
        
        # Match with original prompt if possible, or just keep sequence
        # Since we modified the list in step 1, we should actually reconstruct the list
        # based on the original prompts that stayed.
        # Let's simplify: reconstruct the prompts list with new IDs
    
    # Actually, a better way to handle prompt-image sync after deletion:
    # We already removed from target_para["prompts"] at step 1.
    # Now we just need to update their IDs and URLs to match the new file sequence.
    for i, p_info in enumerate(target_para["prompts"]):
        p_info["id"] = i + 1
        p_info["url"] = f"/{video.base_dir}/images/p{paragraph_id:03d}_{p_info['id']:02d}.png"

    target_para["images_count"] = len(target_para["prompts"])
    target_para["seconds_per_image"] = target_para["seconds"] / target_para["images_count"]
    data["total_images"] = sum(p["images_count"] for p in data["items"])
    
    images_json.write_text(json.dumps(data, indent=2))
    
    return {"ok": True}

@router.post("/{video_id}/image-to-video")
async def convert_image_to_video(
    video_id: int, 
    req: ConvertToVideoRequest,
    db: Session = Depends(get_db)
):
    paragraph_id = req.paragraph_id
    image_id = req.image_id

    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    base_dir = Path(video.base_dir)
    images_json = base_dir / "image_prompts_all.json"
    if not images_json.exists():
        raise HTTPException(status_code=400, detail="Images not yet generated")
    
    data = json.loads(images_json.read_text())
    
    target_prompt = req.custom_prompt
    found = False
    
    for item in data.get("items", []):
        if item["paragraph_id"] == paragraph_id:
            for p_info in item.get("prompts", []):
                if p_info["id"] == image_id:
                    if not target_prompt:
                        target_prompt = p_info["prompt"]
                    found = True
                    break
        if found: break
    
    if not found:
        raise HTTPException(status_code=404, detail="Image info not found in json")

    # Locate source image
    source_img_path = base_dir / "images" / f"p{paragraph_id:03d}_{image_id:02d}.png"
    if not source_img_path.exists():
        raise HTTPException(status_code=404, detail="Source image file not found or already converted")
        
    out_video_path = base_dir / "images" / f"p{paragraph_id:03d}_{image_id:02d}.mp4"

    settings = get_user_settings_for_video(video, db)
    engine = ImageEngine(
        openai_api_key=settings.openai_api_key,
        leonardo_api_key=settings.leonardo_api_key,
        grok_api_key=settings.grok_api_key,
    )

    # Derive orientation from width/height (Video model has no orientation field)
    if video.width and video.height:
        if video.width > video.height:
            orientation = "horizontal"
        elif video.width < video.height:
            orientation = "vertical"
        else:
            orientation = "square"
    else:
        orientation = "vertical"

    if req.provider.lower() == "grok":
        cost_info = engine.generate_grok_video(
            prompt=target_prompt,
            image_path=source_img_path,
            out_path=out_video_path,
            duration=req.duration,
            orientation=orientation,
        )
        used_model = "grok-imagine-video"
    else:
        cost_info = engine.generate_leonardo_video(
            prompt=target_prompt,
            image_path=source_img_path,
            out_path=out_video_path,
            duration=req.duration,
            video_model=req.model_id,
            orientation=orientation,
        )
        used_model = req.model_id

    # Update JSON
    timestamp = int(datetime.now().timestamp())
    for item in data.get("items", []):
        if item["paragraph_id"] == paragraph_id:
            for p_info in item.get("prompts", []):
                if p_info["id"] == image_id:
                    p_info["is_video"] = True
                    p_info["video_model"] = used_model
                    p_info["url"] = f"/{video.base_dir}/images/{out_video_path.name}?t={timestamp}"
                    if cost_info:
                        existing_cost = p_info.get("cost", {"amount": 0})
                        p_info["cost"] = {"amount": existing_cost.get("amount", 0) + cost_info.get("amount", 0)}
                    break
    
    images_json.write_text(json.dumps(data, indent=2))
    source_img_path.unlink(missing_ok=True)
    
    return {"ok": True, "url": f"/{video.base_dir}/images/{out_video_path.name}?t={timestamp}"}

@router.post("/{video_id}/upload-clip/{paragraph_id}/{image_id}")
async def upload_clip(
    video_id: int,
    paragraph_id: int,
    image_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    base_dir = Path(video.base_dir)
    images_json = base_dir / "image_prompts_all.json"
    if not images_json.exists():
        raise HTTPException(status_code=400, detail="Images not yet generated")
        
    data = json.loads(images_json.read_text())
    
    # Save the file
    out_video_path = base_dir / "images" / f"p{paragraph_id:03d}_{image_id:02d}.mp4"
    with open(out_video_path, "wb") as f:
        f.write(await file.read())
        
    # Standardize video to avoid MoviePy freezes
    _normalize_video(out_video_path)
    # Update JSON
    timestamp = int(datetime.now().timestamp())
    found = False
    for item in data.get("items", []):
        if item["paragraph_id"] == paragraph_id:
            for p_info in item.get("prompts", []):
                if p_info["id"] == image_id:
                    p_info["is_video"] = True
                    p_info["video_model"] = "UPLOADED"
                    p_info["url"] = f"/{video.base_dir}/images/{out_video_path.name}?t={timestamp}"
                    found = True
                    break
    
    if not found:
        raise HTTPException(status_code=404, detail="Image info not found in json")
        
    images_json.write_text(json.dumps(data, indent=2))
    
    # Remove old .png if any
    source_img_path = base_dir / "images" / f"p{paragraph_id:03d}_{image_id:02d}.png"
    source_img_path.unlink(missing_ok=True)
    
    return {"ok": True, "url": f"/{video.base_dir}/images/{out_video_path.name}?t={timestamp}"}

def _normalize_video(video_path: Path):
    """Normalize video to a safe 24fps Constant Frame Rate and standard pixel format using ffmpeg."""
    import subprocess
    tmp_path = video_path.parent / f"tmp_norm_{video_path.name}"
    video_path.rename(tmp_path)
    try:
        norm_cmd = [
            "ffmpeg", "-y",
            "-i", str(tmp_path),
            "-vf", "scale='min(1080,iw)':-2,format=yuv420p", # max 1080p width, preserve aspect
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-r", "24",
            "-c:a", "aac", "-b:a", "128k",
            str(video_path)
        ]
        res = subprocess.run(norm_cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[_normalize_video] ffmpeg error: {res.stderr[-500:]}", flush=True)
            tmp_path.rename(video_path)
        else:
            tmp_path.unlink()
    except Exception as e:
        print(f"[_normalize_video] Critical failure: {e}", flush=True)
        if tmp_path.exists():
            tmp_path.rename(video_path)

from pydantic import BaseModel
class LinkClipRequest(BaseModel):
    paragraph_id: int
    image_id: int
    link: str

@router.post("/{video_id}/link-clip")
async def link_clip(
    video_id: int,
    req: LinkClipRequest,
    db: Session = Depends(get_db)
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
        
    base_dir = Path(video.base_dir)
    images_json = base_dir / "image_prompts_all.json"
    if not images_json.exists():
        raise HTTPException(status_code=400, detail="Images not yet generated")
        
    import re
    # Check if link is a direct .mp4 (e.g. Copied Video Address)
    if ".mp4" in req.link.lower():
        url = req.link.strip()
        from app.services.image_engine import ImageEngine
        engine = ImageEngine()
        try:
            out_video_path = base_dir / "images" / f"p{req.paragraph_id:03d}_{req.image_id:02d}.mp4"
            engine._download_image(url, out_video_path)
            # Standardize video to avoid MoviePy freezes
            _normalize_video(out_video_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to download direct MP4: {e}")
    else:
        # Fallback to trying to parse generation ID
        match = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', req.link)
        if not match:
            raise HTTPException(status_code=400, detail="El enlace no es un archivo .mp4 ni contiene un ID de generación.")
            
        gen_id = match.group(0)
        from app.services.image_engine import ImageEngine
        engine = ImageEngine()
        try:
            url = engine._poll_leonardo_video(gen_id, timeout=10)
            if not url:
                raise RuntimeError("No se pudo obtener el vídeo usando este ID. Leonardo devuelve null.")
            out_video_path = base_dir / "images" / f"p{req.paragraph_id:03d}_{req.image_id:02d}.mp4"
            engine._download_image(url, out_video_path)
            # Standardize video to avoid MoviePy freezes
            _normalize_video(out_video_path)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error en API de Leonardo: {e}")
            
    data = json.loads(images_json.read_text())
    timestamp = int(datetime.now().timestamp())
    found = False
    for item in data.get("items", []):
        if item["paragraph_id"] == req.paragraph_id:
            for p_info in item.get("prompts", []):
                if p_info["id"] == req.image_id:
                    p_info["is_video"] = True
                    p_info["video_model"] = "LINKED"
                    p_info["url"] = f"/{video.base_dir}/images/{out_video_path.name}?t={timestamp}"
                    found = True
                    break
    
    if not found:
        raise HTTPException(status_code=404, detail="Image info not found in json")
        
    images_json.write_text(json.dumps(data, indent=2))
    
    source_img_path = base_dir / "images" / f"p{req.paragraph_id:03d}_{req.image_id:02d}.png"
    source_img_path.unlink(missing_ok=True)
    
    return {"ok": True, "url": f"/{video.base_dir}/images/{out_video_path.name}?t={timestamp}"}

@router.post("/{video_id}/regenerate-prompt")
async def regenerate_prompt_api(
    video_id: int, 
    paragraph_id: int, 
    image_id: int, 
    db: Session = Depends(get_db)
):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    base_dir = Path(video.base_dir)
    plan_path = base_dir / "plan.json"
    images_json = base_dir / "image_prompts_all.json"
    
    if not plan_path.exists() or not images_json.exists():
        raise HTTPException(status_code=400, detail="Required data missing (plan or images_data)")
    
    plan = json.loads(plan_path.read_text())
    data = json.loads(images_json.read_text())
    
    # 1. Find paragraph text
    para_text = ""
    for item in plan:
        if item["idx"] == paragraph_id:
            para_text = item["spoken"]
            break

    if not para_text:
        raise HTTPException(status_code=404, detail="Paragraph text not found")

    # 1b. Find the stored phrase for this specific image (if generated by the
    # phrase-aware pipeline). Falls back to None for legacy videos so the LLM
    # uses the whole paragraph as before.
    image_phrase = None
    for item in data.get("items", []):
        if item["paragraph_id"] == paragraph_id:
            for p_info in item.get("prompts", []):
                if p_info["id"] == image_id:
                    image_phrase = p_info.get("phrase") or None
                    break
            break

    # 2. Get style (with channel override)
    style_name = data.get("style", "stocksenior")
    channel = db.query(Channel).filter(Channel.id == video.channel_id).first()
    channel_style = StyleService.get_channel_style(channel, style_name)

    # 3. Generate 1 new prompt — phrase-targeted if we have one
    settings = get_user_settings_for_video(video, db)
    engine = ImageEngine(
        openai_api_key=settings.openai_api_key,
        leonardo_api_key=settings.leonardo_api_key,
        grok_api_key=settings.grok_api_key,
        provider=video.llm_provider
    )
    script_full = "\n".join([item.get("spoken", "") for item in plan])

    # NEW: Load custom niche rules
    custom_niche_rules = StyleService.get_custom_niche_rules(base_dir)

    prompts = engine.generate_prompts(
        para_text,
        style_name,
        n=1,
        full_context=script_full,
        style_override=channel_style,
        custom_rules=custom_niche_rules,
        phrase=image_phrase,
    )
    
    if not prompts:
        raise HTTPException(status_code=500, detail="Failed to generate new prompt via AI")
    
    new_prompt = prompts[0]
    
    # 4. Update image_prompts_all.json
    found = False
    for item in data.get("items", []):
        if item["paragraph_id"] == paragraph_id:
            for p_info in item.get("prompts", []):
                if p_info["id"] == image_id:
                    p_info["prompt"] = new_prompt
                    found = True
                    break
        if found: break
    
    if found:
        images_json.write_text(json.dumps(data, indent=2))
        return {"ok": True, "prompt": new_prompt}
    
    raise HTTPException(status_code=404, detail="Image ID not found in mapping")

@router.post("/{video_id}/regenerate-thumbnail-hook")
async def regenerate_thumbnail_hook(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    base_dir = Path(video.base_dir)
    plan_path = base_dir / "plan.json"
    images_json = base_dir / "image_prompts_all.json"
    
    if not plan_path.exists() or not images_json.exists():
        raise HTTPException(status_code=400, detail="Required data missing")
    
    plan = json.loads(plan_path.read_text())
    data = json.loads(images_json.read_text())
    
    script_full = "\n".join([item.get("spoken", "") for item in plan])
    settings = get_user_settings_for_video(video, db)
    llm_prov = video.llm_provider
    api_key = settings.grok_api_key if llm_prov == "grok" else settings.openai_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail=f"Falta API Key para {llm_prov.upper()}.")
    seo = SEOEngine(api_key=api_key, provider=llm_prov)
    # NEW: use custom rules from guide for hook
    custom_title_rules = StyleService.get_custom_title_rules(base_dir)
    hook = seo.generate_thumbnail_hook(script_full[:2000], custom_rules=custom_title_rules)
    
    if "thumbnail" not in data:
        data["thumbnail"] = {}
    data["thumbnail"]["hook"] = hook
    
    images_json.write_text(json.dumps(data, indent=2))
    return {"ok": True, "hook": hook}

@router.post("/{video_id}/regenerate-thumbnail-visual-prompt")
async def regenerate_thumbnail_visual_prompt(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    base_dir = Path(video.base_dir)
    plan_path = base_dir / "plan.json"
    images_json = base_dir / "image_prompts_all.json"
    
    if not plan_path.exists() or not images_json.exists():
        raise HTTPException(status_code=400, detail="Required data missing")
    
    plan = json.loads(plan_path.read_text())
    data = json.loads(images_json.read_text())
    
    script_full = "\n".join([item.get("spoken", "") for item in plan])
    style_name = data.get("style", "stocksenior")
    settings = get_user_settings_for_video(video, db)
    llm_prov = video.llm_provider
    api_key = settings.grok_api_key if llm_prov == "grok" else settings.openai_api_key
    if not api_key:
        raise HTTPException(status_code=400, detail=f"Falta API Key para {llm_prov.upper()}.")
    seo = SEOEngine(api_key=api_key, provider=llm_prov)
    hook = data.get("thumbnail", {}).get("hook", "")
    
    # Use custom thumbnail rules if available
    custom_thumb_rules = StyleService.get_custom_thumbnail_rules(base_dir)
    visual_prompt = seo.generate_thumbnail_visual_prompt(
        script_full[:2000], style_name, 
        thumbnail_hook=hook,
        custom_rules=custom_thumb_rules
    )
    
    if "thumbnail" not in data:
        data["thumbnail"] = {}
    data["thumbnail"]["visual_prompt"] = visual_prompt
    
    images_json.write_text(json.dumps(data, indent=2))
    return {"ok": True, "visual_prompt": visual_prompt}

@router.post("/{video_id}/upload-thumbnail")
async def upload_thumbnail(video_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    base_dir = Path(video.base_dir)
    thumbnail_path = base_dir / "output" / "thumbnail.png"
    
    with open(thumbnail_path, "wb") as buffer:
        buffer.write(await file.read())
    
    return {"ok": True, "url": f"/{video.base_dir}/output/thumbnail.png?t={int(datetime.now().timestamp())}"}

@router.post("/{video_id}/generate-thumbnail")
async def generate_thumbnail_api(
    video_id: int, 
    req: ThumbnailGenerationRequest,
    db: Session = Depends(get_db)
):
    hook = req.hook
    visual_prompt = req.visual_prompt
    model_id = req.model_id

    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    base_dir = Path(video.base_dir)
    images_json = base_dir / "image_prompts_all.json"
    if not images_json.exists():
        raise HTTPException(status_code=400, detail="Generate images first")
    
    data = json.loads(images_json.read_text())
    
    if "thumbnail" not in data:
        data["thumbnail"] = {}
    
    if hook:
        data["thumbnail"]["hook"] = hook
    if visual_prompt:
        data["thumbnail"]["visual_prompt"] = visual_prompt
    
    current_hook = data["thumbnail"].get("hook")
    current_visual = data["thumbnail"].get("visual_prompt")
    
    if not current_hook or not current_visual:
        # Fallback to generation if missing
        plan_path = base_dir / "plan.json"
        if plan_path.exists():
            plan = json.loads(plan_path.read_text())
            script_full = "\n".join([item.get("spoken", "") for item in plan])
            settings = get_user_settings_for_video(video, db)
            llm_prov = video.llm_provider
            api_key = settings.grok_api_key if llm_prov == "grok" else settings.openai_api_key
            if not api_key:
                raise HTTPException(status_code=400, detail=f"Falta API Key para {llm_prov.upper()}.")
            
            seo = SEOEngine(api_key=api_key, provider=llm_prov)
            if not current_hook:
                custom_title_rules = StyleService.get_custom_title_rules(base_dir)
                current_hook = seo.generate_thumbnail_hook(script_full[:2000], custom_rules=custom_title_rules, channel_name=video.channel.name)
                data["thumbnail"]["hook"] = current_hook
                if not current_visual:
                    custom_thumb_rules = StyleService.get_custom_thumbnail_rules(base_dir)
                    current_visual = seo.generate_thumbnail_visual_prompt(
                        script_full[:2000], data.get("style", "stocksenior"), 
                        thumbnail_hook=current_hook,
                        custom_rules=custom_thumb_rules
                    )
                    data["thumbnail"]["visual_prompt"] = current_visual

    # Unify flow: Get negative prompt from channel style
    channel = db.query(Channel).filter(Channel.id == video.channel_id).first()
    style_name = data.get("style", "stocksenior")
    style_cfg = StyleService.get_channel_style(channel, style_name)
    neg = style_cfg.get("negative_prompt", "")
    
    gen_mode = req.generation_mode or "QUALITY"

    thumbnail_path = base_dir / "output" / "thumbnail.png"
    settings = get_user_settings_for_video(video, db)
    if not settings:
         raise HTTPException(status_code=400, detail="Faltan ajustes de usuario.")
         
    engine = ImageEngine(
        openai_api_key=settings.openai_api_key, 
        leonardo_api_key=settings.leonardo_api_key,
        grok_api_key=settings.grok_api_key,
        provider=video.llm_provider
    )
    await engine.generate_thumbnail(
        current_hook, current_visual, thumbnail_path, 
        size=f"{video.width}x{video.height}", 
        model_id=model_id,
        negative_prompt=neg,
        mode=gen_mode,
        channel_name=video.channel.name,
        workflow_name=data.get("workflow_name")
    )
    
    # Save updates
    images_json.write_text(json.dumps(data, indent=2))
    
    return {"ok": True, "url": f"/{video.base_dir}/output/thumbnail.png?t={int(datetime.now().timestamp())}"}

@router.post("/{video_id}/update-thumbnail-text")
async def update_thumbnail_text(
    video_id: int, 
    req: ThumbnailGenerationRequest,
    db: Session = Depends(get_db)
):
    hook = req.hook
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    if not hook:
        raise HTTPException(status_code=400, detail="Hook text is required")

    # Update json
    base_dir = Path(video.base_dir)
    images_json = base_dir / "image_prompts_all.json"
    if images_json.exists():
        data = json.loads(images_json.read_text())
        if "thumbnail" not in data: data["thumbnail"] = {}
        data["thumbnail"]["hook"] = hook
        images_json.write_text(json.dumps(data, indent=2))

    engine = ImageEngine()
    url_rel = engine.apply_text_to_thumbnail(video.base_dir, hook, channel_name=video.channel.name)
    
    return {"ok": True, "url": f"/{url_rel}?t={int(datetime.now().timestamp())}"}

@router.post("/{video_id}/seo")
async def generate_seo(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    base_dir = Path(video.base_dir)
    script_path = base_dir / "script.txt"
    if not script_path.exists():
        raise HTTPException(status_code=400, detail="Script not uploaded")
    
    script = script_path.read_text()
    settings = get_user_settings_for_video(video, db)
    llm_prov = video.llm_provider
    api_key = settings.grok_api_key if llm_prov == "grok" else settings.openai_api_key
    
    if not api_key:
        raise HTTPException(status_code=400, detail=f"Falta API Key para {llm_prov.upper()}.")
    
    engine = SEOEngine(api_key=api_key, provider=llm_prov)
    
    # Fetch custom rules
    desc_rules = StyleService.get_custom_description_rules(base_dir)
    tag_rules = StyleService.get_custom_tag_rules(base_dir)
    lang_rules = StyleService.get_custom_language_rules(base_dir)
    
    # Combine description rules with language rules for better context
    combined_desc_rules = f"{desc_rules or ''}\n{lang_rules or ''}".strip()
    
    description = engine.generate_description(script[:3000], custom_rules=combined_desc_rules)
    hashtags_list = engine.generate_hashtags(script[:2000], custom_rules=tag_rules)
    hashtags = " ".join(hashtags_list)
    
    # Also generate the question tags
    question_tags = engine.generate_video_questions_tags(script[:2000], custom_rules=tag_rules)
    
    video.description = description
    db.commit()
    
    (base_dir / "seo/metadata.json").write_text(json.dumps({
        "description": description,
        "hashtags": hashtags,
        "tags": question_tags
    }, indent=2))
    
    return {"ok": True, "description": description, "hashtags": hashtags, "tags": question_tags}

@router.post("/{video_id}/render")
async def render_video(video_id: int, subtitles: bool = False, overlay: str | None = None, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    base_dir = Path(video.base_dir)
    durations_path = base_dir / "paragraphs_durations.json"
    if not durations_path.exists():
        raise HTTPException(status_code=400, detail="Audio not generated")

    # Reset progress file and mark status as rendering
    output_dir = base_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    progress_file = output_dir / "render_progress.txt"
    progress_file.write_text("0")

    video.status = "rendering"
    video.last_error = None
    db.commit()

    def _do_render_sync(vid_id: int, subs: bool, ovl: str | None):
        """Runs in a thread executor so the event loop stays free for other requests."""
        from app.database import SessionLocal
        db_bg = SessionLocal()
        try:
            vid = db_bg.query(Video).filter(Video.id == vid_id).first()
            if not vid:
                return
            _render_video_blocking(vid, db_bg, subs, ovl)
        except Exception as e:
            print(f"[BG render] FAILED for video {vid_id}: {e}", flush=True)
            import traceback
            traceback.print_exc()
            vid = db_bg.query(Video).filter(Video.id == vid_id).first()
            if vid:
                vid.status = "failed"
                vid.last_error = str(e)
                db_bg.commit()
        finally:
            db_bg.close()

    # Run the CPU-bound render in a thread so the asyncio event loop stays
    # responsive for other requests (status polls, UI navigation, etc).
    loop = asyncio.get_running_loop()
    loop.run_in_executor(None, _do_render_sync, video_id, subtitles, overlay)

    return {"ok": True, "background": True, "status": "rendering"}


@router.get("/{video_id}/render-progress")
def get_render_progress(video_id: int, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    progress = 0
    if video.base_dir:
        progress_file = Path(video.base_dir) / "output" / "render_progress.txt"
        if progress_file.exists():
            try:
                progress = int(progress_file.read_text().strip() or 0)
            except Exception:
                progress = 0

    return {
        "progress": progress,
        "status": video.status,
        "last_error": video.last_error,
    }


def _render_video_blocking(video, db, subtitles: bool, overlay: str | None):
    """Original synchronous render logic, callable from background tasks."""
    try:
        base_dir = Path(video.base_dir)
        durations_path = base_dir / "paragraphs_durations.json"
        if not durations_path.exists():
            raise HTTPException(status_code=400, detail="Audio not generated")

        durations = json.loads(durations_path.read_text())
        
        image_paths = []
        audio_paths = []
        durs = []
        
        for d in durations:
            idx = d["id"]

            files_dict = {}
            for ext in [".png", ".mp4"]:
                for p in base_dir.glob(f"images/p{idx:03d}_*{ext}"):
                    files_dict[p.stem] = p

            img_ps = sorted(files_dict.values(), key=lambda x: x.stem)

            # Paragraph has no images: extend last visual to cover this paragraph's audio
            # so the audio keeps playing without the rendered video freezing/ending.
            if not img_ps:
                p_total_dur = d["seconds"]
                if durs:
                    print(f"[render] Paragraph {idx} has no images; extending previous visual by {p_total_dur:.1f}s", flush=True)
                    durs[-1] += p_total_dur
                    audio_paths.append(base_dir / "audio/chunks" / d["file"])
                else:
                    # No previous image to extend either — skip whole paragraph (audio would
                    # play with nothing to show, which is worse).
                    print(f"[render] WARNING: Paragraph {idx} has no images and no previous visual to extend; skipping audio too.", flush=True)
                continue
            
            v_ps = [p for p in img_ps if p.suffix.lower() == '.mp4']
            i_ps = [p for p in img_ps if p.suffix.lower() == '.png']
            
            # Helper to get duration of an MP4
            from moviepy.video.io.VideoFileClip import VideoFileClip
            
            p_total_dur = d["seconds"]
            video_durations = []
            sum_v_dur = 0
            
            for vp in v_ps:
                try:
                    with VideoFileClip(str(vp)) as vc:
                        vdur = vc.duration
                        video_durations.append(vdur)
                        sum_v_dur += vdur
                except:
                    video_durations.append(4.0) # Fallback
                    sum_v_dur += 4.0

            # If videos exceed paragraph duration, scale them down proportionally
            if sum_v_dur > p_total_dur:
                factor = p_total_dur / sum_v_dur
                for i in range(len(video_durations)):
                    video_durations[i] *= factor
                
                # In this case images get almost no time, let's give them a tiny bit if they exist
                for vp, vdur in zip(v_ps, video_durations):
                    image_paths.append(vp)
                    durs.append(vdur)
                
                if i_ps:
                    dur_per_img = 0.5 # Tiny flash for images if they exist but no time left
                    for ip in i_ps:
                        image_paths.append(ip)
                        durs.append(dur_per_img)
            else:
                # Videos take their natural duration
                for vp, vdur in zip(v_ps, video_durations):
                    image_paths.append(vp)
                    durs.append(vdur)
                
                # Remaining time for images
                rem_dur = p_total_dur - sum_v_dur
                if i_ps:
                    dur_per_img = rem_dur / len(i_ps)
                    for ip in i_ps:
                        image_paths.append(ip)
                        durs.append(dur_per_img)
                elif rem_dur > 0 and v_ps:
                    # If no images, distribute remaining time to the last video (stretch it)
                    durs[-1] += rem_dur
            
            audio_paths.append(base_dir / "audio/chunks" / d["file"])
        
        if not image_paths:
            raise HTTPException(status_code=400, detail="No images found for rendering")

        # Background music: Pick random file from channel/music
        bg_music_path = None
        channel_dir = base_dir.parent
        music_dir = channel_dir / "music"
        if music_dir.exists():
            music_files = list(music_dir.glob("*.mp3"))
            if music_files:
                bg_music_path = random.choice(music_files)

        # Determine overlay path if provided
        overlay_path = None
        if overlay and overlay != "Sin overlay":
            possible_overlay = Path("/app/overlay") / overlay
            if possible_overlay.exists():
                overlay_path = possible_overlay

        out_path = base_dir / "output/final_video.mp4"
        out_size = (video.width or 1024, video.height or 1792)
        
        RenderingEngine.render_simple_slideshow(
            image_paths=image_paths,
            durations=durs,
            audio_paths=audio_paths,
            out_path=out_path,
            out_size=out_size,
            bg_music_path=bg_music_path,
            overlay_video_path=overlay_path,
            bg_music_volume=0.06,
            voice_volume=1.6
        )
        
        # ── Karaoke Subtitles ──
        if subtitles:
            try:
                (base_dir / "output" / "render_progress.txt").write_text("98")
            except Exception:
                pass
            try:
                from app.services.subtitle_engine import SubtitleEngine
                settings = get_user_settings_for_video(video, db)
                if not settings or not settings.assemblyai_api_key:
                    print("[render] WARNING: Subtitle generation skipped missing AssemblyAI API Key.")
                else:
                    sub_engine = SubtitleEngine(api_key=settings.assemblyai_api_key)
                    
                    # Combine all audio chunks into a single file for transcription
                    combined_audio = base_dir / "output/combined_audio.mp3"
                    if not combined_audio.exists():
                        from pydub import AudioSegment
                        combined = AudioSegment.empty()
                        for ap in audio_paths:
                            combined += AudioSegment.from_mp3(str(ap))
                        combined.export(str(combined_audio), format="mp3")
                    
                    sub_engine.add_subtitles_to_video(
                        video_path=out_path,
                        audio_path=combined_audio,
                        video_size=out_size,
                        cache_dir=base_dir / "output"
                    )
                    print(f"[render] Karaoke subtitles applied successfully!", flush=True)
            except Exception as e:
                print(f"[render] WARNING: Subtitle generation failed: {e}", flush=True)
                # Don't fail the entire render if subtitles fail
        
        # Ensure progress shows 100% at the very end
        try:
            (base_dir / "output" / "render_progress.txt").write_text("100")
        except Exception:
            pass

        video.status = "ready"
        db.commit()

        return {"ok": True, "output": str(out_path), "bg_music": str(bg_music_path) if bg_music_path else None, "subtitles": subtitles}
    except Exception as e:
        video.status = "failed"
        video.last_error = str(e)
        db.commit()
        raise

