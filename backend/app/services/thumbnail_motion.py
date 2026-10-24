"""
Miniaturas con HyperFrames: la imagen sale de ComfyUI SIN texto y la tipografía se compone en
HTML/CSS (fuentes reales, degradados, sombras, bandas inclinadas) y se captura como PNG con
`hyperframes snapshot` en el servicio motion del host.

El texto es el hook de siempre: "LÍNEA 1... LÍNEA 2" ("..." = salto). Con *palabra* se
destaca en color dentro de una línea.

Plantillas:
  epico      → imagen a sangre, texto en el lado libre: línea 1 blanca, línea 2 dorada enorme
               (la guía de estilo del canal Jesús).
  documental → coherente con el vídeo documental: fondo oscuro, la imagen como polaroid
               grande e inclinada, titular condensado con palabra destacada.
  impacto    → dos imágenes partidas en diagonal y la línea 2 sobre una banda de color
               inclinada (tipo "4 BOMBAS / 0 EXPLOSIONES").
"""

import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.services.motion_engine import FONTS_DIR, _esc

TEMPLATES = ("epico", "documental", "impacto")


def split_hook(hook: str) -> Tuple[str, str]:
    """'LA COLUMNA... ¿MILAGRO?' → ('LA COLUMNA', '¿MILAGRO?'); también 'PANTEÓN: HUESOS…'.
    Sin separador, todo es la línea 2 (la grande)."""
    parts = [p.strip(" .:") for p in re.split(r"\.\.\.|…|:", hook or "", maxsplit=1)]
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    return "", (hook or "").strip()


def render_thumbnail(project_dir: Path, out_png: Path) -> Path:
    """Captura la composición como PNG en el servicio motion del host (POST /snapshot)."""
    import os
    import requests
    base = os.getenv("MOTION_URL", "http://host.docker.internal:8610").rstrip("/")
    r = requests.post(f"{base}/snapshot", json={
        "projectDir": project_dir.resolve().as_posix(), "output": out_png.resolve().as_posix(), "at": 0.5,
    }, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"Miniatura HyperFrames falló: {r.text[:500]}")
    return out_png


def _balanced_rows(text: str, n: int) -> List[str]:
    """Parte un texto en (como mucho) n líneas eligiendo los cortes que dejan la línea más larga
    lo más corta posible (sin perder palabras)."""
    from itertools import combinations
    words = text.split()
    n = max(1, min(n, len(words)))
    best, best_len = [text], len(text)
    for cuts in combinations(range(1, len(words)), n - 1):
        bounds = (0,) + cuts + (len(words),)
        rows = [" ".join(words[a:b]) for a, b in zip(bounds, bounds[1:])]
        longest = max(len(r.replace("*", "")) for r in rows)
        if longest < best_len:
            best, best_len = rows, longest
    return best


def _rich(text: str) -> str:
    parts = re.split(r"\*([^*]+)\*", text or "")
    return "".join(f"<em>{_esc(p)}</em>" if i % 2 else _esc(p) for i, p in enumerate(parts))


