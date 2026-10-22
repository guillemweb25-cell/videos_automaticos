"""
MotionEngine: render "motion" (HyperFrames) — alternativa dinámica al slideshow Ken Burns.

Flujo:
  1. plan_scenes()        → el LLM "director" elige un layout por imagen (full / split /
                            code / list / quote) y extrae el texto clave (titular, código,
                            viñetas). Si no hay LLM, heurística.
  2. build_composition()  → genera un proyecto HyperFrames (index.html + assets/) con
                            plantillas fijas: el LLM NO escribe HTML, solo rellena huecos.
                            Incluye subtítulos animados palabra a palabra.
  3. render_project()     → pide el render al servicio `motion` (Node + HyperFrames) por
                            HTTP y va volcando el progreso en render_progress.txt.
  4. mux_audio()          → mezcla voz + música, loudnorm y overlay con FFmpeg (igual que
                            el slideshow), así el audio no depende de HyperFrames.

El vídeo de HyperFrames sale SIN audio; el audio se pone siempre en el paso 4.
"""

import html
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests

FONTS_DIR = Path(__file__).parent.parent / "fonts"
LAYOUTS = ("full", "split", "code", "list", "quote")
TRANSITIONS = ("fade", "slide", "wipe", "zoom")
TRANSITION_SECS = 0.5

# Temas por canal (clave = slug que contenga el nombre de la carpeta del canal).
# accent = color de la palabra activa y de los titulares.
THEMES = {
    "default": {"accent": "#FFD23F", "accent_text": "#111111", "panel": "rgba(10,10,20,0.62)",
                "title_font": "Anton", "body_font": "Poppins"},
    "grabovoi": {"accent": "#F5C542", "accent_text": "#1A0F2E", "panel": "rgba(26,15,46,0.66)",
                 "title_font": "Anton", "body_font": "Poppins"},
}


def theme_for_channel(channel_folder: str) -> Dict:
    folder = (channel_folder or "").lower()
    for key, theme in THEMES.items():
        if key != "default" and key in folder:
            return theme
    return THEMES["default"]


# ─── 1. Director de escenas ─────────────────────────────────────────

def _heuristic_plan(paragraphs: List[Dict]) -> List[List[Dict]]:
    """Sin LLM: alterna full/split y saca un titular corto de la primera frase."""
    plan = []
    for p in paragraphs:
        n = p["n_images"]
        first = re.split(r"[.!?]", p["text"].strip())[0]
        headline = " ".join(first.split()[:6])
        scenes = []
        for i in range(n):
            layout = "split" if (i % 3 == 1 and i + 1 < n) else "full"
            scenes.append({"layout": layout, "headline": headline if i == 0 else ""})
        plan.append(scenes)
    return plan


