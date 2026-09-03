"""Generador de personajes consistentes (SDXL + IPAdapter-face) vía ComfyUI.

Genera un retrato base y, con IPAdapter (preset PLUS FACE), un set de imágenes
del MISMO personaje en varias poses/ángulos — manteniendo la cara. Sirve como
dataset para reutilizar el personaje (o entrenar una LoRA). Todo en un solo grafo
(la imagen base alimenta directamente los nodos IPAdapter, sin subir ficheros).
"""
import os
import json
import time
import uuid
from pathlib import Path
from typing import Optional, List

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.models.user import User
from app.routers.video_ltx import _to_english_prompt  # reutiliza la traducción ES->EN

router = APIRouter(prefix="/characters", tags=["characters"])

COMFY_URL = os.getenv("COMFY_URL", "http://192.168.1.46:8188").rstrip("/")
STORE_DIR = Path("/app/cache/characters")

# Rutas con barra normal (sin minas de escape \n); se convierten a la barra de
# Windows que ComfyUI espera al construir el grafo.
STYLES = {
    "anime": "SDXL/novaAnimeXL_xlV10.safetensors",
    "realista": "SDXL/RealVisXL_V5.0_fp16.safetensors",
    "cartoon": "SDXL/disneyrealcartoonmix_v10.safetensors",
}
STYLE_SUFFIX = {
    "anime": "anime style, cel shaded, masterpiece, best quality",
    "realista": "photorealistic, natural skin, sharp focus, 8k",
    "cartoon": "3d cartoon style, pixar style, colorful",
}
# (clave, sufijo en inglés) — la base es el retrato frontal limpio.
# Sufijos forzados (con peso) para que la pose gane al IPAdapter y varíe de verdad.
POSES = [
    ("tres_cuartos", "(three-quarter view:1.3), body turned to the side, cowboy shot, waist up, looking over shoulder"),
    ("perfil", "(side profile view:1.4), (facing left:1.2), profile portrait, looking to the side"),
    ("cuerpo_entero", "(full body shot:1.5), (wide shot:1.3), standing, dynamic action pose, whole body visible from head to feet, full character"),
    ("sonriendo", "(big happy smile:1.3), (laughing:1.1), front view, cheerful joyful expression, upper body"),
]

# Peso de IPAdapter: alto = misma cara pero copia composición (poco cambio);
# bajo = más variación de pose. 0.6 + "ease out" es el equilibrio cara/pose.
IP_WEIGHT = 0.6
IP_WEIGHT_TYPE = "ease out"
NEG = "lowres, bad anatomy, worst quality, blurry, extra fingers, deformed, multiple people, text, watermark, (nsfw:1.6), (nude:1.6)"


def _store_path(uid: int) -> Path:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    return STORE_DIR / f"user_{uid}.json"


