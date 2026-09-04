"""Generador de vídeo con LTX 2.5 (texto->vídeo vertical) vía ComfyUI.

Envía un grafo LTX 2.5 (GGUF distilled) a ComfyUI, sondea el estado y sirve el
MP4 resultante (proxy de /view de ComfyUI, ya que el output de ComfyUI no está
montado en el contenedor). Pensado para clips verticales cortos para colgar.
"""
import os
import json
import time
import uuid
from pathlib import Path

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional

from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/ltx", tags=["ltx-video"])

COMFY_URL = os.getenv("COMFY_URL", "http://192.168.1.46:8188").rstrip("/")
TEMPLATE = Path("/app/workflows/LTX25-T2V-Vertical.json")
TEMPLATE_I2V = Path("/app/workflows/LTX25-I2V-Vertical.json")
HISTORY_DIR = Path("/app/cache/ltx_history")


def _upload_output_image(filename: str) -> str:
    """Trae una imagen del output de ComfyUI (personaje/escena) y la sube a input
    para poder usarla como imagen de partida en I2V."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nombre no permitido")
    r = requests.get(f"{COMFY_URL}/view", params={"filename": filename, "type": "output", "subfolder": ""}, timeout=30)
    if not r.ok:
        raise HTTPException(status_code=404, detail="Imagen de partida no encontrada")
    up = requests.post(f"{COMFY_URL}/upload/image",
                       files={"image": (filename, r.content, "image/png")},
                       data={"overwrite": "true", "type": "input"}, timeout=30)
    if not up.ok:
        raise HTTPException(status_code=502, detail="No se pudo subir la imagen a ComfyUI")
    return up.json().get("name", filename)


def _hist_path(user_id: int) -> Path:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    return HISTORY_DIR / f"user_{user_id}.json"


def _load_hist(user_id: int) -> list:
    p = _hist_path(user_id)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_hist(user_id: int, items: list) -> None:
    _hist_path(user_id).write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _to_english_prompt(text: str) -> str:
    """Traduce/mejora el prompt a inglés cinematográfico (el encoder gemma de
    LTX es casi solo inglés). Best-effort: si falla, devuelve el original."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return text
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=os.getenv("OPENAI_BASE_URL") or None)
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You translate short prompts for a text-to-video model into fluent, vivid ENGLISH. "
                    "Keep the user's subject and intent EXACTLY. Output ONLY the English prompt on one "
                    "line, no quotes, no explanation. If it's already English, improve it slightly for "
                    "cinematic video (lighting, camera, detail)."
                )},
                {"role": "user", "content": text},
            ],
            temperature=0.4,
        )
        out = (r.choices[0].message.content or "").strip()
        return out or text
    except Exception:
        return text