def plan_scenes(paragraphs: List[Dict], llm_client=None, model: str = "gpt-4o-mini") -> List[List[Dict]]:
    """paragraphs: [{"text": str, "n_images": int}] → por párrafo, una escena por imagen:
    {"layout", "headline", "big"?, "bullets"?}. Nunca lanza: si el LLM falla, heurística."""
    if llm_client is None:
        return _heuristic_plan(paragraphs)

    listing = "\n\n".join(
        f"PÁRRAFO {i + 1} ({p['n_images']} escenas):\n{p['text']}" for i, p in enumerate(paragraphs)
    )
    system_msg = (
        "Eres el director de montaje de vídeos de YouTube. Para cada párrafo de la narración "
        "decides cómo se ve cada escena (una escena = una imagen de fondo). Layouts posibles:\n"
        "- full: imagen a pantalla completa con un titular corto opcional.\n"
        "- split: pantalla partida con dos imágenes entrando por los lados + titular.\n"
        "- code: un número o código en GRANDE (ej. códigos de Grabovoi '520 741 8', cifras, fechas, "
        "porcentajes). Úsalo SIEMPRE que la narración dicte un código o una cifra importante; "
        "convierte números dichos con palabras a dígitos ('cinco, dos, cero' → '520').\n"
        "- list: 2-3 viñetas muy cortas (pasos, errores, beneficios). Nunca listes los dígitos "
        "de un código: eso es 'code'.\n"
        "- quote: una frase potente del texto, en grande.\n"
        "Reglas: titulares de 2-6 palabras, viñetas de 2-5 palabras, en el idioma de la narración, "
        "sin emojis, sin inventar datos que no estén en el texto. Varía los layouts; no más de "
        "dos 'full' seguidos. Deja headline vacío en algunas escenas para que respire.\n"
        "Responde SOLO JSON: {\"paragraphs\": [[{\"layout\": ..., \"headline\": ..., "
        "\"big\": ..., \"bullets\": [...]}, ...], ...]} con exactamente el número de escenas "
        "pedido por párrafo."
    )
    try:
        resp = llm_client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_msg},
                      {"role": "user", "content": listing}],
            temperature=0.6,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        raw = data.get("paragraphs") or []
    except Exception as e:
        print(f"[motion] director LLM falló ({e}); uso heurística", flush=True)
        return _heuristic_plan(paragraphs)

    fallback = _heuristic_plan(paragraphs)
    plan = []
    for i, p in enumerate(paragraphs):
        got = raw[i] if i < len(raw) and isinstance(raw[i], list) else []
        scenes = []
        for j in range(p["n_images"]):
            s = got[j] if j < len(got) and isinstance(got[j], dict) else fallback[i][j]
            layout = s.get("layout") if s.get("layout") in LAYOUTS else "full"
            headline = str(s.get("headline") or "")
            big = str(s.get("big") or "")
            # El LLM a veces mete la frase de la cita en "big": úsala como cita.
            if layout == "quote" and not headline:
                headline = big
            scene = {
                "layout": layout,
                "headline": headline[:80 if layout == "quote" else 60],
                "big": big[:24] if layout == "code" else "",
                "bullets": [str(b)[:40] for b in (s.get("bullets") or [])][:3],
            }
            # Degradar layouts a los que les falta contenido.
            if layout == "code" and not scene["big"]:
                scene["layout"] = "full"
            if layout == "list" and len(scene["bullets"]) < 2:
                scene["layout"] = "full"
            if layout == "quote" and not scene["headline"]:
                scene["layout"] = "full"
            scenes.append(scene)
        plan.append(scenes)

    # Variedad: como mucho dos "full" seguidos; el tercero pasa a pantalla partida
    # (usa la imagen siguiente, así que la última escena del vídeo no puede ser split).
    flat = [s for para in plan for s in para]
    run = 0
    for k, s in enumerate(flat):
        run = run + 1 if s["layout"] == "full" else 0
        if run == 3 and k + 1 < len(flat):
            s["layout"] = "split"
            run = 0
    return plan


# ─── 2. Composición HyperFrames ─────────────────────────────────────

def _esc(text: str) -> str:
    return html.escape(text or "", quote=True)


def _group_words(words: List[Dict], max_words: int = 3, max_gap_ms: int = 350) -> List[List[Dict]]:
    groups, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        last = i == len(words) - 1
        brk = len(cur) >= max_words or last
        if not brk and words[i + 1]["start"] - w["end"] > max_gap_ms:
            brk = True
        if not brk and w["text"].rstrip().endswith((".", ",", "!", "?", ":", ";")):
            brk = True
        if brk:
            groups.append(cur)
            cur = []
    return groups


