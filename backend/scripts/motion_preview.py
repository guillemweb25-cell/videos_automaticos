#!/usr/bin/env python
"""Preview de un render motion (HyperFrames) sobre un vídeo YA generado (audio + imágenes),
sin tocar su final_video.mp4. Sirve para iterar el diseño con vídeos reales.

Escribe output/preview_<estilo>.mp4. El plan de escenas se calcula para el vídeo entero y se
cachea (motion_plan_<estilo>.json), así el render final usa el mismo plan.

Run it INSIDE the api container (it needs DB + cache access), con el servicio motion
del host arrancado (motion/start_motion.bat):

    docker exec videos_automaticos-api-1 python scripts/motion_preview.py 356 --style documental --secs 90 --qr
    docker exec videos_automaticos-api-1 python scripts/motion_preview.py 356 --style documental --full --qr
"""
import os
import sys
import json
import random
import argparse
from pathlib import Path

# Make `import app.*` work no matter the current working directory.
APP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from app.database import SessionLocal                                   # noqa: E402
from app.models.video import Video                                      # noqa: E402
from app.routers.video_gen import _collect_render_inputs, _render_motion  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video_id", type=int)
    ap.add_argument("--style", default="documental", choices=["motion", "documental"])
    ap.add_argument("--secs", type=float, default=90.0, help="duración del preview")
    ap.add_argument("--full", action="store_true", help="vídeo entero (con tarjetas finales)")
    ap.add_argument("--qr", action="store_true", help="incluir el QR de afiliado del canal")
    ap.add_argument("--no-subs", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == args.video_id).first()
        if not video:
            sys.exit(f"vídeo {args.video_id} no encontrado")
        base_dir = Path(video.base_dir)
        durations = json.loads((base_dir / "paragraphs_durations.json").read_text())
        image_paths, durs, audio_paths = _collect_render_inputs(base_dir, durations)
        music = sorted((base_dir.parent / "music").glob("*.mp3"))
        out_path = base_dir / "output" / f"preview_{args.style}{'' if args.full else '_' + str(int(args.secs))}.mp4"
        _render_motion(video, db, image_paths, durs, audio_paths, out_path,
                       (video.width or 1024, video.height or 1792),
                       random.choice(music) if music else None, None,
                       subtitles=not args.no_subs, style=args.style, show_qr=args.qr,
                       limit_secs=None if args.full else args.secs)
        print(out_path)
    finally:
        db.close()


if __name__ == "__main__":
    main()