def _load(uid: int) -> list:
    p = _store_path(uid)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(uid: int, items: list) -> None:
    _store_path(uid).write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_graph(uid: int, desc_en: str, ckpt: str, style_suffix: str, seed: int,
                 num_poses: int, w: int = 832, h: int = 1216) -> dict:
    desc = f"{desc_en}, {style_suffix}"
    ckpt = ckpt.replace("/", "\\")  # ComfyUI (Windows) lista los checkpoints con backslash
    g = {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["ckpt", 1]}},
        "ipload": {"class_type": "IPAdapterUnifiedLoader", "inputs": {"model": ["ckpt", 0], "preset": "PLUS FACE (portraits)"}},
        "base_lat": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "base_pos": {"class_type": "CLIPTextEncode", "inputs": {"text": f"{desc}, front view portrait, looking at viewer, simple background", "clip": ["ckpt", 1]}},
        "base_k": {"class_type": "KSampler", "inputs": {"seed": seed, "steps": 26, "cfg": 6.0, "sampler_name": "euler_ancestral", "scheduler": "normal", "denoise": 1, "model": ["ckpt", 0], "positive": ["base_pos", 0], "negative": ["neg", 0], "latent_image": ["base_lat", 0]}},
        "base_dec": {"class_type": "VAEDecode", "inputs": {"samples": ["base_k", 0], "vae": ["ckpt", 2]}},
        "base_save": {"class_type": "SaveImage", "inputs": {"filename_prefix": f"char_u{uid}_base", "images": ["base_dec", 0]}},
    }
    for i, (_key, suffix) in enumerate(POSES[:num_poses]):
        g[f"ip_{i}"] = {"class_type": "IPAdapterAdvanced", "inputs": {"model": ["ipload", 0], "ipadapter": ["ipload", 1], "image": ["base_dec", 0], "weight": IP_WEIGHT, "weight_type": IP_WEIGHT_TYPE, "combine_embeds": "concat", "start_at": 0.0, "end_at": 0.9, "embeds_scaling": "V only"}}
        g[f"pos_{i}"] = {"class_type": "CLIPTextEncode", "inputs": {"text": f"{desc}, {suffix}", "clip": ["ckpt", 1]}}
        g[f"lat_{i}"] = {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}}
        g[f"k_{i}"] = {"class_type": "KSampler", "inputs": {"seed": seed + 1 + i, "steps": 26, "cfg": 6.0, "sampler_name": "euler_ancestral", "scheduler": "normal", "denoise": 1, "model": [f"ip_{i}", 0], "positive": [f"pos_{i}", 0], "negative": ["neg", 0], "latent_image": [f"lat_{i}", 0]}}
        g[f"dec_{i}"] = {"class_type": "VAEDecode", "inputs": {"samples": [f"k_{i}", 0], "vae": ["ckpt", 2]}}
        g[f"save_{i}"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": f"char_u{uid}_pose{i}", "images": [f"dec_{i}", 0]}}
    return g


class CharGenerateRequest(BaseModel):
    description: str
    style: str = "anime"
    num_poses: int = 4
    seed: Optional[int] = None


@router.post("/generate")
def char_generate(req: CharGenerateRequest, current_user: User = Depends(get_current_user)):
    if not (req.description or "").strip():
        raise HTTPException(status_code=400, detail="Falta la descripción del personaje")
    ckpt = STYLES.get(req.style, STYLES["anime"])
    style_suffix = STYLE_SUFFIX.get(req.style, STYLE_SUFFIX["anime"])
    desc_en = _to_english_prompt(req.description.strip())
    import random
    seed = req.seed if req.seed is not None else random.randint(0, 2**31 - 1)
    num = max(1, min(len(POSES), int(req.num_poses)))

    wf = _build_graph(current_user.id, desc_en, ckpt, style_suffix, seed, num)
    try:
        r = requests.post(f"{COMFY_URL}/prompt", json={"prompt": wf}, timeout=30)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo contactar con ComfyUI: {e}")
    if not r.ok:
        raise HTTPException(status_code=400, detail=f"ComfyUI rechazó el grafo: {r.text[:500]}")
    return {"ok": True, "prompt_id": r.json().get("prompt_id"), "expected": num + 1,
            "description_en": desc_en, "style": req.style, "seed": seed}


@router.get("/status/{prompt_id}")
def char_status(prompt_id: str, current_user: User = Depends(get_current_user)):
    try:
        hist = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=15).json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ComfyUI no responde: {e}")
    if prompt_id not in hist:
        try:
            q = requests.get(f"{COMFY_URL}/queue", timeout=10).json()
            running = any(prompt_id == str(i[1]) for i in q.get("queue_running", []))
        except Exception:
            running = False
        return {"status": "running" if running else "pending"}
    entry = hist[prompt_id]
    st = entry.get("status", {}).get("status_str")
    if st == "error":
        return {"status": "error"}
    # recoger imágenes en orden: base primero, luego poses
    imgs = []
    outs = entry.get("outputs", {})
    for key in ["base_save"] + [f"save_{i}" for i in range(len(POSES))]:
        node = outs.get(key)
        if node:
            for im in node.get("images", []):
                imgs.append(im.get("filename"))
    if imgs:
        return {"status": "done", "images": imgs}
    return {"status": "running"}


class CharSaveRequest(BaseModel):
    name: str
    description: str
    description_en: Optional[str] = ""
    style: str = "anime"
    seed: Optional[int] = None
    images: List[str] = []


@router.post("/save")
def char_save(req: CharSaveRequest, current_user: User = Depends(get_current_user)):
    items = _load(current_user.id)
    entry = {
        "id": uuid.uuid4().hex,
        "name": req.name or "Personaje",
        "description": req.description,
        "description_en": req.description_en or "",
        "style": req.style,
        "seed": req.seed,
        "images": req.images,
        "created_at": int(time.time()),
    }
    items.insert(0, entry)
    _save(current_user.id, items[:100])
    return {"ok": True, "entry": entry}


@router.get("/list")
def char_list(current_user: User = Depends(get_current_user)):
    return {"ok": True, "items": _load(current_user.id)}


@router.delete("/{entry_id}")
def char_delete(entry_id: str, current_user: User = Depends(get_current_user)):
    items = [x for x in _load(current_user.id) if x.get("id") != entry_id]
    _save(current_user.id, items)
    return {"ok": True}


@router.get("/image")
def char_image(filename: str, current_user: User = Depends(get_current_user)):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nombre no permitido")
    try:
        r = requests.get(f"{COMFY_URL}/view", params={"filename": filename, "type": "output", "subfolder": ""}, timeout=30)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"ComfyUI no responde: {e}")
    if not r.ok:
        raise HTTPException(status_code=404, detail="Imagen no encontrada")
    return Response(content=r.content, media_type="image/png")
