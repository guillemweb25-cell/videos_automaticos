"""Repost / mirror flow: download a YouTube video with yt-dlp and hand it back
ready to re-upload by hand to another platform (Bilibili.com).

Deliberately does NOT auto-upload anywhere — the user drops the returned MP4 +
metadata into Bilibili manually (~2 min/video). Fully isolated from the AI
generation pipeline; a "mirror" channel just reuses the Channel row with its
AI fields left null.
"""
import os
import re
import asyncio
from pathlib import Path
from urllib.parse import quote

from urllib.parse import urlparse

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.models.channel import Channel
from app.models.user import User
from app.services.youtube_dl import YouTubeDLService, DOWNLOAD_BASE

router = APIRouter(prefix="/repost", tags=["repost"])


def _safe_folder(channel: Channel) -> str:
    """Stable, filesystem-safe subfolder for a channel's downloads."""
    base = channel.creds_dir or channel.youtube_handle or f"channel_{channel.id}"
    return re.sub(r"[^A-Za-z0-9_.-]", "_", base.lstrip("@")) or f"channel_{channel.id}"


def _get_owned_channel(channel_id: int, db: Session, user: User) -> Channel:
    channel = (
        db.query(Channel)
        .filter(Channel.id == channel_id, Channel.user_id == user.id)
        .first()
    )
    if not channel:
        raise HTTPException(status_code=404, detail="Canal no encontrado")
    return channel


_THUMB_HOSTS = {
    "i.ytimg.com", "i1.ytimg.com", "i2.ytimg.com", "i3.ytimg.com",
    "i4.ytimg.com", "i9.ytimg.com", "img.youtube.com", "yt3.ggpht.com",
    "s.ytimg.com",
}


class RepostDownloadRequest(BaseModel):
    url: str


@router.get("/{channel_id}/info")
async def repost_info(
    channel_id: int,
    url: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Metadatos del vídeo (título, descripción, etiquetas, miniatura) SIN
    descargar el MP4. Para la ficha previa."""
    _get_owned_channel(channel_id, db, current_user)
    if not (url or "").strip():
        raise HTTPException(status_code=400, detail="Falta la URL del vídeo")
    try:
        info = await asyncio.to_thread(YouTubeDLService.video_info, url.strip())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al leer el vídeo: {e}")
    if info.get("thumbnail"):
        from urllib.parse import quote as _q
        info["thumbnail_proxy"] = f"/repost/{channel_id}/thumbnail?url={_q(info['thumbnail'])}"
    return info


@router.get("/{channel_id}/thumbnail")
def repost_thumbnail(
    channel_id: int,
    url: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Proxy de la miniatura (para poder descargarla desde el navegador sin
    problemas de CORS). Restringido a hosts de miniaturas de YouTube."""
    _get_owned_channel(channel_id, db, current_user)
    host = (urlparse(url).hostname or "").lower()
    if host not in _THUMB_HOSTS:
        raise HTTPException(status_code=400, detail="Host de miniatura no permitido")
    try:
        r = requests.get(url, timeout=20)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo obtener la miniatura: {e}")
    if not r.ok:
        raise HTTPException(status_code=404, detail="Miniatura no encontrada")

    # YouTube sirve la miniatura en WEBP y Bilibili no lo acepta: convertimos
    # siempre a PNG con Pillow.
    try:
        import io
        from PIL import Image
        img = Image.open(io.BytesIO(r.content)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")
    except Exception:
        # Fallback improbable: si la conversión falla, devolvemos el original.
        return Response(content=r.content, media_type=r.headers.get("content-type", "image/jpeg"))


@router.post("/{channel_id}/download")
async def repost_download(
    channel_id: int,
    req: RepostDownloadRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Descarga el vídeo de YouTube (MP4, mejor calidad) y devuelve metadatos
    listos para reubir. La descarga (bloqueante) corre en un hilo."""
    channel = _get_owned_channel(channel_id, db, current_user)
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="Falta la URL del vídeo")

    folder = _safe_folder(channel)
    try:
        info = await asyncio.to_thread(YouTubeDLService.download_video, url, folder)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al descargar: {e}")

    fp = Path(info["file_path"])
    try:
        rel = fp.resolve().relative_to(DOWNLOAD_BASE.resolve())
    except Exception:
        rel = Path(folder) / fp.name
    rel_str = str(rel).replace("\\", "/")

    return {
        "ok": True,
        "title": info.get("title", ""),
        "description": info.get("description", ""),
        "tags": info.get("tags", []),
        "categories": info.get("categories", []),
        "duration": info.get("duration"),
        "original_url": info.get("original_url", url),
        "filename": fp.name,
        "size_bytes": fp.stat().st_size if fp.exists() else None,
        "rel_path": rel_str,
        "download_url": f"/repost/{channel_id}/file?rel={quote(rel_str)}",
    }


@router.get("/{channel_id}/downloads")
def repost_list(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lista los MP4 ya descargados para este canal (más recientes primero)."""
    channel = _get_owned_channel(channel_id, db, current_user)
    d = DOWNLOAD_BASE / _safe_folder(channel)
    files = []
    if d.exists():
        for f in sorted(d.glob("*.mp4"), key=os.path.getctime, reverse=True):
            rel_str = f"{_safe_folder(channel)}/{f.name}"
            files.append({
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "rel_path": rel_str,
                "download_url": f"/repost/{channel_id}/file?rel={quote(rel_str)}",
            })
    return {"ok": True, "count": len(files), "files": files}


@router.get("/{channel_id}/file")
def repost_file(
    channel_id: int,
    rel: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sirve un MP4 descargado. Restringido a la carpeta del canal (anti path
    traversal)."""
    channel = _get_owned_channel(channel_id, db, current_user)
    base = DOWNLOAD_BASE.resolve()
    target = (DOWNLOAD_BASE / rel).resolve()
    # El fichero debe estar dentro de la carpeta de descargas de ESTE canal.
    channel_dir = (DOWNLOAD_BASE / _safe_folder(channel)).resolve()
    if not str(target).startswith(str(channel_dir)) or not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Ruta no permitida")
    if not target.exists():
        raise HTTPException(status_code=404, detail="Fichero no encontrado")
    return FileResponse(str(target), filename=target.name, media_type="video/mp4")