def build_composition(
    project_dir: Path,
    segments: List[Dict],
    scenes: List[Dict],
    words: Optional[List[Dict]],
    out_size: Tuple[int, int],
    theme: Dict,
    fps: int = 24,
    end_cards: Optional[List[Dict]] = None,
) -> Tuple[Path, float]:
    """Escribe project_dir/index.html y copia los assets.

    segments: [{"path": Path, "start": s, "duration": s}] contiguos (uno por imagen o clip).
    scenes:   una escena del director por segmento.
    words:    [{"text", "start" ms, "end" ms}] sobre el audio concatenado (o None).
    end_cards: [{"path": Path, "duration": s, "kind": "thumb"|"logo"}] tras el último segmento.
    Devuelve (ruta index.html, duración total).
    """
    W, H = out_size
    vertical = H > W
    assets = project_dir / "assets"
    if project_dir.exists():
        shutil.rmtree(project_dir)
    assets.mkdir(parents=True)

    for f in ("Anton-Regular.ttf", "Poppins-Bold.ttf"):
        if (FONTS_DIR / f).exists():
            shutil.copy2(FONTS_DIR / f, assets / f)
    gsap_src = Path(__file__).parent.parent / "static" / "gsap.min.js"
    if gsap_src.exists():
        shutil.copy2(gsap_src, assets / "gsap.min.js")
        gsap_tag = '<script src="assets/gsap.min.js"></script>'
    else:
        gsap_tag = '<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>'

    copied: Dict[str, str] = {}

    def asset(p: Path) -> str:
        key = str(p)
        if key not in copied:
            name = f"m{len(copied):03d}{p.suffix.lower()}"
            shutil.copy2(p, assets / name)
            copied[key] = f"assets/{name}"
        return copied[key]

    def media(p: Path, el_id: str, extra_cls: str = "", start: float = 0.0, dur: float = 0.0) -> str:
        src = asset(p)
        if p.suffix.lower() == ".mp4":
            # Los clips de vídeo (I2V) se reproducen en silencio durante su escena.
            return (f'<video id="{el_id}" class="media {extra_cls}" src="{src}" muted playsinline '
                    f'data-start="{start:.3f}" data-duration="{dur:.3f}"></video>')
        return f'<img id="{el_id}" class="media {extra_cls}" src="{src}" alt="">'

    title_px = int(min(W, H) * (0.11 if vertical else 0.085))
    big_px = int(min(W, H) * (0.2 if vertical else 0.17))
    body_px = int(min(W, H) * (0.06 if vertical else 0.05))
    cap_px = int(min(W, H) * (0.075 if vertical else 0.058))
    cap_bottom = int(H * (0.2 if vertical else 0.08))

    sections: List[str] = []
    js: List[str] = []
    total = 0.0

    for i, (seg, scene) in enumerate(zip(segments, scenes)):
        sid = f"s{i:03d}"
        start = seg["start"]
        dur = seg["duration"]
        # Cada escena empieza TRANSITION_SECS antes para solaparse con la anterior.
        lead = TRANSITION_SECS if i > 0 else 0.0
        c_start = max(0.0, start - lead)
        c_dur = dur + (start - c_start)
        total = max(total, start + dur)
        layout = scene.get("layout", "full")
        nxt = segments[i + 1]["path"] if i + 1 < len(segments) else None
        if layout == "split" and nxt is None:
            layout = "full"

        inner = ""
        if layout == "split":
            inner = (f'<div class="split {"split-v" if vertical else "split-h"}">'
                     f'<div class="pane" id="{sid}-a">{media(seg["path"], sid + "-ma", "", c_start, c_dur)}</div>'
                     f'<div class="pane" id="{sid}-b">{media(nxt, sid + "-mb", "", c_start, c_dur)}</div>'
                     f'<div class="split-line" id="{sid}-line"></div></div>')
        else:
            dim = " dim" if layout in ("code", "list", "quote") else ""
            inner = f'<div class="bg{dim}">{media(seg["path"], sid + "-m", "blur" if layout == "code" else "", c_start, c_dur)}</div>'

        text_html = ""
        headline = scene.get("headline") or ""
        if layout == "code":
            digits = "".join(
                f'<span class="digit" id="{sid}-d{k}">{_esc(ch) if ch != " " else "&nbsp;"}</span>'
                for k, ch in enumerate(scene["big"]))
            text_html = (f'<div class="center"><div class="label" id="{sid}-t">{_esc(headline)}</div>'
                         f'<div class="big">{digits}</div></div>')
        elif layout == "list":
            items = "".join(f'<li id="{sid}-b{k}"><span class="dot"></span>{_esc(b)}</li>'
                            for k, b in enumerate(scene["bullets"]))
            text_html = (f'<div class="center"><div class="label" id="{sid}-t">{_esc(headline)}</div>'
                         f'<ul class="bullets">{items}</ul></div>')
        elif layout == "quote":
            qwords = "".join(f'<span class="qw" id="{sid}-q{k}">{_esc(w)}</span> '
                             for k, w in enumerate(headline.split()))
            text_html = f'<div class="center"><div class="quote">{qwords}</div></div>'
        elif headline:
            text_html = f'<div class="chip-wrap"><div class="chip" id="{sid}-t">{_esc(headline)}</div></div>'

        sections.append(
            f'<section id="{sid}" class="clip scene" style="z-index:{10 + i}" '
            f'data-start="{c_start:.3f}" data-duration="{c_dur:.3f}" data-track-index="1">'
            f'{inner}{text_html}</section>')

        t0 = c_start
        # Transición de entrada (la escena nueva queda encima de la anterior).
        if i > 0:
            tr = TRANSITIONS[i % len(TRANSITIONS)]
            fr, to = {
                "fade": ({"opacity": 0}, {"opacity": 1}),
                "slide": ({"xPercent": 100} if not vertical else {"yPercent": 100}, {"xPercent": 0, "yPercent": 0}),
                "wipe": ({"clipPath": "inset(0% 100% 0% 0%)"}, {"clipPath": "inset(0% 0% 0% 0%)"}),
                "zoom": ({"scale": 1.25, "opacity": 0}, {"scale": 1, "opacity": 1}),
            }[tr]
            js.append(f'tl.fromTo("#{sid}", {json.dumps(fr)}, {{...{json.dumps(to)}, duration: {TRANSITION_SECS}, ease: "power2.out", immediateRender: false}}, {t0:.3f});')

        # Ken Burns sobre la(s) imagen(es); dirección alterna por escena.
        dx = 3 if i % 2 == 0 else -3
        if layout == "split":
            ax, bx = ("yPercent", "yPercent") if vertical else ("xPercent", "xPercent")
            js.append(f'tl.fromTo("#{sid}-a", {{{ax}: -100}}, {{{ax}: 0, duration: 0.7, ease: "power3.out", immediateRender: false}}, {t0 + 0.05:.3f});')
            js.append(f'tl.fromTo("#{sid}-b", {{{bx}: 100}}, {{{bx}: 0, duration: 0.7, ease: "power3.out", immediateRender: false}}, {t0 + 0.2:.3f});')
            js.append(f'tl.fromTo("#{sid}-line", {{scale: 0}}, {{scale: 1, duration: 0.5, ease: "power2.out", immediateRender: false}}, {t0 + 0.6:.3f});')
            for m in ("ma", "mb"):
                js.append(f'tl.fromTo("#{sid}-{m}", {{scale: 1.05}}, {{scale: 1.18, duration: {c_dur:.3f}, ease: "none", immediateRender: false}}, {t0:.3f});')
        else:
            js.append(f'tl.fromTo("#{sid}-m", {{scale: 1.04, xPercent: {-dx / 2}}}, {{scale: 1.16, xPercent: {dx / 2}, duration: {c_dur:.3f}, ease: "none", immediateRender: false}}, {t0:.3f});')

        tt = t0 + lead + 0.25
        if layout == "code":
            js.append(f'tl.fromTo("#{sid}-t", {{y: 40, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.5, ease: "power3.out", immediateRender: false}}, {tt:.3f});')
            n = len(scene["big"])
            step = min(0.18, max(0.06, (dur * 0.5) / max(1, n)))
            for k in range(n):
                js.append(f'tl.fromTo("#{sid}-d{k}", {{scale: 0.3, opacity: 0, y: 60}}, {{scale: 1, opacity: 1, y: 0, duration: 0.35, ease: "back.out(2.2)", immediateRender: false}}, {tt + 0.3 + k * step:.3f});')
        elif layout == "list":
            js.append(f'tl.fromTo("#{sid}-t", {{y: 40, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.5, ease: "power3.out", immediateRender: false}}, {tt:.3f});')
            nb = len(scene["bullets"])
            step = max(0.5, (dur - 1.0) / max(1, nb + 1))
            for k in range(nb):
                js.append(f'tl.fromTo("#{sid}-b{k}", {{x: -80, opacity: 0}}, {{x: 0, opacity: 1, duration: 0.5, ease: "power3.out", immediateRender: false}}, {tt + 0.4 + k * step:.3f});')
        elif layout == "quote":
            nq = len(headline.split())
            step = min(0.25, max(0.08, (dur * 0.6) / max(1, nq)))
            for k in range(nq):
                js.append(f'tl.fromTo("#{sid}-q{k}", {{y: 30, opacity: 0, filter: "blur(8px)"}}, {{y: 0, opacity: 1, filter: "blur(0px)", duration: 0.4, ease: "power2.out", immediateRender: false}}, {tt + k * step:.3f});')
        elif headline:
            js.append(f'tl.fromTo("#{sid}-t", {{clipPath: "inset(0% 100% 0% 0%)", x: -30}}, {{clipPath: "inset(0% 0% 0% 0%)", x: 0, duration: 0.6, ease: "power3.out", immediateRender: false}}, {tt:.3f});')

    # Tarjetas finales (miniatura + logo), como en el slideshow clásico.
    t_cursor = total
    for k, card in enumerate(end_cards or []):
        cid = f"end{k}"
        bg = "#000" if card.get("kind") == "logo" else "transparent"
        fit = "contain" if card.get("kind") == "logo" else "cover"
        sections.append(
            f'<section id="{cid}" class="clip scene" style="z-index:{900 + k};background:{bg}" '
            f'data-start="{t_cursor:.3f}" data-duration="{card["duration"]:.3f}" data-track-index="1">'
            f'<div class="bg"><img id="{cid}-m" class="media" style="object-fit:{fit}" src="{asset(card["path"])}" alt=""></div></section>')
        js.append(f'tl.fromTo("#{cid}", {{opacity: 0}}, {{opacity: 1, duration: 0.5, immediateRender: false}}, {t_cursor:.3f});')
        js.append(f'tl.fromTo("#{cid}-m", {{scale: 1.0}}, {{scale: 1.06, duration: {card["duration"]:.3f}, ease: "none", immediateRender: false}}, {t_cursor:.3f});')
        t_cursor += card["duration"]
    if end_cards:
        js.append(f'tl.to("#root", {{opacity: 0, duration: 1.0}}, {t_cursor - 1.0:.3f});')
    total = t_cursor

    # Subtítulos: grupos de 2-3 palabras, la activa con caja de color + "pop".
    caps: List[str] = []
    groups = _group_words(words or [])
    for g_i, group in enumerate(groups):
        g_start = group[0]["start"] / 1000.0
        g_end = group[-1]["end"] / 1000.0 + 0.12
        # Nunca dos grupos a la vez en pantalla: corta en el inicio del siguiente.
        if g_i + 1 < len(groups):
            g_end = min(g_end, groups[g_i + 1][0]["start"] / 1000.0)
        g_end = min(g_end, total)
        if g_start >= total:
            break
        cid = f"c{g_i:04d}"
        spans = "".join(f'<span class="w" id="{cid}-{k}">{_esc(w["text"].upper())}</span>'
                        for k, w in enumerate(group))
        caps.append(f'<div id="{cid}" class="clip cap" data-start="{g_start:.3f}" '
                    f'data-duration="{max(0.2, g_end - g_start):.3f}" data-track-index="2">'
                    f'<div class="cap-line">{spans}</div></div>')
        js.append(f'tl.fromTo("#{cid} .cap-line", {{scale: 0.8, y: 20}}, {{scale: 1, y: 0, duration: 0.18, ease: "back.out(2)", immediateRender: false}}, {g_start:.3f});')
        for k, w in enumerate(group):
            ws, we = w["start"] / 1000.0, w["end"] / 1000.0
            js.append(f'tl.fromTo("#{cid}-{k}", {{backgroundColor: "rgba(0,0,0,0)", color: "#FFFFFF", scale: 1}}, '
                      f'{{backgroundColor: "{theme["accent"]}", color: "{theme["accent_text"]}", scale: 1.12, duration: 0.08, immediateRender: false}}, {ws:.3f});')
            if k < len(group) - 1:
                js.append(f'tl.to("#{cid}-{k}", {{backgroundColor: "rgba(0,0,0,0)", color: "#FFFFFF", scale: 1, duration: 0.08}}, {max(ws + 0.08, we):.3f});')

    acc = theme["accent"]
    css = f"""
@font-face {{ font-family: "Anton"; src: url("assets/Anton-Regular.ttf"); }}
@font-face {{ font-family: "Poppins"; src: url("assets/Poppins-Bold.ttf"); font-weight: 700; }}
html, body {{ margin: 0; background: #000; }}
#root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
.clip {{ position: absolute; inset: 0; }}
.scene {{ overflow: hidden; }}
.bg, .pane {{ position: absolute; inset: 0; overflow: hidden; }}
.media {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.bg.dim::after {{ content: ""; position: absolute; inset: 0; background: radial-gradient(ellipse at center, rgba(0,0,0,0.35), rgba(0,0,0,0.78)); }}
.media.blur {{ filter: blur(14px) brightness(0.7); }}
.split-h .pane {{ width: 50%; }}
.split-h .pane:nth-child(2) {{ left: 50%; }}
.split-v .pane {{ height: 50%; }}
.split-v .pane:nth-child(2) {{ top: 50%; }}
.split-line {{ position: absolute; background: {acc}; box-shadow: 0 0 24px {acc}; }}
.split-h .split-line {{ left: calc(50% - 4px); top: 0; width: 8px; height: 100%; }}
.split-v .split-line {{ top: calc(50% - 4px); left: 0; height: 8px; width: 100%; }}
.center {{ position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center;
  justify-content: center; text-align: center; padding: 0 {int(W * 0.08)}px; box-sizing: border-box;
  padding-bottom: {int(H * (0.12 if vertical else 0.06))}px; }}
.label {{ font-family: "Poppins"; font-size: {body_px}px; color: {acc}; text-transform: uppercase;
  letter-spacing: 0.06em; margin-bottom: {int(body_px * 0.4)}px; text-shadow: 0 4px 18px rgba(0,0,0,0.8); }}
.big {{ font-family: "Anton"; font-size: {big_px}px; line-height: 1; color: #fff; letter-spacing: 0.04em;
  text-shadow: 0 0 40px {acc}, 0 8px 30px rgba(0,0,0,0.9); white-space: nowrap; }}
.digit {{ display: inline-block; }}
.bullets {{ list-style: none; margin: 0; padding: 0; text-align: left; }}
.bullets li {{ font-family: "Poppins"; font-size: {body_px}px; color: #fff; margin: {int(body_px * 0.35)}px 0;
  display: flex; align-items: center; text-shadow: 0 4px 16px rgba(0,0,0,0.9); }}
.dot {{ width: {int(body_px * 0.45)}px; height: {int(body_px * 0.45)}px; border-radius: 50%; background: {acc};
  margin-right: {int(body_px * 0.5)}px; flex: none; box-shadow: 0 0 16px {acc}; }}
.quote {{ font-family: "Anton"; font-size: {title_px}px; line-height: 1.15; color: #fff;
  text-transform: uppercase; text-shadow: 0 6px 30px rgba(0,0,0,0.9); }}
.qw {{ display: inline-block; }}
.chip-wrap {{ position: absolute; left: {int(W * 0.06)}px; right: {int(W * 0.06)}px;
  top: {int(H * (0.12 if vertical else 0.08))}px; display: flex; justify-content: {"center" if vertical else "flex-start"}; }}
.chip {{ font-family: "Anton"; font-size: {int(title_px * 0.62)}px; color: {theme["accent_text"]}; background: {acc};
  padding: {int(title_px * 0.12)}px {int(title_px * 0.3)}px; text-transform: uppercase; line-height: 1.1;
  box-shadow: 0 10px 30px rgba(0,0,0,0.5); max-width: 100%; }}
.cap {{ z-index: 2000; pointer-events: none; }}
.cap-line {{ position: absolute; left: {int(W * 0.05)}px; right: {int(W * 0.05)}px; bottom: {cap_bottom}px;
  text-align: center; font-family: "Poppins"; font-size: {cap_px}px; line-height: 1.25; }}
.w {{ display: inline-block; color: #fff; padding: 0 {int(cap_px * 0.14)}px; margin: 0 {int(cap_px * 0.06)}px;
  border-radius: {int(cap_px * 0.14)}px; -webkit-text-stroke: {max(2, cap_px // 16)}px #000; paint-order: stroke fill;
  text-shadow: 0 4px 12px rgba(0,0,0,0.85); }}
"""

    index = project_dir / "index.html"
    index.write_text(f"""<!doctype html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={W}, height={H}">
{gsap_tag}
<style>{css}</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}"
     data-width="{W}" data-height="{H}" data-fps="{fps}">
{chr(10).join(sections)}
{chr(10).join(caps)}
</div>
<script>
window.__timelines = window.__timelines || {{}};
const tl = gsap.timeline({{ paused: true }});
{chr(10).join(js)}
window.__timelines.main = tl;
</script>
</body>
</html>
""", encoding="utf-8")
    return index, total


