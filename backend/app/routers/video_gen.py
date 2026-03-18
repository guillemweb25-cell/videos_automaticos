from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, UploadFile, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
import json
import os
import random
import math
from datetime import datetime
from typing import List

from app.database import get_db
from app.models.video import Video
from app.models.channel import Channel
from app.schemas.video import (
    VideoCreate, VideoResponse, VideoUpdate, 
    ImageGenerationRequest, RegenerateImageRequest, 
    AddImageRequest, ThumbnailGenerationRequest
)

from app.services.audio_engine import AudioEngine
from app.services.image_engine import ImageEngine
from app.services.rendering_engine import RenderingEngine
from app.services.seo_engine import SEOEngine
from app.services.style_service import StyleService
from app.services.elevenlabs_voices import ELEVEN_VOICES
from app.services.style_service import ALIASES
from app.core.utils import slugify

router = APIRouter()

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
    styles = [{"id": alias, "name": alias.replace("_", " ").capitalize()} for alias in ALIASES.keys()]


    # Leonardo Models
    leonardo_models = [
        {"id": "7b592283-e8a7-4c5a-9ba6-d18c31f258b9", "name": "Lucid Origin (Economic/Great Text)"},
        {"id": "b24e16ff-06e3-43eb-8d33-4416c2d75876", "name": "Leonardo Vision XL (Fast)"},
        {"id": "gpt-image-1.5", "name": "GPT Image-1.5 (High Quality/Expensive)"},
        {"id": "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3", "name": "Phoenix 1.0 (Best for Text)"},
        {"id": "e316348f-7773-490e-adcd-46757c738eb7", "name": "Absolute Reality v1.6"},
    ]
    
    # Generation Modes
    generation_modes = [
        {"id": "FAST", "name": "Modo Rápido ($0.012)", "cost": 0.012},
        {"id": "QUALITY", "name": "Modo Calidad ($0.0852)", "cost": 0.0852},
    ]
    
    return {
        "voices": {
            "tiktok": tiktok_voices,
            "elevenlabs": eleven_voices
        },
        "styles": styles,
        "leonardo_models": leonardo_models,
        "generation_modes": generation_modes
    }

