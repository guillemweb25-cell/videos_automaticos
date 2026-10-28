#!/usr/bin/env python
"""Genera un workflow MOSS-Image turbo por canal a partir de su workflow SDXL por defecto,
conservando su bloque de estilo (pasado a lenguaje natural, sin pesos "(...:1.3)") y añadiendo
en positivo lo que en turbo no puede ir en el negativo (manos, ropa, sin texto).

    docker exec videos_automaticos-api-1 python scripts/make_moss_workflows.py            # muestra
    docker exec videos_automaticos-api-1 python scripts/make_moss_workflows.py --apply    # escribe y
        pone cada canal con su MOSS-<nombre>.json como default_workflow
Ver docs/moss-image-guia.md.
"""
import json
import os
import re
import sys
from pathlib import Path

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from app.database import SessionLocal          # noqa: E402
from app.models.channel import Channel          # noqa: E402

WF_DIR = Path("/app/workflows") if Path("/app/workflows").exists() else Path("workflows")
BASE = json.loads((WF_DIR / "MOSS-Turbo.json").read_text(encoding="utf-8"))
# Palabras de "calidad" estilo SD que en MOSS no aportan (docs/moss-image-guia.md §5).
FILLER = re.compile(r"\b(masterpiece|best quality|high quality|highres|8k|4k|uhd|ultra[- ]detailed|"
                    r"highly detailed|hyper[- ]detailed|award[- ]winning|trending on artstation|resolution)\b", re.I)
SHOWS_TEXT = re.compile(r"\b(numbers?|digits?|letters?|hebrew|text|inscriptions?|glyphs?)\b", re.I)


def positive_text(wf: dict) -> str:
    for node in wf.values():
        if node.get("class_type") == "CLIPTextEncode" and node.get("_meta", {}).get("title", "").lower() == "positive":
            return node["inputs"].get("text", "")
    for node in wf.values():
        if node.get("class_type") == "CLIPTextEncode":
            return node["inputs"].get("text", "")
    return ""


def natural(style: str) -> str:
    s = re.sub(r"\(([^()]*?):\s*[\d.]+\)", r"\1", style)   # (a, b:1.3) -> a, b
    s = s.replace("(", "").replace(")", "")
    s = FILLER.sub("", s)
    parts = [p.strip(" .") for p in s.split(",")]
    parts = [p for p in parts if p]
    seen, out = set(), []
    for p in parts:
        if p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return ", ".join(out)


def moss_text(style: str, channel_style: str = "") -> str:
    base = natural(style)
    # En condicional: decirle "toda persona..." le invita a meter personas en cualquier escena.
    tail = ("Show people only if the scene describes them; if anyone appears, they have realistic anatomy "
            "with correctly formed hands and wear modest, fully covering clothing appropriate to the era.")
    # Canales que muestran números/letras (Grabovoi, cábala): sin "no text".
    if SHOWS_TEXT.search(style) or SHOWS_TEXT.search(channel_style or ""):
        tail += " No watermark, no frame."
    else:
        tail += " No text, no letters, no watermark, no frame."
    return (f"{base[0].upper()}{base[1:]}. " if base else "") + tail


def main(apply: bool):
    db = SessionLocal()
    try:
        for ch in db.query(Channel).order_by(Channel.id).all():
            src_name = ch.default_workflow
            if not src_name or src_name.startswith("MOSS-"):
                print(f"[{ch.id}] {ch.name}: sin workflow SDXL ({src_name}) -> MOSS-Turbo.json")
                if apply and not src_name and (ch.default_style or "") != "repost":
                    ch.default_workflow = "MOSS-Turbo.json"
                continue
            src = WF_DIR / src_name
            if not src.exists():
                print(f"[{ch.id}] {ch.name}: no existe {src_name}, se omite")
                continue
            style = positive_text(json.loads(src.read_text(encoding="utf-8")))
            name = "MOSS-" + re.sub(r"-Ultra$", "", src.stem) + ".json"
            text = moss_text(style, ch.image_style_prompt or "")
            print(f"[{ch.id}] {ch.name}: {src_name} -> {name}\n    {text}\n")
            if apply:
                wf = json.loads(json.dumps(BASE))
                wf["4"]["inputs"]["text"] = text
                wf["9"]["inputs"]["filename_prefix"] = "moss_" + re.sub(r"\W+", "_", src.stem.lower())
                (WF_DIR / name).write_text(json.dumps(wf, indent=2, ensure_ascii=False), encoding="utf-8")
                ch.default_workflow = name
        if apply:
            db.commit()
            print("Aplicado.")
    finally:
        db.close()


if __name__ == "__main__":
    main("--apply" in sys.argv)