# ─── 3. Render (servicio motion) ────────────────────────────────────

def render_project(project_dir: Path, out_path: Path, fps: int = 24,
                   progress_file: Optional[Path] = None, pct_range: Tuple[int, int] = (5, 88),
                   timeout_s: int = 6 * 3600) -> Path:
    """Lanza el render en el servicio `motion` (host Windows, ver motion/server.mjs) y espera.
    Se mandan rutas del contenedor (/app/cache/...); el servicio las traduce a D:\\...\\cache."""
    base = os.getenv("MOTION_URL", "http://host.docker.internal:8610").rstrip("/")
    # video.base_dir suele ser relativo ("cache/..."): el servicio necesita /app/cache/...
    r = requests.post(f"{base}/render", json={
        "projectDir": project_dir.resolve().as_posix(), "output": out_path.resolve().as_posix(), "fps": fps,
    }, timeout=30)
    r.raise_for_status()
    job_id = r.json()["id"]
    lo, hi = pct_range
    t_end = time.time() + timeout_s
    last = -1
    while time.time() < t_end:
        time.sleep(3)
        st = requests.get(f"{base}/status/{job_id}", timeout=30).json()
        pct = lo + int((hi - lo) * float(st.get("progress") or 0) / 100.0)
        if progress_file and pct != last:
            try:
                progress_file.write_text(str(pct))
            except Exception:
                pass
            last = pct
        if st.get("state") == "done":
            return out_path
        if st.get("state") == "error":
            raise RuntimeError(f"Render motion falló: {st.get('error')}")
    raise RuntimeError("Render motion: timeout")