def build_thumbnail(project_dir: Path, images: List[Path], hook: str, template: str = "epico",
                    theme: Optional[Dict] = None, size: Tuple[int, int] = (1280, 720),
                    char_side: str = "right", kicker: str = "") -> Path:
    """Escribe project_dir/index.html. images[0] = imagen principal (images[1] para 'impacto').
    char_side = dónde está el personaje en la imagen (el texto va al lado contrario)."""
    theme = theme or {"bg": "#100c0a", "text": "#F4EDE2", "accent": "#E2B24C", "accent2": "#C9483B"}
    W, H = size
    u = H / 100.0
    assets = project_dir / "assets"
    if project_dir.exists():
        shutil.rmtree(project_dir)
    assets.mkdir(parents=True)
    for f in ("BebasNeue-Regular.ttf", "Anton-Regular.ttf", "Poppins-Bold.ttf"):
        if (FONTS_DIR / f).exists():
            shutil.copy2(FONTS_DIR / f, assets / f)
    srcs = []
    for k, p in enumerate(images[:2]):
        name = f"img{k}{p.suffix.lower()}"
        shutil.copy2(p, assets / name)
        srcs.append(f"assets/{name}")

    line1, line2 = split_hook(hook)
    T, A, A2, BG = theme["text"], theme["accent"], theme["accent2"], theme["bg"]
    text_left = char_side != "left"   # personaje a la derecha → texto a la izquierda
    side = "left" if text_left else "right"
    vertical = H > W   # miniatura/portada de un Short (1080x1920)
    # Tamaño de letra según lo largo que sea cada línea (que quepa en ~55% del ancho; en
    # vertical el texto ocupa casi todo el ancho).
    def fit(text: str, base: float, width_frac: float, ratio: float) -> float:
        n = max(1, len(text.replace("*", "")))
        if vertical:
            width_frac, base = 0.86, base * 0.62
        return min(base, (W * width_frac) / (n * ratio))

    if template == "documental":
        title = (line1 + " " + line2).strip()
        words = title.split()
        if "*" not in title and words:
            words[-1] = f"*{words[-1]}*"
            title = " ".join(words)
        # Reparto en 2-3 líneas equilibradas.
        if vertical:  # más ancho disponible: menos líneas
            rows = _balanced_rows(title, 3 if len(title) > 18 else 2)
        else:
            rows = _balanced_rows(title, 4 if len(title) > 24 else (3 if len(title) > 14 else 2))
        fs = fit(max(rows, key=len), 24 * u, 0.42, 0.44)
        body = f"""
<div class="pol"><div class="frame"><img src="{srcs[0]}" alt=""></div></div>
<div class="txt">{f'<div class="kick">{_esc(kicker)}</div>' if kicker else ''}
  <div class="t" style="font-size:{fs:.0f}px">{''.join(f'<div>{_rich(r)}</div>' for r in rows)}</div></div>"""
        css = f"""
#root {{ background: radial-gradient(ellipse at 70% 50%, #2a1d14 0%, {BG} 65%); }}
.pol {{ position: absolute; {'right' if text_left else 'left'}: {W * 0.04:.0f}px; top: {H * 0.1:.0f}px;
  width: {W * 0.5:.0f}px; transform: rotate({2.5 if text_left else -2.5}deg); }}
.frame {{ background: #F3EEE6; padding: {u * 1.6:.0f}px; box-shadow: 0 {u * 2:.0f}px {u * 5:.0f}px rgba(0,0,0,0.7); }}
.frame img {{ width: 100%; height: {H * 0.74:.0f}px; object-fit: cover; display: block; }}
.txt {{ position: absolute; {side}: {W * 0.05:.0f}px; width: {W * 0.46:.0f}px; top: 0; bottom: 0;
  display: flex; flex-direction: column; justify-content: center; }}
.kick {{ font-family: "Poppins"; font-size: {u * 4.2:.0f}px; color: {A2}; letter-spacing: 0.08em;
  text-transform: uppercase; margin-bottom: {u * 1.5:.0f}px; }}
.t {{ font-family: "Bebas"; line-height: 0.92; color: {T}; text-shadow: 0 {u * 0.8:.0f}px {u * 2.5:.0f}px rgba(0,0,0,0.8); }}
"""
    elif template == "impacto":
        f1 = fit(line1, 17 * u, 0.62, 0.42)
        f2 = fit(line2, 19 * u, 0.62, 0.45)
        # Partida en diagonal SOLO si se pasan dos imágenes a propósito; si no, una a sangre.
        if len(srcs) > 1:
            visual = (f'<div class="half a"><img src="{srcs[0]}" alt=""></div>'
                      f'<div class="half b"><img src="{srcs[1]}" alt=""></div><div class="seam"></div>')
        else:
            visual = f'<div class="half"><img src="{srcs[0]}" alt=""></div><div class="ishade"></div>'
        body = f"""
{visual}
<div class="txt">
  {f'<div class="l1" style="font-size:{f1:.0f}px">{_rich(line1)}</div>' if line1 else ''}
  <div class="band"><span class="l2" style="font-size:{f2:.0f}px">{_rich(line2)}</span></div>
</div>"""
        css = f"""
.half {{ position: absolute; inset: 0; }}
.half img {{ width: 100%; height: 100%; object-fit: cover; }}
.half.a {{ clip-path: polygon(0 0, 66% 0, 50% 100%, 0 100%); }}
.half.b {{ clip-path: polygon(66% 0, 100% 0, 100% 100%, 50% 100%); }}
.half.b img {{ filter: saturate(1.15) contrast(1.05); }}
.ishade {{ position: absolute; inset: 0; background: linear-gradient(0deg, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.2) 45%, rgba(0,0,0,0) 70%); }}
.seam {{ position: absolute; inset: 0; background: {A};
  clip-path: polygon(65.4% 0, 66.6% 0, 50.6% 100%, 49.4% 100%); }}
.txt {{ position: absolute; {side}: {W * 0.04:.0f}px; right: {W * 0.04:.0f}px; bottom: {H * 0.11:.0f}px;
  display: flex; flex-direction: column; align-items: {'flex-start' if text_left else 'flex-end'}; }}
.l1 {{ font-family: "Anton"; color: #fff; line-height: 1; letter-spacing: 0.01em;
  -webkit-text-stroke: {u * 0.45:.1f}px #000; paint-order: stroke fill;
  text-shadow: 0 {u * 0.8:.0f}px {u * 2:.0f}px rgba(0,0,0,0.9); transform: rotate(-3deg); }}
.band {{ background: linear-gradient(90deg, rgba(0,0,0,0.35), rgba(0,0,0,0) 45%, rgba(0,0,0,0.35)), {A2}; padding: {u * 0.6:.0f}px {u * 3:.0f}px;
  transform: rotate(-3deg) skewX(-6deg); margin-top: {u * 1.2:.0f}px; box-shadow: 0 {u:.0f}px {u * 3:.0f}px rgba(0,0,0,0.6); }}
.l2 {{ display: inline-block; font-family: "Anton"; line-height: 1.05; transform: skewX(6deg);
  background: linear-gradient(180deg, #FFF3B0 0%, {A} 55%, #C98A1B 100%); -webkit-background-clip: text; background-clip: text;
  color: transparent; filter: drop-shadow(0 {u * 0.5:.0f}px 0 #3a0d08); }}
"""
    else:  # epico
        rows2 = _balanced_rows(line2, 2) if len(line2) > 14 else [line2]
        f1 = fit(line1, 15 * u, 0.5, 0.42)
        f2 = fit(max(rows2, key=len), 30 * u, 0.55, 0.42)
        grad_dir = "90deg" if text_left else "270deg"
        body = f"""
<div class="full"><img src="{srcs[0]}" alt=""></div>
<div class="shade"></div>
<div class="txt">
  {f'<div class="kick">{_esc(kicker)}</div>' if kicker else ''}
  {f'<div class="l1" style="font-size:{f1:.0f}px">{_rich(line1)}</div>' if line1 else ''}
  <div class="l2" style="font-size:{f2:.0f}px">{"".join(f"<div>{_rich(r)}</div>" for r in rows2)}</div>
</div>"""
        css = f"""
.full {{ position: absolute; inset: 0; }}
.full img {{ width: 100%; height: 100%; object-fit: cover; }}
.shade {{ position: absolute; inset: 0; background: linear-gradient({grad_dir}, rgba(8,6,5,0.95) 0%, rgba(8,6,5,0.82) 34%, rgba(8,6,5,0) 64%),
  radial-gradient(ellipse at 50% 120%, rgba(0,0,0,0.5), rgba(0,0,0,0) 60%); }}
.txt {{ position: absolute; {side}: {W * 0.05:.0f}px; width: {W * 0.55:.0f}px; top: {H * 0.12:.0f}px; bottom: {H * 0.12:.0f}px;
  display: flex; flex-direction: column; justify-content: center; align-items: {'flex-start' if text_left else 'flex-end'};
  text-align: {'left' if text_left else 'right'}; }}
.kick {{ font-family: "Poppins"; font-size: {u * 4:.0f}px; color: #fff; letter-spacing: 0.1em; text-transform: uppercase;
  margin-bottom: {u:.0f}px; text-shadow: 0 2px 8px rgba(0,0,0,0.9); }}
.l1 {{ font-family: "Bebas"; color: #fff; line-height: 0.95; text-shadow: 0 {u * 0.6:.0f}px {u * 2:.0f}px rgba(0,0,0,0.95); }}
.l2 {{ font-family: "Bebas"; line-height: 0.9; margin-top: {u * 0.5:.0f}px;
  background: linear-gradient(180deg, #FFF0B8 0%, {A} 50%, #B9781A 100%); -webkit-background-clip: text; background-clip: text;
  color: transparent; filter: drop-shadow(0 {u * 0.6:.0f}px {u * 1.5:.0f}px rgba(0,0,0,0.85)) drop-shadow(0 0 {u * 3:.0f}px rgba(226,178,76,0.35)); }}
"""

    if vertical:
        # Mismo HTML, otra disposición: el texto va abajo y centrado (portada de Short).
        css += {
            "documental": f"""
.pol {{ left: {W * 0.08:.0f}px; right: auto; top: {H * 0.07:.0f}px; width: {W * 0.84:.0f}px; transform: rotate(2deg); }}
.frame img {{ height: {H * 0.42:.0f}px; }}
.txt {{ left: {W * 0.08:.0f}px; right: {W * 0.08:.0f}px; width: auto; top: {H * 0.56:.0f}px; bottom: {H * 0.08:.0f}px;
  justify-content: flex-start; }}
""",
            "impacto": f"""
.ishade {{ background: linear-gradient(0deg, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.3) 40%, rgba(0,0,0,0) 62%); }}
.txt {{ left: {W * 0.05:.0f}px; right: {W * 0.05:.0f}px; bottom: {H * 0.17:.0f}px; align-items: center; text-align: center; }}
""",
            "epico": f"""
.shade {{ background: linear-gradient(0deg, rgba(8,6,5,0.95) 0%, rgba(8,6,5,0.7) 32%, rgba(8,6,5,0) 58%); }}
.txt {{ left: {W * 0.07:.0f}px; right: {W * 0.07:.0f}px; width: auto; top: auto; bottom: {H * 0.15:.0f}px;
  justify-content: flex-end; align-items: center; text-align: center; }}
""",
        }[template]

    index = project_dir / "index.html"
    index.write_text(f"""<!doctype html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={W}, height={H}">
<style>
@font-face {{ font-family: "Bebas"; src: url("assets/BebasNeue-Regular.ttf"); }}
@font-face {{ font-family: "Anton"; src: url("assets/Anton-Regular.ttf"); }}
@font-face {{ font-family: "Poppins"; src: url("assets/Poppins-Bold.ttf"); font-weight: 700; }}
html, body {{ margin: 0; background: {BG}; }}
#root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: {BG}; }}
em {{ font-style: normal; color: {A}; }}
{css}
</style>
</head>
<body>
<div id="root" data-composition-id="thumb" data-start="0" data-duration="1" data-width="{W}" data-height="{H}" data-no-timeline>
{body}
</div>
</body>
</html>
""", encoding="utf-8")
    return index