def _snap32(v: int) -> int:
    return max(256, (int(v) // 32) * 32)


def _snap_len(n: int) -> int:
    # LTX quiere longitud de la forma 8k+1
    n = max(25, int(n))
    return ((n - 1) // 8) * 8 + 1


class LtxGenerateRequest(BaseModel):
    prompt: str
    negative: Optional[str] = None
    width: int = 512
    height: int = 768
    length: int = 121          # ~4.8 s @25fps
    fps: int = 25
    seed: Optional[int] = None
    auto_translate: bool = True


@router.post("/generate")
def ltx_generate(req: LtxGenerateRequest, current_user: User = Depends(get_current_user)):
    if not (req.prompt or "").strip():
        raise HTTPException(status_code=400, detail="Falta el prompt")
    if not TEMPLATE.exists():
        raise HTTPException(status_code=500, detail="Plantilla LTX no encontrada")

    wf = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    w, h = _snap32(req.width), _snap32(req.height)
    length = _snap_len(req.length)
    fps = max(8, min(30, int(req.fps)))
    import random
    seed = req.seed if req.seed is not None else random.randint(0, 2**31 - 1)

    prompt_used = _to_english_prompt(req.prompt.strip()) if req.auto_translate else req.prompt.strip()
    wf["pos"]["inputs"]["text"] = prompt_used
    if req.negative and req.negative.strip():
        wf["neg"]["inputs"]["text"] = req.negative.strip()
    wf["vlat"]["inputs"].update({"width": w, "height": h, "length": length})
    wf["alat"]["inputs"].update({"frames_number": length, "frame_rate": fps})
    wf["cond"]["inputs"]["frame_rate"] = fps
    wf["out"]["inputs"]["frame_rate"] = fps
    wf["noise"]["inputs"]["noise_seed"] = seed
    wf["out"]["inputs"]["filename_prefix"] = f"ltx_u{current_user.id}"

    try:
        r = requests.post(f"{COMFY_URL}/prompt", json={"prompt": wf}, timeout=30)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo contactar con ComfyUI: {e}")
    if not r.ok:
        raise HTTPException(status_code=400, detail=f"ComfyUI rechazó el grafo: {r.text[:500]}")
    pid = r.json().get("prompt_id")
    return {"ok": True, "prompt_id": pid, "width": w, "height": h, "length": length,
            "fps": fps, "seed": seed, "prompt_used": prompt_used}


class LtxI2VRequest(BaseModel):
    image_filename: str        # PNG en el output de ComfyUI (personaje/escena)
    prompt: str = ""           # movimiento/acción (opcional)
    width: int = 512
    height: int = 768
    length: int = 97
    fps: int = 25
    seed: Optional[int] = None
    auto_translate: bool = True


@router.post("/i2v")
def ltx_i2v(req: LtxI2VRequest, current_user: User = Depends(get_current_user)):
    """Anima una imagen (image-to-video) manteniendo su apariencia. La imagen es
    un PNG generado en la app (personaje/escena)."""
    if not (req.image_filename or "").strip():
        raise HTTPException(status_code=400, detail="Falta la imagen de partida")
    if not TEMPLATE_I2V.exists():
        raise HTTPException(status_code=500, detail="Plantilla I2V no encontrada")

    wf = json.loads(TEMPLATE_I2V.read_text(encoding="utf-8"))
    w, h = _snap32(req.width), _snap32(req.height)
    length = _snap_len(req.length)
    fps = max(8, min(30, int(req.fps)))
    import random
    seed = req.seed if req.seed is not None else random.randint(0, 2**31 - 1)

    motion = (req.prompt or "").strip() or "subtle natural motion, gentle movement, cinematic"
    prompt = _to_english_prompt(motion) if req.auto_translate else motion
    img_name = _upload_output_image(req.image_filename.strip())

    wf["pos"]["inputs"]["text"] = prompt
    wf["loadimg"]["inputs"]["image"] = img_name
    wf["resize"]["inputs"].update({"width": w, "height": h})
    wf["vlat"]["inputs"].update({"width": w, "height": h, "length": length})
    wf["alat"]["inputs"].update({"frames_number": length, "frame_rate": fps})
    wf["cond"]["inputs"]["frame_rate"] = fps
    wf["out"]["inputs"]["frame_rate"] = fps
    wf["noise"]["inputs"]["noise_seed"] = seed
    wf["out"]["inputs"]["filename_prefix"] = f"ltxi2v_u{current_user.id}"

    try:
        r = requests.post(f"{COMFY_URL}/prompt", json={"prompt": wf}, timeout=30)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo contactar con ComfyUI: {e}")
    if not r.ok:
        raise HTTPException(status_code=400, detail=f"ComfyUI rechazó el grafo: {r.text[:500]}")
    return {"ok": True, "prompt_id": r.json().get("prompt_id"), "width": w, "height": h,
            "length": length, "fps": fps, "seed": seed, "prompt_used": prompt}


@router.get("/status/{prompt_id}")
def ltx_status(prompt_id: str, current_user: User = Depends(get_current_user)):
    """Estado de un render. running/pending/done/error + fichero si terminó."""
    try:
        hist = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=15).json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ComfyUI no responde: {e}")

    if prompt_id not in hist:
        # ¿sigue en cola / ejecutando?
        try:
            q = requests.get(f"{COMFY_URL}/queue", timeout=10).json()
            running = any(prompt_id == str(item[1]) for item in q.get("queue_running", []))
            pending = any(prompt_id == str(item[1]) for item in q.get("queue_pending", []))
        except Exception:
            running = pending = False
        return {"status": "running" if running else ("pending" if pending else "unknown")}

    entry = hist[prompt_id]
    st = entry.get("status", {})
    status_str = st.get("status_str")
    if status_str == "error":
        # buscar el mensaje de error
        msg = ""
        for m in st.get("messages", []):
            if m and m[0] == "execution_error":
                msg = (m[1] or {}).get("exception_message", "")
                break
        return {"status": "error", "error": msg[:500]}

    # sacar el fichero de salida
    filename = None
    subfolder = ""
    for node in entry.get("outputs", {}).values():
        for g in node.get("gifs", []) + node.get("videos", []):
            filename = g.get("filename")
            subfolder = g.get("subfolder", "")
    if filename:
        return {"status": "done", "filename": filename, "subfolder": subfolder}
    return {"status": "done" if status_str == "success" else "running"}


class LtxSaveRequest(BaseModel):
    prompt: str                 # original (el que escribió el usuario)
    prompt_used: Optional[str] = None   # traducido/mejorado
    filename: str
    subfolder: Optional[str] = ""
    width: int = 0
    height: int = 0
    length: int = 0
    fps: int = 0
    seed: Optional[int] = None


@router.post("/save")
def ltx_save(req: LtxSaveRequest, current_user: User = Depends(get_current_user)):
    """Guarda un vídeo generado en el historial del usuario."""
    items = _load_hist(current_user.id)
    entry = {
        "id": uuid.uuid4().hex,
        "prompt": req.prompt,
        "prompt_used": req.prompt_used or "",
        "filename": req.filename,
        "subfolder": req.subfolder or "",
        "width": req.width, "height": req.height, "length": req.length, "fps": req.fps,
        "seed": req.seed,
        "created_at": int(time.time()),
    }
    items.insert(0, entry)          # más reciente primero
    _save_hist(current_user.id, items[:200])  # cap por si acaso
    return {"ok": True, "entry": entry}


@router.get("/history")
def ltx_history(current_user: User = Depends(get_current_user)):
    return {"ok": True, "items": _load_hist(current_user.id)}


@router.delete("/history/{entry_id}")
def ltx_history_delete(entry_id: str, current_user: User = Depends(get_current_user)):
    items = _load_hist(current_user.id)
    items = [x for x in items if x.get("id") != entry_id]
    _save_hist(current_user.id, items)
    return {"ok": True}


@router.get("/video")
def ltx_video(filename: str, subfolder: str = "", current_user: User = Depends(get_current_user)):
    """Sirve el MP4 desde ComfyUI (proxy de /view). El output de ComfyUI no está
    montado en el contenedor, así que lo traemos por HTTP."""
    # Guardas mínimas contra traversal en el nombre.
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nombre no permitido")
    try:
        r = requests.get(
            f"{COMFY_URL}/view",
            params={"filename": filename, "type": "output", "subfolder": subfolder},
            timeout=60,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ComfyUI no responde: {e}")
    if not r.ok:
        raise HTTPException(status_code=404, detail="Vídeo no encontrado")
    return Response(content=r.content, media_type="video/mp4")