# ─── 4. Audio + post ────────────────────────────────────────────────

def mux_audio(silent_video: Path, audio_paths: List[Path], out_path: Path, total: float,
              bg_music_path: Optional[Path] = None, overlay_video_path: Optional[Path] = None,
              out_size: Tuple[int, int] = (1080, 1920), voice_volume: float = 1.6,
              bg_music_volume: float = 0.06) -> Path:
    """Voz concatenada (+ música en bucle con fade-out) + loudnorm, y overlay opcional."""
    tmp = out_path.parent
    concat_list = tmp / "__motion_voice.txt"
    # Rutas absolutas: el demuxer concat resuelve las relativas desde la carpeta de la lista.
    concat_list.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in audio_paths), encoding="utf-8")

    cmd = ["ffmpeg", "-y", "-i", str(silent_video),
           "-f", "concat", "-safe", "0", "-i", str(concat_list)]
    filters = [f"[1:a]volume={voice_volume},apad,atrim=0:{total:.3f}[voice]"]
    mix_inputs = "[voice]"
    n_in = 2
    if bg_music_path and bg_music_path.exists():
        cmd += ["-stream_loop", "-1", "-i", str(bg_music_path)]
        filters.append(f"[{n_in}:a]volume={bg_music_volume},atrim=0:{total:.3f},"
                       f"afade=t=out:st={max(0.0, total - 2.0):.3f}:d=2[music]")
        mix_inputs += "[music]"
        n_in += 1
        filters.append(f"{mix_inputs}amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1:LRA=11[a_out]")
    else:
        filters.append("[voice]loudnorm=I=-14:TP=-1:LRA=11[a_out]")

    if overlay_video_path and overlay_video_path.exists():
        cmd += ["-stream_loop", "-1", "-i", str(overlay_video_path)]
        filters.append(f"[{n_in}:v]scale={out_size[0]}:{out_size[1]},colorkey=black:0.3:0.1[ovl]")
        # shortest=1 es seguro: el overlay va en bucle infinito (ver bug de los 80 s).
        filters.append("[0:v][ovl]overlay=shortest=1[v_out]")
        vmap, vcodec = "[v_out]", ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
    else:
        vmap, vcodec = "0:v", ["-c:v", "copy"]

    cmd += ["-filter_complex", ";".join(filters), "-map", vmap, "-map", "[a_out]",
            *vcodec, "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}",
            "-movflags", "+faststart", str(out_path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    concat_list.unlink(missing_ok=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg mux motion falló: {res.stderr[-800:]}")
    return out_path
