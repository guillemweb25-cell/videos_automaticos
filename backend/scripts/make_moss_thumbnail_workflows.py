#!/usr/bin/env python
"""Pasa a MOSS-Image los workflows de miniatura propios de canal (workflows/<slug>-thumbnail.json),
guardando el SDXL original como <slug>-thumbnail-sdxl.json. Conserva el bloque de estilo
(en lenguaje natural) igual que make_moss_workflows.py.

    docker exec videos_automaticos-api-1 python scripts/make_moss_thumbnail_workflows.py [--apply]
"""
import json
import os
import re
import shutil
import sys

APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, APP_DIR)
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(APP_DIR)

from app.core.utils import slugify                       # noqa: E402
from app.database import SessionLocal                     # noqa: E402
from app.models.channel import Channel                    # noqa: E402
from make_moss_workflows import BASE, WF_DIR, moss_text, positive_text  # noqa: E402


def main(apply: bool):
    db = SessionLocal()
    try:
        for ch in db.query(Channel).order_by(Channel.id).all():
            path = WF_DIR / f"{slugify(ch.name)}-thumbnail.json"
            if not path.exists():
                continue
            wf = json.loads(path.read_text(encoding="utf-8"))
            if any(n.get("class_type") == "EmptyFlux2LatentImage" for n in wf.values()):
                print(f"[{ch.id}] {path.name}: ya es MOSS")
                continue
            text = moss_text(positive_text(wf), ch.image_style_prompt or "")
            print(f"[{ch.id}] {path.name} -> MOSS\n    {text}\n")
            if apply:
                shutil.copy2(path, path.with_name(path.stem + "-sdxl.json"))
                new = json.loads(json.dumps(BASE))
                new["4"]["inputs"]["text"] = text
                new["9"]["inputs"]["filename_prefix"] = "moss_thumb_" + re.sub(r"\W+", "_", slugify(ch.name))
                path.write_text(json.dumps(new, indent=2, ensure_ascii=False), encoding="utf-8")
        if apply:
            print("Aplicado (copia SDXL en *-thumbnail-sdxl.json).")
    finally:
        db.close()


if __name__ == "__main__":
    main("--apply" in sys.argv)
