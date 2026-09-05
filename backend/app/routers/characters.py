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
import threading
from pathlib import Path
from typing import Optional, List

import requests
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/characters", tags=["characters"])


def _translate_character(text: str, neutral_bg: bool) -> str:
    """Traduce la descripción del personaje a inglés. Con fondo neutro, instruye
    al LLM para describir SOLO al personaje (sin escena/fondo/luz), que es lo que
    metía fondos indeseados en el dataset."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return text
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=os.getenv("OPENAI_BASE_URL") or None)
        extra = (" Describe ONLY the character (body, face, hair, eyes, clothing, accessories, "
                 "expression). Do NOT mention any background, scene, setting, environment, "
                 "location or lighting." if neutral_bg else "")
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "Translate this character description into fluent English for an image "
                    "model. Keep the subject and appearance EXACTLY. Output ONLY the English "
                    "description on one line, no quotes, no explanation." + extra
                )},
                {"role": "user", "content": text},
            ],
            temperature=0.4,
        )
        return (r.choices[0].message.content or "").strip() or text
    except Exception:
        return text

COMFY_URL = os.getenv("COMFY_URL", "http://192.168.1.46:8188").rstrip("/")
STORE_DIR = Path("/app/cache/characters")
POSE_LIB = Path("/app/pose_library")           # esqueletos OpenPose por género
# ControlNet OpenPose SDXL "fuerte" (xinsir); fallback al T2I-Adapter si falta.
OPENPOSE_CN = "SDXL\\controlnet-openpose-sdxl-xinsir.safetensors"
POSE_LABELS = {
    "frontal": "Frontal", "tres_cuartos": "3/4", "perfil": "Perfil",
    "brazos_cruzados": "Brazos cruzados", "caminando": "Caminando",
    "sentado": "Sentado", "saludando": "Saludando", "retrato": "Retrato (primer plano)",
}
# Poses con esqueleto OpenPose (cuerpo). "retrato" es especial: primer plano SIN
# ControlNet (solo IPAdapter-face), para máxima fidelidad de cara.
SKELETON_KEYS = ["frontal", "tres_cuartos", "perfil", "brazos_cruzados", "caminando", "sentado", "saludando"]
# Poses fijas del "character sheet" (set/regenerar): base frontal + cuerpo + retrato.
SHEET_SKELETONS = ["frontal", "tres_cuartos", "perfil", "brazos_cruzados", "caminando", "saludando"]
RETRATO_SUFFIX = "(close-up portrait:1.3), face, head and shoulders, looking at viewer, upper body"


def _gender_dir(gender: str) -> Path:
    return POSE_LIB / (gender if gender in ("hombre", "mujer") else "mujer")


def _list_poses(gender: str = "mujer") -> list:
    d = _gender_dir(gender)
    out = []
    if d.exists():
        for k in SKELETON_KEYS:
            if (d / f"{k}.png").exists():
                out.append({"key": k, "label": POSE_LABELS[k]})
    out.append({"key": "retrato", "label": POSE_LABELS["retrato"]})  # siempre disponible
    return out


def _upload_pose(gender: str, key: str) -> Optional[str]:
    """Sube el esqueleto (del género indicado) a la carpeta input de ComfyUI."""
    p = _gender_dir(gender) / f"{key}.png"
    if not p.exists():
        return None
    up = requests.post(f"{COMFY_URL}/upload/image",
                       files={"image": (f"pose_{gender}_{key}.png", p.read_bytes(), "image/png")},
                       data={"overwrite": "true", "type": "input"}, timeout=30)
    return up.json().get("name") if up.ok else None

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
NEG = ("lowres, bad anatomy, worst quality, blurry, extra fingers, deformed, multiple people, "
       "text, watermark, (nsfw:1.6), (nude:1.6), "
       "(extra legs:1.3), (extra limbs:1.3), missing legs, malformed legs, deformed legs, "
       "fused legs, twisted legs, (floating limbs:1.2), disconnected limbs, mutated limbs, "
       "poorly drawn feet, deformed feet, bad proportions, unnatural pose")


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


def _apply_lora(g: dict, lora_filename: str, strength_model: float = 0.9,
                strength_clip: float = 1.0) -> None:
    """Inyecta un LoraLoader en un grafo ya construido y reencamina el modelo y el
    CLIP a través de él. Genérico: sirve para cualquier builder que use ["ckpt",0]
    (modelo) y ["ckpt",1] (clip). El VAE (["ckpt",2]) se deja intacto. Muta g in situ.

    Con esto, un personaje con LoRA propia (identidad píxel-perfecta) la aplica
    encima del checkpoint; el IPAdapter (PLUS FACE) y el ControlNet siguen colgando
    del modelo ya "loraizado" y refuerzan cara/pose."""
    fn = (lora_filename or "").strip()
    if not fn:
        return
    fn = fn.replace("/", "\\")   # ComfyUI espera la barra de Windows en subcarpetas
    g["charlora"] = {"class_type": "LoraLoader", "inputs": {
        "model": ["ckpt", 0], "clip": ["ckpt", 1],
        "lora_name": fn, "strength_model": float(strength_model),
        "strength_clip": float(strength_clip)}}
    for name, node in g.items():
        if name in ("ckpt", "charlora"):
            continue
        for k, v in node.get("inputs", {}).items():
            if v == ["ckpt", 0]:
                node["inputs"][k] = ["charlora", 0]
            elif v == ["ckpt", 1]:
                node["inputs"][k] = ["charlora", 1]


def _char_lora(char: dict) -> tuple:
    """(filename, trigger, strength_model) de la LoRA del personaje, o (None, '', 0.9)."""
    fn = (char.get("lora_filename") or "").strip()
    return fn or None, (char.get("lora_trigger") or "").strip(), float(char.get("lora_strength") or 0.9)


def _scene_store_path(uid: int) -> Path:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    return STORE_DIR / f"scenes_user_{uid}.json"


def _load_scenes(uid: int) -> list:
    p = _scene_store_path(uid)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_scenes(uid: int, items: list) -> None:
    _scene_store_path(uid).write_text(json.dumps(items[:200], ensure_ascii=False, indent=2), encoding="utf-8")


def _poll_and_save_scene(uid: int, entry_id: str, prompt_id: str, expected: int) -> None:
    """En un hilo de fondo: espera a que ComfyUI termine y guarda las imágenes en
    la entrada del historial. Robusto ante cierre del navegador."""
    for _ in range(400):  # ~20 min
        time.sleep(3)
        try:
            hist = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=15).json()
        except Exception:
            continue
        if prompt_id not in hist:
            continue
        outs = hist[prompt_id].get("outputs", {})
        imgs = [im.get("filename") for k in sorted(outs.keys()) for im in outs[k].get("images", [])]
        items = _load_scenes(uid)
        for e in items:
            if e.get("id") == entry_id:
                e["images"] = imgs
                e["done"] = True
                break
        _save_scenes(uid, items)
        return


def _poll_and_update_char(uid: int, char_id: str, prompt_id: str, expected: int) -> None:
    """En un hilo de fondo: espera a que ComfyUI termine el render y reemplaza las
    imágenes del personaje. Robusto ante cierre del navegador."""
    for _ in range(400):  # ~20 min
        time.sleep(3)
        try:
            hist = requests.get(f"{COMFY_URL}/history/{prompt_id}", timeout=15).json()
        except Exception:
            continue
        if prompt_id not in hist:
            continue
        outs = hist[prompt_id].get("outputs", {})
        imgs = [im.get("filename") for k in sorted(outs.keys()) for im in outs[k].get("images", [])]
        if imgs and len(imgs) >= expected:
            items = _load(uid)
            for c in items:
                if c.get("id") == char_id:
                    c["images"] = imgs
                    break
            _save(uid, items)
        return  # terminó (con o sin imágenes)


def _cn_apply(g: dict, key: str, pos_node: str, pose_input: str) -> tuple:
    """Añade un ControlNetApplyAdvanced (OpenPose) y devuelve las fuentes pos/neg."""
    g[f"pose_{key}"] = {"class_type": "LoadImage", "inputs": {"image": pose_input}}
    g[f"cn_{key}"] = {"class_type": "ControlNetApplyAdvanced", "inputs": {
        "positive": [pos_node, 0], "negative": ["neg", 0], "control_net": ["cnload", 0],
        "image": [f"pose_{key}", 0], "strength": 0.9, "start_percent": 0.0, "end_percent": 0.9}}
    return [f"cn_{key}", 0], [f"cn_{key}", 1]


def _build_graph(uid: int, desc_en: str, ckpt: str, style_suffix: str, seed: int,
                 num_poses: int, neutral_bg: bool = True, pose_names: Optional[dict] = None,
                 w: int = 832, h: int = 1216) -> dict:
    """Set de personaje. Si `pose_names` (dict {key: input_name}) está presente,
    usa ControlNet OpenPose para forzar las poses de la librería; si no, poses por
    texto (IPAdapter para la cara en ambos casos)."""
    desc = f"{desc_en}, {style_suffix}"
    ckpt = ckpt.replace("/", "\\")
    controlled = bool(pose_names)
    bg = ", (plain white background:1.4), (simple background:1.3), studio backdrop, isolated character" if neutral_bg else ""
    neg = NEG + (", detailed background, scenery, landscape, buildings, cityscape, cluttered background, environment, indoors, outdoors" if neutral_bg else "")
    # PLUS FACE (especializado en cara) para bloquear la IDENTIDAD. El atuendo
    # viene de la descripción en el texto; la pose, del ControlNet.
    g = {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["ckpt", 1]}},
        "ipload": {"class_type": "IPAdapterUnifiedLoader", "inputs": {"model": ["ckpt", 0], "preset": "PLUS FACE (portraits)"}},
    }
    if controlled:
        g["cnload"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": OPENPOSE_CN}}

    # ---- BASE (referencia; con control = pose frontal de librería) ----
    base_text = f"{'full body shot, ' if controlled else ''}{desc}, front view, looking at viewer{bg}"
    g["base_lat"] = {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}}
    g["base_pos"] = {"class_type": "CLIPTextEncode", "inputs": {"text": base_text, "clip": ["ckpt", 1]}}
    bpos, bneg = ["base_pos", 0], ["neg", 0]
    if controlled and pose_names.get("frontal"):
        bpos, bneg = _cn_apply(g, "base", "base_pos", pose_names["frontal"])
    g["base_k"] = {"class_type": "KSampler", "inputs": {"seed": seed, "steps": 26, "cfg": 6.0, "sampler_name": "euler_ancestral", "scheduler": "normal", "denoise": 1, "model": ["ckpt", 0], "positive": bpos, "negative": bneg, "latent_image": ["base_lat", 0]}}
    g["base_dec"] = {"class_type": "VAEDecode", "inputs": {"samples": ["base_k", 0], "vae": ["ckpt", 2]}}
    g["base_save"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": f"char_u{uid}_base", "images": ["base_dec", 0]}}

    # ---- POSES ----
    if controlled:
        # todas las poses del sheet (menos frontal=base) con esqueleto + retrato primer plano
        pose_items = [(k, "full body shot") for k in SHEET_SKELETONS[1:] if pose_names.get(k)]
        pose_items.append(("retrato", RETRATO_SUFFIX))
    else:
        pose_items = [(None, suffix) for (_k, suffix) in POSES[:num_poses]]

    for i, (pkey, suffix) in enumerate(pose_items):
        # PLUS FACE fuerte en cuerpo (identidad), algo menor en retrato (ya es primer plano)
        ipw = 0.85 if (controlled and pkey != "retrato") else IP_WEIGHT
        g[f"ip_{i}"] = {"class_type": "IPAdapterAdvanced", "inputs": {"model": ["ipload", 0], "ipadapter": ["ipload", 1], "image": ["base_dec", 0], "weight": ipw, "weight_type": "linear", "combine_embeds": "concat", "start_at": 0.0, "end_at": 1.0, "embeds_scaling": "V only"}}
        g[f"pos_{i}"] = {"class_type": "CLIPTextEncode", "inputs": {"text": f"{desc}, {suffix}{bg}", "clip": ["ckpt", 1]}}
        psrc, nsrc = [f"pos_{i}", 0], ["neg", 0]
        if controlled and pkey and pose_names.get(pkey):
            psrc, nsrc = _cn_apply(g, str(i), f"pos_{i}", pose_names[pkey])
        g[f"lat_{i}"] = {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}}
        g[f"k_{i}"] = {"class_type": "KSampler", "inputs": {"seed": seed + 1 + i, "steps": 26, "cfg": 6.0, "sampler_name": "euler_ancestral", "scheduler": "normal", "denoise": 1, "model": [f"ip_{i}", 0], "positive": psrc, "negative": nsrc, "latent_image": [f"lat_{i}", 0]}}
        g[f"dec_{i}"] = {"class_type": "VAEDecode", "inputs": {"samples": [f"k_{i}", 0], "vae": ["ckpt", 2]}}
        g[f"save_{i}"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": f"char_u{uid}_pose{i}", "images": [f"dec_{i}", 0]}}
    return g


class CharGenerateRequest(BaseModel):
    description: str
    style: str = "anime"
    num_poses: int = 4
    seed: Optional[int] = None
    neutral_bg: bool = True
    gender: str = "mujer"          # hombre | mujer (para las poses OpenPose)
    pose_control: bool = False     # forzar poses de la librería con ControlNet


@router.post("/generate")
def char_generate(req: CharGenerateRequest, current_user: User = Depends(get_current_user)):
    if not (req.description or "").strip():
        raise HTTPException(status_code=400, detail="Falta la descripción del personaje")
    ckpt = STYLES.get(req.style, STYLES["anime"])
    style_suffix = STYLE_SUFFIX.get(req.style, STYLE_SUFFIX["anime"])
    desc_en = _translate_character(req.description.strip(), req.neutral_bg)
    import random
    seed = req.seed if req.seed is not None else random.randint(0, 2**31 - 1)

    pose_names = None
    if req.pose_control:
        pose_names = {}
        for k in SHEET_SKELETONS:
            name = _upload_pose(req.gender, k)
            if name:
                pose_names[k] = name
        if not pose_names:
            pose_names = None  # sin librería para ese género -> texto
    # con control el set es fijo (3/4 + retrato, base frontal); sin control hasta 4
    num = max(1, min(3 if pose_names else len(POSES), int(req.num_poses)))

    wf = _build_graph(current_user.id, desc_en, ckpt, style_suffix, seed, num, req.neutral_bg, pose_names)
    try:
        r = requests.post(f"{COMFY_URL}/prompt", json={"prompt": wf}, timeout=30)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo contactar con ComfyUI: {e}")
    if not r.ok:
        raise HTTPException(status_code=400, detail=f"ComfyUI rechazó el grafo: {r.text[:500]}")
    return {"ok": True, "prompt_id": r.json().get("prompt_id"), "expected": num + 1,
            "description_en": desc_en, "style": req.style, "seed": seed,
            "gender": req.gender, "pose_control": bool(pose_names)}


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
    # recoger TODAS las imágenes de salida, ordenadas por clave de nodo
    # (base_save < save_0 < save_1… ; img_0 < img_1… ) — vale para set y escena.
    imgs = []
    outs = entry.get("outputs", {})
    for key in sorted(outs.keys()):
        for im in outs[key].get("images", []):
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
    gender: str = "mujer"


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
        "gender": req.gender,
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


def _upload_ref(char_id: str, filename: str) -> str:
    """Descarga la imagen de referencia del output de ComfyUI y la sube a su
    carpeta input (para poder usarla con LoadImage/IPAdapter)."""
    r = requests.get(f"{COMFY_URL}/view", params={"filename": filename, "type": "output", "subfolder": ""}, timeout=30)
    if not r.ok:
        raise HTTPException(status_code=404, detail="Referencia no encontrada")
    name = f"charref_{char_id}.png"
    up = requests.post(f"{COMFY_URL}/upload/image",
                       files={"image": (name, r.content, "image/png")},
                       data={"overwrite": "true", "type": "input"}, timeout=30)
    if not up.ok:
        raise HTTPException(status_code=502, detail="No se pudo subir la referencia a ComfyUI")
    return up.json().get("name", name)


def _build_scene_graph(uid: int, ref_name: str, prompt_en: str, ckpt: str,
                       style_suffix: str, seed: int, num: int, w: int, h: int,
                       pose_name: Optional[str] = None) -> dict:
    ckpt = ckpt.replace("/", "\\")
    # Con pose, el esqueleto es de cuerpo entero -> forzamos ese encuadre.
    desc = f"{'full body shot, ' if pose_name else ''}{prompt_en}, {style_suffix}"
    g = {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": NEG, "clip": ["ckpt", 1]}},
        "ref": {"class_type": "LoadImage", "inputs": {"image": ref_name}},
        "ipload": {"class_type": "IPAdapterUnifiedLoader", "inputs": {"model": ["ckpt", 0], "preset": "PLUS FACE (portraits)"}},
    }
    if pose_name:
        g["cnload"] = {"class_type": "ControlNetLoader", "inputs": {"control_net_name": OPENPOSE_CN}}
        g["pose"] = {"class_type": "LoadImage", "inputs": {"image": pose_name}}
    for i in range(num):
        # Peso alto + linear para bloquear identidad en escenas (era el fallo de coherencia).
        g[f"ip_{i}"] = {"class_type": "IPAdapterAdvanced", "inputs": {"model": ["ipload", 0], "ipadapter": ["ipload", 1], "image": ["ref", 0], "weight": 0.85, "weight_type": "linear", "combine_embeds": "concat", "start_at": 0.0, "end_at": 1.0, "embeds_scaling": "V only"}}
        g[f"pos_{i}"] = {"class_type": "CLIPTextEncode", "inputs": {"text": desc, "clip": ["ckpt", 1]}}
        pos_src, neg_src = [f"pos_{i}", 0], ["neg", 0]
        if pose_name:
            g[f"cn_{i}"] = {"class_type": "ControlNetApplyAdvanced", "inputs": {
                "positive": [f"pos_{i}", 0], "negative": ["neg", 0], "control_net": ["cnload", 0],
                "image": ["pose", 0], "strength": 0.9, "start_percent": 0.0, "end_percent": 0.9}}
            pos_src, neg_src = [f"cn_{i}", 0], [f"cn_{i}", 1]
        g[f"lat_{i}"] = {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}}
        g[f"k_{i}"] = {"class_type": "KSampler", "inputs": {"seed": seed + i, "steps": 28, "cfg": 6.0, "sampler_name": "euler_ancestral", "scheduler": "normal", "denoise": 1, "model": [f"ip_{i}", 0], "positive": pos_src, "negative": neg_src, "latent_image": [f"lat_{i}", 0]}}
        g[f"dec_{i}"] = {"class_type": "VAEDecode", "inputs": {"samples": [f"k_{i}", 0], "vae": ["ckpt", 2]}}
        g[f"img_{i}"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": f"scene_u{uid}", "images": [f"dec_{i}", 0]}}
    return g


class SceneRequest(BaseModel):
    character_id: str
    prompt: str
    num_images: int = 2
    width: int = 832
    height: int = 1216
    seed: Optional[int] = None
    pose: Optional[str] = None   # clave de la librería de poses (o None = libre)


@router.get("/poses")
def char_poses(gender: str = "mujer", current_user: User = Depends(get_current_user)):
    """Poses disponibles en la librería (esqueletos OpenPose) para el género dado."""
    return {"ok": True, "poses": _list_poses(gender)}


@router.post("/scene")
def char_scene(req: SceneRequest, current_user: User = Depends(get_current_user)):
    """Genera imágenes nuevas de un personaje guardado (misma cara vía IPAdapter)
    en la escena/pose del prompt."""
    if not (req.prompt or "").strip():
        raise HTTPException(status_code=400, detail="Falta el prompt de la escena")
    char = next((c for c in _load(current_user.id) if c.get("id") == req.character_id), None)
    if not char or not char.get("images"):
        raise HTTPException(status_code=404, detail="Personaje no encontrado")

    ckpt = STYLES.get(char.get("style", "anime"), STYLES["anime"])
    style_suffix = STYLE_SUFFIX.get(char.get("style", "anime"), STYLE_SUFFIX["anime"])
    from app.routers.video_ltx import _to_english_prompt
    prompt_en = _to_english_prompt(req.prompt.strip())
    import random
    seed = req.seed if req.seed is not None else random.randint(0, 2**31 - 1)
    num = max(1, min(4, int(req.num_images)))
    w = max(512, (int(req.width) // 8) * 8)
    h = max(512, (int(req.height) // 8) * 8)

    # Antepone la IDENTIDAD del personaje (cara/pelo/rasgos) al prompt de escena,
    # para que el modelo sepa QUIÉN es y no genere una persona genérica. El atuendo
    # de la escena (más específico) suele mandar sobre el de la descripción.
    char_desc = (char.get("description_en") or char.get("description") or "").strip()
    ref_name = _upload_ref(req.character_id, char["images"][0])
    pose_name = None
    if req.pose == "retrato":
        prompt_en = f"{RETRATO_SUFFIX}, {char_desc}, {prompt_en}"   # primer plano, sin ControlNet
    else:
        if char_desc:
            prompt_en = f"{char_desc}, {prompt_en}"
        if req.pose:
            pose_name = _upload_pose(char.get("gender", "mujer"), req.pose)
    # LoRA propia del personaje (identidad píxel-perfecta): trigger al frente del prompt.
    lora_fn, lora_trigger, lora_sm = _char_lora(char)
    if lora_fn and lora_trigger:
        prompt_en = f"{lora_trigger}, {prompt_en}"
    wf = _build_scene_graph(current_user.id, ref_name, prompt_en, ckpt, style_suffix, seed, num, w, h, pose_name)
    if lora_fn:
        _apply_lora(wf, lora_fn, lora_sm)
    try:
        r = requests.post(f"{COMFY_URL}/prompt", json={"prompt": wf}, timeout=30)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo contactar con ComfyUI: {e}")
    if not r.ok:
        raise HTTPException(status_code=400, detail=f"ComfyUI rechazó el grafo: {r.text[:500]}")
    pid = r.json().get("prompt_id")
    # Historial: crea la entrada (pendiente) y un hilo que guarda las imágenes al terminar.
    entry_id = uuid.uuid4().hex
    entry = {
        "id": entry_id, "character_id": req.character_id, "character_name": char.get("name", ""),
        "prompt": req.prompt.strip(), "prompt_en": prompt_en, "seed": seed,
        "pose": req.pose or "", "num": num, "images": [], "done": False,
        "created_at": int(time.time()),
    }
    scenes = _load_scenes(current_user.id)
    scenes.insert(0, entry)
    _save_scenes(current_user.id, scenes)
    threading.Thread(target=_poll_and_save_scene, args=(current_user.id, entry_id, pid, num), daemon=True).start()
    return {"ok": True, "prompt_id": pid, "expected": num, "prompt_en": prompt_en, "seed": seed, "entry_id": entry_id}


def _build_regen_graph(uid: int, ref_name: str, desc_en: str, ckpt: str,
                       style_suffix: str, seed: int, pose_names: dict, w: int = 832, h: int = 1216) -> dict:
    """Regenera el character sheet (frontal, 3/4, perfil + retrato) desde la
    imagen de referencia de un personaje guardado (misma cara y atuendo)."""
    desc = f"{desc_en}, {style_suffix}"
    ckpt = ckpt.replace("/", "\\")
    bg = ", (plain white background:1.4), (simple background:1.3), studio backdrop, isolated character"
    neg = NEG + ", detailed background, scenery, landscape, buildings, cityscape, environment"
    g = {
        "ckpt": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "neg": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["ckpt", 1]}},
        "ref": {"class_type": "LoadImage", "inputs": {"image": ref_name}},
        "ipload": {"class_type": "IPAdapterUnifiedLoader", "inputs": {"model": ["ckpt", 0], "preset": "PLUS FACE (portraits)"}},
        "cnload": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": OPENPOSE_CN}},
    }
    items = [(k, "full body shot") for k in SHEET_SKELETONS if pose_names.get(k)]
    items.append(("retrato", RETRATO_SUFFIX))
    for i, (pkey, suffix) in enumerate(items):
        ipw = IP_WEIGHT if pkey == "retrato" else 0.85   # PLUS FACE fuerte = identidad
        g[f"ip_{i}"] = {"class_type": "IPAdapterAdvanced", "inputs": {"model": ["ipload", 0], "ipadapter": ["ipload", 1], "image": ["ref", 0], "weight": ipw, "weight_type": "linear", "combine_embeds": "concat", "start_at": 0.0, "end_at": 1.0, "embeds_scaling": "V only"}}
        g[f"pos_{i}"] = {"class_type": "CLIPTextEncode", "inputs": {"text": f"{desc}, {suffix}{bg}", "clip": ["ckpt", 1]}}
        psrc, nsrc = [f"pos_{i}", 0], ["neg", 0]
        if pkey != "retrato" and pose_names.get(pkey):
            g[f"pose_{i}"] = {"class_type": "LoadImage", "inputs": {"image": pose_names[pkey]}}
            g[f"cn_{i}"] = {"class_type": "ControlNetApplyAdvanced", "inputs": {"positive": [f"pos_{i}", 0], "negative": ["neg", 0], "control_net": ["cnload", 0], "image": [f"pose_{i}", 0], "strength": 0.9, "start_percent": 0.0, "end_percent": 0.9}}
            psrc, nsrc = [f"cn_{i}", 0], [f"cn_{i}", 1]
        g[f"lat_{i}"] = {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}}
        g[f"k_{i}"] = {"class_type": "KSampler", "inputs": {"seed": seed + i, "steps": 26, "cfg": 6.0, "sampler_name": "euler_ancestral", "scheduler": "normal", "denoise": 1, "model": [f"ip_{i}", 0], "positive": psrc, "negative": nsrc, "latent_image": [f"lat_{i}", 0]}}
        g[f"dec_{i}"] = {"class_type": "VAEDecode", "inputs": {"samples": [f"k_{i}", 0], "vae": ["ckpt", 2]}}
        g[f"img_{i}"] = {"class_type": "SaveImage", "inputs": {"filename_prefix": f"regen_u{uid}", "images": [f"dec_{i}", 0]}}
    return g


class RegenRequest(BaseModel):
    seed: Optional[int] = None
    gender: Optional[str] = None   # hombre | mujer (para elegir los esqueletos)


@router.post("/{char_id}/regenerate-poses")
def char_regen(char_id: str, req: RegenRequest, current_user: User = Depends(get_current_user)):
    """Regenera las imágenes de un personaje guardado con el juego de poses nuevo
    (frontal, 3/4, perfil, retrato), manteniendo cara y atuendo."""
    char = next((c for c in _load(current_user.id) if c.get("id") == char_id), None)
    if not char or not char.get("images"):
        raise HTTPException(status_code=404, detail="Personaje no encontrado")
    ckpt = STYLES.get(char.get("style", "anime"), STYLES["anime"])
    style_suffix = STYLE_SUFFIX.get(char.get("style", "anime"), STYLE_SUFFIX["anime"])
    gender = req.gender if req.gender in ("hombre", "mujer") else char.get("gender", "mujer")
    # persiste el género elegido en el personaje
    if char.get("gender") != gender:
        items = _load(current_user.id)
        for c in items:
            if c.get("id") == char_id:
                c["gender"] = gender
                break
        _save(current_user.id, items)
    desc_en = char.get("description_en") or _translate_character(char.get("description", ""), True)
    import random
    seed = req.seed if req.seed is not None else random.randint(0, 2**31 - 1)

    # LoRA propia del personaje: trigger al frente de la descripción.
    lora_fn, lora_trigger, lora_sm = _char_lora(char)
    if lora_fn and lora_trigger:
        desc_en = f"{lora_trigger}, {desc_en}"

    ref_name = _upload_ref(char_id, char["images"][0])
    pose_names = {}
    for k in SHEET_SKELETONS:
        n = _upload_pose(gender, k)
        if n:
            pose_names[k] = n
    wf = _build_regen_graph(current_user.id, ref_name, desc_en, ckpt, style_suffix, seed, pose_names)
    if lora_fn:
        _apply_lora(wf, lora_fn, lora_sm)
    try:
        r = requests.post(f"{COMFY_URL}/prompt", json={"prompt": wf}, timeout=30)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo contactar con ComfyUI: {e}")
    if not r.ok:
        raise HTTPException(status_code=400, detail=f"ComfyUI rechazó el grafo: {r.text[:500]}")
    pid = r.json().get("prompt_id")
    expected = len(pose_names) + 1
    # Poll de fondo: actualiza las imágenes del personaje cuando ComfyUI termine,
    # aunque el navegador cierre o se rinda el sondeo del frontend.
    threading.Thread(target=_poll_and_update_char, args=(current_user.id, char_id, pid, expected), daemon=True).start()
    return {"ok": True, "prompt_id": pid, "expected": expected}


class UpdateImagesRequest(BaseModel):
    images: List[str]


@router.post("/{char_id}/update-images")
def char_update_images(char_id: str, req: UpdateImagesRequest, current_user: User = Depends(get_current_user)):
    """Reemplaza las imágenes de un personaje (tras regenerar poses)."""
    items = _load(current_user.id)
    found = False
    for c in items:
        if c.get("id") == char_id:
            c["images"] = req.images
            found = True
            break
    if not found:
        raise HTTPException(status_code=404, detail="Personaje no encontrado")
    _save(current_user.id, items)
    return {"ok": True}


class CharLoraRequest(BaseModel):
    lora_filename: Optional[str] = None   # None o "" = quitar la LoRA
    lora_trigger: str = ""
    lora_strength: float = 0.9


@router.post("/{char_id}/lora")
def char_set_lora(char_id: str, req: CharLoraRequest, current_user: User = Depends(get_current_user)):
    """Asigna (o quita) una LoRA propia al personaje. Con LoRA asignada, las
    escenas y la regeneración del sheet la aplican para identidad píxel-perfecta,
    anteponiendo el trigger word al prompt."""
    items = _load(current_user.id)
    entry = None
    for c in items:
        if c.get("id") == char_id:
            fn = (req.lora_filename or "").strip()
            c["lora_filename"] = fn
            c["lora_trigger"] = (req.lora_trigger or "").strip()
            c["lora_strength"] = float(req.lora_strength or 0.9)
            entry = c
            break
    if entry is None:
        raise HTTPException(status_code=404, detail="Personaje no encontrado")
    _save(current_user.id, items)
    return {"ok": True, "entry": entry}


@router.get("/scenes")
def char_scenes(current_user: User = Depends(get_current_user)):
    """Historial de imágenes generadas (pestaña Imágenes), más recientes primero."""
    return {"ok": True, "items": _load_scenes(current_user.id)}


@router.delete("/scenes/{entry_id}")
def char_scene_delete(entry_id: str, current_user: User = Depends(get_current_user)):
    """Borra una entrada del historial (los ficheros en disco de ComfyUI no se tocan)."""
    items = [x for x in _load_scenes(current_user.id) if x.get("id") != entry_id]
    _save_scenes(current_user.id, items)
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