@router.post("/", response_model=VideoResponse)
def create_video(video_in: VideoCreate, db: Session = Depends(get_db)):
    # 1. Check channel exists
    channel = db.query(Channel).filter(Channel.id == video_in.channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    # 2. Create DB record
    video = Video(**video_in.model_dump())
    db.add(video)
    db.commit()
    db.refresh(video)

    # 3. Initialize directory (Cache structure: cache/0001-channel-name/YYYY-MM-DD-video-title)
    channel_slug = f"{channel.id:04d}-{slugify(channel.name)}"
    date_str = datetime.now().strftime("%Y-%m-%d")
    video_title_slug = slugify(video.title or "untitled")
    video_slug = f"{date_str}-{video_title_slug}"
    
    base_dir = Path("cache") / channel_slug / video_slug
    base_dir.mkdir(parents=True, exist_ok=True)
    
    (base_dir / "audio/chunks").mkdir(parents=True, exist_ok=True)
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

@router.get("/{video_id}/thumbnail.png")
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
    
    # Simple split into paragraphs for now
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
    
    video.status = "generating_audio"
    video.voice = voice
    db.commit()
    
    try:
        base_dir = Path(video.base_dir)
        plan_path = base_dir / "plan.json"
        if not plan_path.exists():
            raise HTTPException(status_code=400, detail="Script not uploaded")
        
        plan = json.loads(plan_path.read_text())
        results = []
        total_sec = 0
        
        for item in plan:
            idx = item["idx"]
            text = item["spoken"]
            out_path = base_dir / "audio/chunks" / f"{idx:03d}.mp3"
            
            # Caching: Skip if file already exists
            if not out_path.exists():
                if provider.lower() == "elevenlabs":
                    AudioEngine.synthesize_elevenlabs(text, voice, out_path)
                else:
                    AudioEngine.synthesize_tiktok(text, voice, out_path)
            
            dur = AudioEngine.get_duration(out_path)
            total_sec += dur
            results.append({"id": idx, "seconds": dur, "file": out_path.name})
        
        (base_dir / "paragraphs_durations.json").write_text(json.dumps(results, indent=2))
        
        video.duration_seconds = total_sec
        video.status = "audio_ready"
        db.commit()
        return {"ok": True, "total_seconds": total_sec, "chunks": len(results)}
    except Exception as e:
        video.status = "failed"
        video.last_error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{video_id}/images")
async def generate_images(video_id: int, req: ImageGenerationRequest, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video.status = "generating_images"
    video.style = req.style_name
    video.max_images_per_paragraph = req.max_images_per_paragraph
    db.commit()
    
    # Run image generation in background thread to avoid proxy timeouts
    import threading
    from app.database import SessionLocal
    
    def _generate_images_background(vid_id, sty, max_imgs, m_id, gen_mode):

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

            plan = json.loads(plan_path.read_text())
            engine = ImageEngine()
            
            # Load channel for custom style
            channel = db_bg.query(Channel).filter(Channel.id == vid.channel_id).first()
            
            seconds_per_image = 10.0
            all_prompts_data = {
                "video_id": vid_id,
                "style": sty,
                "model": "gpt-4o-mini",
                "seconds_per_image": seconds_per_image,
                "max_images_per_paragraph": max_imgs,
                "total_paragraphs": len(plan),
                "processed_paragraphs": 0,
                "total_images": 0,
                "items": [],
                "generation_mode": gen_mode
            }

            # Caching: Load existing prompts if possible
            existing_prompts_all = {}
            all_prompts_all_path = base_dir / "image_prompts_all.json"
            if all_prompts_all_path.exists():
                try:
                    old_data = json.loads(all_prompts_all_path.read_text())
                    if old_data.get("style") == sty and old_data.get("max_images_per_paragraph") == max_imgs:
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
                else:
                    import math
                    images_count = min(max_imgs, math.ceil(duration / seconds_per_image))
                
                # 1. Generate prompts (or reuse if text matches)
                cached = existing_prompts_all.get(idx)
                if cached and cached["spoken"] == text and len(cached["prompts"]) == images_count:
                    prompts = [p["prompt"] for p in cached["prompts"]]
                    cached_prompts_objs = cached["prompts"]
                    # Add cached prompts to history for next paragraphs
                    recent_prompts.extend(prompts)
                else:
                    channel_style = StyleService.get_channel_style(channel, sty)
                    prompts = engine.generate_prompts(
                        text, sty, 
                        n=images_count, 
                        full_context=script_full, 
                        style_override=channel_style,
                        recent_history=recent_prompts[-8:], # Pass last 8 prompts as history
                        custom_rules=custom_niche_rules
                    )
                    recent_prompts.extend(prompts)
                    cached_prompts_objs = []
                
                if not prompts: continue

                
                paragraph_item = {
                    "paragraph_id": idx,
                    "seconds": duration,
                    "spoken": text,
                    "images_count": len(prompts),
                    "seconds_per_image": duration / len(prompts) if prompts else 0,
                    "prompts": []
                }
                
                # 2. Generate images (skip if exists)
                paragraph_item["prompts"] = []
                for i, p_text in enumerate(prompts):
                    img_idx = i + 1
                    out_path = base_dir / "images" / f"p{idx:03d}_{img_idx:02d}.png"
                    
                    if not out_path.exists():
                        style = StyleService.get_channel_style(channel, sty)
                        neg = style.get("negative_prompt")
                        
                        init_image_id = None
                        if i > 0:
                            prev_img_path = base_dir / "images" / f"p{idx:03d}_{i:02d}.png"
                            if prev_img_path.exists():
                                try:
                                    init_image_id = engine.upload_init_image(prev_img_path)
                                except Exception as e:
                                    print(f"Warning: Failed to upload reference image for paragraph {idx} image {img_idx}: {e}")
                        
                        cost_info = engine.generate_leonardo_image(p_text, out_path, size=f"{vid.width}x{vid.height}", negative_prompt=neg, init_image_id=init_image_id, model_id=m_id, mode=gen_mode)
                        p_info_entry = {
                            "id": img_idx,
                            "prompt": p_text
                        }
                        if cost_info:
                            p_info_entry["cost"] = cost_info
                        paragraph_item["prompts"].append(p_info_entry)
                    else:
                        existing_p = None
                        if cached_prompts_objs and i < len(cached_prompts_objs):
                            existing_p = cached_prompts_objs[i]
                        
                        entry = {
                            "id": img_idx,
                            "prompt": p_text
                        }
                        if existing_p and "cost" in existing_p:
                            entry["cost"] = existing_p["cost"]
                            
                        paragraph_item["prompts"].append(entry)
                    total_images += 1
                
                all_prompts_data["items"].append(paragraph_item)
                all_prompts_data["processed_paragraphs"] += 1
                # Save progress after each paragraph
                all_prompts_data["total_images"] = total_images
                all_prompts_all_path.write_text(json.dumps(all_prompts_data, indent=2))
            
            all_prompts_data["total_images"] = total_images
            all_prompts_all_path.write_text(json.dumps(all_prompts_data, indent=2))
            
            # 3. Generate Thumbnail with Hook
            thumbnail_path = base_dir / "output" / "thumbnail.png"
            if not thumbnail_path.exists():
                try:
                    seo = SEOEngine()
                    script_snippet = "\n".join([item.get("spoken", "") for item in plan])
                    # NEW: use custom rules from guide for hook
                    custom_title_rules = StyleService.get_custom_title_rules(base_dir)
                    hook = seo.generate_thumbnail_hook(script_full, custom_rules=custom_title_rules)
                    
                    # Look for custom thumbnail rules in style-guide.md
                    custom_thumb_rules = StyleService.get_custom_thumbnail_rules(base_dir)
                    visual_prompt = seo.generate_thumbnail_visual_prompt(
                        script_full, sty, 
                        thumbnail_hook=hook, 
                        custom_rules=custom_thumb_rules
                    )
                    
                    if "thumbnail" not in all_prompts_data:
                        all_prompts_data["thumbnail"] = {}
                    all_prompts_data["thumbnail"]["hook"] = hook
                    all_prompts_data["thumbnail"]["visual_prompt"] = visual_prompt
                    
                    engine.generate_thumbnail(hook, visual_prompt, thumbnail_path, size=f"{vid.width}x{vid.height}")
                except Exception as e:
                    print(f"Warning: Thumbnail generation failed: {e}")

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
    
    thread = threading.Thread(
        target=_generate_images_background,
        args=(video_id, req.style_name, req.max_images_per_paragraph, req.model_id, req.generation_mode),
        daemon=True
    )

    thread.start()
    
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
    # Add relative path for frontend access via /cache
    # base_dir is like "cache/0001-channel/..."
    # We want "cache/0001-channel/.../images/p001_01.png"
    for item in data.get("items", []):
        p_idx = item["paragraph_id"]
        item["audio_url"] = f"/{video.base_dir}/audio/chunks/{p_idx:03d}.mp3"
        for p_info in item.get("prompts", []):
            img_idx = p_info["id"]
            rel_path = f"{video.base_dir}/images/p{p_idx:03d}_{img_idx:02d}.png"
            p_info["url"] = f"/{rel_path}"
    
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

    # Update json if prompt changed
    if custom_prompt:
        images_json.write_text(json.dumps(data, indent=2))

    # Delete old image so Leonardo generates a new one (or just overwrite it)
    out_path = base_dir / "images" / f"p{paragraph_id:03d}_{image_id:02d}.png"
    if out_path.exists():
        out_path.unlink()
    
    engine = ImageEngine()
    style_name = data.get("style", "stocksenior")
    channel = db.query(Channel).filter(Channel.id == video.channel_id).first()
    style = StyleService.get_channel_style(channel, style_name)
    neg = style.get("negative_prompt")
    
    # Check if a specific model was requested (passed as a query param or from somewhere)
    # For now, we'll allow an optional model_id in the regenerate call too if we want
    cost_info = engine.generate_leonardo_image(target_prompt, out_path, size=f"{video.width}x{video.height}", negative_prompt=neg, model_id=model_id, mode=generation_mode)
    
    # Update cost in JSON
    for item in data.get("items", []):
        if item["paragraph_id"] == paragraph_id:
            for p_info in item.get("prompts", []):
                if p_info["id"] == image_id:
                    if cost_info:
                        p_info["cost"] = cost_info
                    break
    
    # Save JSON with prompt and cost update
    images_json.write_text(json.dumps(data, indent=2))
    
    return {"ok": True, "url": f"/{video.base_dir}/images/{out_path.name}?t={int(datetime.now().timestamp())}"}

@router.post("/{video_id}/add-image")
async def add_image(video_id: int, req: AddImageRequest, db: Session = Depends(get_db)):
    paragraph_id = req.paragraph_id
    style_name = req.style_name
    model_id = req.model_id
    generation_mode = req.generation_mode

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

    # 1. Get reference image and prompt
    last_p = target_para["prompts"][-1]
    last_img_id = last_p["id"]
    last_prompt = last_p["prompt"]
    last_img_path = base_dir / "images" / f"p{paragraph_id:03d}_{last_img_id:02d}.png"

    # 2. Logic for continuity
    engine = ImageEngine()
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
    
    new_prompt = engine.generate_continuation_prompt(
        target_para["spoken"], 
        last_prompt, 
        effective_style, 
        style_override=channel_style,
        custom_rules=custom_niche_rules
    )
    
    # 3. Generate New Image
    new_img_id = last_img_id + 1
    out_path = base_dir / "images" / f"p{paragraph_id:03d}_{new_img_id:02d}.png"
    
    style = StyleService.get_channel_style(channel, effective_style)
    neg = style.get("negative_prompt")
    
    cost_info = engine.generate_leonardo_image(new_prompt, out_path, size=f"{video.width}x{video.height}", negative_prompt=neg, init_image_id=init_image_id, model_id=model_id, mode=generation_mode)

    # 4. Update JSON
    new_entry = {
        "id": new_img_id,
        "prompt": new_prompt,
        "url": f"/{video.base_dir}/images/p{paragraph_id:03d}_{new_img_id:02d}.png"
    }
    if cost_info:
        new_entry["cost"] = cost_info
        
    target_para["prompts"].append(new_entry)
    target_para["images_count"] = len(target_para["prompts"])
    target_para["seconds_per_image"] = target_para["seconds"] / target_para["images_count"]
    data["total_images"] += 1
    
    images_json.write_text(json.dumps(data, indent=2))
    
    return {"ok": True, "image": target_para["prompts"][-1]}

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
    
    # 2. Get style (with channel override)
    style_name = data.get("style", "stocksenior")
    channel = db.query(Channel).filter(Channel.id == video.channel_id).first()
    channel_style = StyleService.get_channel_style(channel, style_name)
    
    # 3. Generate 1 new prompt
    engine = ImageEngine()
    script_full = "\n".join([item.get("spoken", "") for item in plan])
    
    # NEW: Load custom niche rules
    custom_niche_rules = StyleService.get_custom_niche_rules(base_dir)
    
    prompts = engine.generate_prompts(
        para_text, 
        style_name, 
        n=1, 
        full_context=script_full, 
        style_override=channel_style,
        custom_rules=custom_niche_rules
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
    seo = SEOEngine()
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
    seo = SEOEngine()
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
            seo = SEOEngine()
            if not current_hook:
                current_hook = seo.generate_thumbnail_hook(script_full[:2000])
                data["thumbnail"]["hook"] = current_hook
                if not current_visual:
                    custom_thumb_rules = StyleService.get_custom_thumbnail_rules(base_dir)
                    current_visual = seo.generate_thumbnail_visual_prompt(
                        script_full[:2000], data.get("style", "stocksenior"), 
                        thumbnail_hook=current_hook,
                        custom_rules=custom_thumb_rules
                    )
                    data["thumbnail"]["visual_prompt"] = current_visual

    thumbnail_path = base_dir / "output" / "thumbnail.png"
    engine = ImageEngine()
    engine.generate_thumbnail(current_hook, current_visual, thumbnail_path, size=f"{video.width}x{video.height}", model_id=model_id)
    
    # Save updates
    images_json.write_text(json.dumps(data, indent=2))
    
    return {"ok": True, "url": f"/{video.base_dir}/output/thumbnail.png?t={int(datetime.now().timestamp())}"}

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
    engine = SEOEngine()
    
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
def render_video(video_id: int, subtitles: bool = False, db: Session = Depends(get_db)):
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    video.status = "rendering"
    db.commit()
    
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
            # Look for all images pXXX_XX.png
            img_ps = sorted(list(base_dir.glob(f"images/p{idx:03d}_*.png")))
            if not img_ps:
                continue
            
            dur_per_img = d["seconds"] / len(img_ps)
            for img_p in img_ps:
                image_paths.append(img_p)
                durs.append(dur_per_img)
            
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

        out_path = base_dir / "output/final_video.mp4"
        out_size = (video.width or 1024, video.height or 1792)
        
        RenderingEngine.render_simple_slideshow(
            image_paths=image_paths,
            durations=durs,
            audio_paths=audio_paths,
            out_path=out_path,
            out_size=out_size,
            bg_music_path=bg_music_path,
            bg_music_volume=0.06,
            voice_volume=1.6
        )
        
        # ── Karaoke Subtitles ──
        if subtitles:
            try:
                from app.services.subtitle_engine import SubtitleEngine
                sub_engine = SubtitleEngine()
                
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
        
        video.status = "ready"
        db.commit()
        
        return {"ok": True, "output": str(out_path), "bg_music": str(bg_music_path) if bg_music_path else None, "subtitles": subtitles}
    except Exception as e:
        video.status = "failed"
        video.last_error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

