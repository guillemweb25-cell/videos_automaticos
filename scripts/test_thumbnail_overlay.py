"""
Quick visual test for the thumbnail text overlay.

Generates a synthetic warm-toned background and stamps the Jesús-channel
3-line layout (label / TÍTULO / subtítulo) on it. Use to iterate on
typography / gradient / positioning without spinning up the whole pipeline.

Usage:
    python scripts/test_thumbnail_overlay.py "EL DIA QUE TODO CAMBIO ... PENTECOSTES ... el Espíritu Santo cambió el mundo"
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from PIL import Image, ImageDraw

from app.services.image_engine import ImageEngine


def make_warm_background(size=(1024, 1792)) -> Image.Image:
    """Cheap radial-ish warm background (orange center → dark edges)."""
    w, h = size
    bg = Image.new("RGB", (w, h), (15, 10, 5))
    cx, cy = w / 2, h / 2
    max_r = (w**2 + h**2) ** 0.5 / 2
    pixels = bg.load()
    for y in range(h):
        for x in range(w):
            dx, dy = (x - cx) / max_r, (y - cy) / max_r
            d = (dx * dx + dy * dy) ** 0.5
            t = max(0.0, 1.0 - d * 1.4)
            r = int(20 + 200 * t)
            g = int(15 + 120 * t)
            b = int(5 + 30 * t)
            pixels[x, y] = (r, g, b)
    return bg


def main():
    text = sys.argv[1] if len(sys.argv) > 1 else "EL DIA QUE TODO CAMBIO ... PENTECOSTES ... el Espíritu Santo cambió el mundo"

    out_dir = ROOT / "scripts" / "thumbnail_test_output"
    out_dir.mkdir(parents=True, exist_ok=True)

    bg = make_warm_background((1024, 1792))
    out_path = out_dir / "test_thumbnail.png"
    bg.save(out_path)

    engine = ImageEngine.__new__(ImageEngine)  # bypass __init__ (no API keys needed)
    engine._apply_thumbnail_text_overlay(out_path, text, channel_name="Mensajes de Jesús")

    print(f"Wrote {out_path} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
