"""
Short promocional (vertical) a partir de un vídeo ya generado, con HyperFrames.

  1. candidate_sentences() → frases de la narración con sus tiempos (tiempos por palabra).
  2. plan_promo()           → el LLM "editor" elige 3-5 frases (gancho primero, cierre con
                              intriga) y un "golpe" visual para cada una; también el titular
                              gancho y el título/descripción del short.
  3. build_voice()          → recorta esas frases del audio original (misma voz) y las une.
  4. build_composition()    → motion graphics: fondo vivo, texto cinético palabra a palabra,
                              tarjetas de imagen, anillo contador, chips, checklist, barra de
                              progreso, transiciones circulares y tarjeta final con CTA (+ QR).
El render lo hace motion_engine.render_project() y el audio motion_engine.mux_audio().

Zonas seguras de Shorts: nada importante en el 16 % derecho (botones) ni en el 18 % inferior
(título y canal).
"""

import json
import math
import random
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.services.motion_engine import FONTS_DIR, _esc

BEATS = ("photo", "cards", "number", "chips", "checklist")
GAP_SECS = 0.25        # silencio entre frases recortadas
CTA_SECS = 4.0         # tarjeta final
COVER_SECS = 2.0       # portada fija al final: se elige como miniatura desde la app de YouTube
HOOK_SECS = 1.6        # titular gancho al empezar


# ─── 1. Frases candidatas ────────────────────────────────────────────

def candidate_sentences(words: List[Dict], min_s: float = 2.5, max_s: float = 13.0) -> List[Dict]:
    """Corta la transcripción en frases (por puntuación) con sus palabras y tiempos (s)."""
    out, cur = [], []
    for w in words:
        cur.append(w)
        if w["text"].rstrip().endswith((".", "?", "!", "…")):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    sents = []
    for ws in out:
        t0, t1 = ws[0]["start"] / 1000.0, ws[-1]["end"] / 1000.0
        if min_s <= t1 - t0 <= max_s:
            sents.append({"id": len(sents), "start": t0, "end": t1, "words": ws,
                          "text": " ".join(w["text"] for w in ws)})
    return sents


# ─── 2. Editor (LLM) ─────────────────────────────────────────────────

SYSTEM_MSG = (
    "Eres el editor de Shorts de un canal de YouTube. A partir de las frases numeradas de la "
    "narración de un vídeo largo, montas un Short promocional de 25-45 segundos usando SOLO "
    "frases de la lista (se recortarán del audio original, no se puede cambiar ni una palabra).\n"
    "Elige 3-5 frases: la PRIMERA es el gancho más fuerte (puede venir de cualquier punto del "
    "vídeo), las siguientes construyen la historia y la ÚLTIMA deja una pregunta o intriga "
    "abierta (no reveles el final: el objetivo es que vean el vídeo completo).\n"
    "Para cada frase elige un golpe visual:\n"
    "- photo: la imagen en grande. Por defecto.\n"
    "- cards: varias imágenes en abanico (lugares, personas, momentos).\n"
    "- number: un anillo con una cifra (number: '1936', '4', '2000') y label de 1-3 palabras. "
    "Solo si la frase dice esa cifra.\n"
    "- chips: 3-5 palabras clave (chips) que se van marcando.\n"
    "- checklist: 2-3 puntos cortos (items) que se van marcando.\n"
    "Para cada frase indica también keywords: 1-3 palabras EXACTAS de la frase que se "
    "destacarán en color.\n"
    "Además: hook_title (2-5 palabras en mayúsculas con UNA palabra entre *asteriscos*, el "
    "gancho que se ve en el primer segundo), short_title (máx. 90 caracteres, termina en "
    "#shorts), description (2-3 frases que inviten a ver el vídeo completo).\n"
    "Responde SOLO JSON: {\"hook_title\", \"short_title\", \"description\", \"beats\": "
    "[{\"sentence\": id, \"visual\", \"number\", \"label\", \"chips\": [], \"items\": [], "
    "\"keywords\": []}]}"
)


def plan_promo(sentences: List[Dict], title: str, llm_client=None, model: str = "gpt-4o-mini",
               min_total: float = 22.0, max_total: float = 48.0) -> Dict:
    """Devuelve {"hook_title", "short_title", "description", "beats": [...]} validado."""
    by_id = {s["id"]: s for s in sentences}
    data = {}
    if llm_client is not None:
        listing = "\n".join(f"[{s['id']}] ({s['end'] - s['start']:.1f}s) {s['text']}" for s in sentences)
        try:
            resp = llm_client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": SYSTEM_MSG},
                          {"role": "user", "content": f"Título del vídeo: {title}\n\nFrases:\n{listing}"}],
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content or "{}")
        except Exception as e:
            print(f"[promo] editor LLM falló: {e}; uso fallback", flush=True)

    beats, total, seen = [], 0.0, set()
    for b in data.get("beats") or []:
        try:
            sid = int(b.get("sentence"))
        except (TypeError, ValueError):
            continue
        s = by_id.get(sid)
        if not s or sid in seen:
            continue
        dur = s["end"] - s["start"]
        if total + dur > max_total:
            break
        visual = b.get("visual") if b.get("visual") in BEATS else "photo"
        number = str(b.get("number") or "").strip()[:8]
        if visual == "number" and not re.search(r"\d", number):
            visual = "photo"
        chips = [str(c).strip()[:22] for c in (b.get("chips") or []) if str(c).strip()][:5]
        items = [str(c).strip()[:40] for c in (b.get("items") or []) if str(c).strip()][:3]
        if visual == "chips" and len(chips) < 3:
            visual = "photo"
        if visual == "checklist" and len(items) < 2:
            visual = "photo"
        beats.append({"sentence": sid, "visual": visual, "number": number,
                      "label": str(b.get("label") or "").strip()[:30], "chips": chips, "items": items,
                      "keywords": [str(k).strip() for k in (b.get("keywords") or [])][:3]})
        seen.add(sid)
        total += dur + GAP_SECS
    # Fallback: las frases más largas del principio hasta llegar al mínimo.
    if total < min_total:
        for s in sentences:
            if s["id"] in seen:
                continue
            beats.append({"sentence": s["id"], "visual": "photo" if len(beats) % 2 == 0 else "cards",
                          "number": "", "label": "", "chips": [], "items": [], "keywords": []})
            seen.add(s["id"])
            total += s["end"] - s["start"] + GAP_SECS
            if total >= min_total:
                break
    hook = str(data.get("hook_title") or "").strip()[:40] or title.upper()[:40]
    if "*" not in hook and hook.split():
        ws = hook.split()
        ws[-1] = f"*{ws[-1]}*"
        hook = " ".join(ws)
    short_title = str(data.get("short_title") or "").strip()[:95] or f"{title[:80]} #shorts"
    if "#shorts" not in short_title.lower():
        short_title = f"{short_title[:86]} #shorts"
    return {"hook_title": hook, "short_title": short_title,
            "description": str(data.get("description") or "").strip()[:900], "beats": beats}


# ─── 3. Voz recortada ────────────────────────────────────────────────

def build_voice(combined_audio: Path, sentences: List[Dict], plan: Dict, out_wav: Path) -> List[Dict]:
    """Recorta las frases elegidas del audio original y las une. Devuelve los golpes con su
    tiempo en el short (start/end) y sus palabras re-temporizadas (ms en el short)."""
    from pydub import AudioSegment
    src = AudioSegment.from_file(str(combined_audio))
    by_id = {s["id"]: s for s in sentences}
    voice = AudioSegment.silent(duration=200)
    t = 0.2
    timed = []
    for b in plan["beats"]:
        s = by_id[b["sentence"]]
        a0 = max(0, int(s["start"] * 1000) - 80)
        a1 = min(len(src), int(s["end"] * 1000) + 150)
        clip = src[a0:a1].fade_in(30).fade_out(60)
        shift = t * 1000 - a0
        words = [{"text": w["text"], "start": w["start"] + shift, "end": w["end"] + shift} for w in s["words"]]
        timed.append({**b, "start": t, "end": t + len(clip) / 1000.0, "src_start": s["start"],
                      "src_end": s["end"], "words": words, "text": s["text"]})
        voice += clip + AudioSegment.silent(duration=int(GAP_SECS * 1000))
        t = len(voice) / 1000.0
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    voice.export(str(out_wav), format="wav")
    return timed


# ─── 4. Composición ──────────────────────────────────────────────────

def _rich(text: str) -> str:
    parts = re.split(r"\*([^*]+)\*", text or "")
    return "".join(f"<em>{_esc(p)}</em>" if i % 2 else _esc(p) for i, p in enumerate(parts))


def _norm(w: str) -> str:
    import unicodedata
    w = unicodedata.normalize("NFKD", w.lower())
    return re.sub(r"[^a-z0-9ñ]", "", "".join(c for c in w if not unicodedata.combining(c)))


def diversify(beats: List[Dict]) -> List[Dict]:
    """El LLM tiende a poner "photo" en todo. Si la frase dice una cifra → anillo contador;
    y nunca dos golpes seguidos con el mismo visual (alterna photo / cards)."""
    prev = None
    for b in beats:
        if b["visual"] == "photo" and not b.get("number"):
            m = re.search(r"\b(\d[\d.]*)\s+([a-záéíóúñ]+)?", b.get("text", ""), re.I)
            if m and len(m.group(1).replace(".", "")) <= 5:
                b["visual"], b["number"] = "number", m.group(1).replace(".", "")
                b["label"] = b.get("label") or (m.group(2) or "").upper()
        if b["visual"] == prev and b["visual"] in ("photo", "cards"):
            b["visual"] = "cards" if prev == "photo" else "photo"
        prev = b["visual"]
    return beats


def images_for(segments: List[Dict], t0: float, t1: float, n: int) -> List[Path]:
    """Imágenes que se veían en el vídeo largo durante [t0, t1] (y vecinas si faltan)."""
    idx = [k for k, s in enumerate(segments) if s["start"] < t1 and s["start"] + s["duration"] > t0]
    if not idx:
        idx = [min(range(len(segments)), key=lambda k: abs(segments[k]["start"] - t0))]
    k0, k1 = idx[0], idx[-1]
    while k1 - k0 + 1 < n and (k0 > 0 or k1 < len(segments) - 1):
        if k1 < len(segments) - 1:
            k1 += 1
        if k1 - k0 + 1 < n and k0 > 0:
            k0 -= 1
    return [segments[k]["path"] for k in range(k0, k1 + 1)][:n]


def build_composition(project_dir: Path, beats: List[Dict], segments: List[Dict], plan: Dict,
                      theme: Dict, out_size: Tuple[int, int] = (1080, 1920), fps: int = 30,
                      logo: Optional[Path] = None, long_title: str = "",
                      qr: Optional[Dict] = None, cover_image: Optional[Path] = None) -> Tuple[Path, float]:
    """cover_image: miniatura vertical ya diseñada (thumbnail_motion) para la portada final;
    si falta, se compone una con la imagen del gancho y el titular."""
    W, H = out_size
    u = W / 100.0
    rng = random.Random(1234)  # determinista: nada de Math.random en la composición
    assets = project_dir / "assets"
    if project_dir.exists():
        shutil.rmtree(project_dir)
    assets.mkdir(parents=True)
    for f in ("BebasNeue-Regular.ttf", "Poppins-Bold.ttf"):
        if (FONTS_DIR / f).exists():
            shutil.copy2(FONTS_DIR / f, assets / f)
    shutil.copy2(Path(__file__).parent.parent / "static" / "gsap.min.js", assets / "gsap.min.js")
    copied: Dict[str, str] = {}

    def asset(p: Path) -> str:
        if str(p) not in copied:
            name = f"m{len(copied):03d}{p.suffix.lower()}"
            shutil.copy2(p, assets / name)
            copied[str(p)] = f"assets/{name}"
        return copied[str(p)]

    def media(p: Path, el_id: str, cls: str, start: float, dur: float) -> str:
        if p.suffix.lower() == ".mp4":
            return (f'<video id="{el_id}" class="{cls}" src="{asset(p)}" muted playsinline '
                    f'data-start="{start:.3f}" data-duration="{dur:.3f}"></video>')
        return f'<img id="{el_id}" class="{cls}" src="{asset(p)}" alt="">'

    T, A, A2, BG = theme["text"], theme["accent"], theme["accent2"], theme["bg"]
    narr_end = beats[-1]["end"] if beats else 0.0
    total = narr_end + CTA_SECS + COVER_SECS
    js: List[str] = []
    html: List[str] = []

    def tw(sel, fr, to, t, dur=0.5, ease="power3.out", extra=""):
        js.append(f'tl.fromTo("{sel}", {json.dumps(fr)}, {{...{json.dumps(to)}, duration: {dur}, ease: "{ease}", immediateRender: false{extra}}}, {t:.3f});')

    # ── Fondo vivo: manchas de color difuminadas que derivan + partículas ──
    blobs = [(A, 0.55, 18, 22), (A2, 0.45, 78, 40), (A, 0.35, 30, 78)]
    for k, (col, op, x, y) in enumerate(blobs):
        html.append(f'<div class="blob" id="blob{k}" style="background:{col};opacity:{op};left:{x - 35}%;top:{y - 20}%"></div>')
        period = 7.0 + 2.5 * k
        reps = max(1, math.ceil(total / period))
        dx, dy = (12, -8) if k % 2 == 0 else (-10, 9)
        js.append(f'tl.fromTo("#blob{k}", {{xPercent: 0, yPercent: 0, scale: 1}}, {{xPercent: {dx}, yPercent: {dy}, scale: 1.15, '
                  f'duration: {period / 2:.2f}, ease: "sine.inOut", repeat: {reps * 2 - 1}, yoyo: true, immediateRender: false}}, 0);')
    for k in range(26):
        x, y, s = rng.uniform(4, 96), rng.uniform(5, 95), rng.uniform(0.25, 0.7)
        drift, period = rng.uniform(4, 10), rng.uniform(4, 8)
        reps = max(1, math.ceil(total / period))
        html.append(f'<div class="pt" id="pt{k}" style="left:{x:.1f}%;top:{y:.1f}%;width:{s * u:.1f}px;height:{s * u:.1f}px"></div>')
        js.append(f'tl.fromTo("#pt{k}", {{y: 0, opacity: 0.15}}, {{y: {-drift * u:.0f}, opacity: 0.85, duration: {period / 2:.2f}, '
                  f'ease: "sine.inOut", repeat: {reps * 2 - 1}, yoyo: true, immediateRender: false}}, {rng.uniform(0, 2):.2f});')

    # ── Barra de progreso (retención) ──
    html.append('<div id="prog"></div>')
    tw("#prog", {"scaleX": 0}, {"scaleX": 1}, 0, total, "none")

    # ── Titular gancho del primer segundo ──
    hook_words = plan["hook_title"].split()
    hook_spans = "".join(f'<span class="hw" id="hw{k}">{_rich(w)}</span> ' for k, w in enumerate(hook_words))
    html.append(f'<div id="hook" class="clip" data-start="0" data-duration="{HOOK_SECS + 0.5:.2f}" data-track-index="3">'
                f'<div class="hook-in">{hook_spans}</div></div>')
    for k in range(len(hook_words)):
        tw(f"#hw{k}", {"scale": 2.2, "opacity": 0, "rotation": rng.uniform(-8, 8)}, {"scale": 1, "opacity": 1, "rotation": 0},
           0.05 + k * 0.12, 0.45, "back.out(2.2)")
    tw("#hook .hook-in", {"scale": 1, "opacity": 1}, {"scale": 0.6, "opacity": 0}, HOOK_SECS, 0.4, "power2.in")

    # ── Golpes ──
    beats = diversify(beats)
    for i, b in enumerate(beats):
        bid = f"b{i}"
        t0 = b["start"] if i > 0 else HOOK_SECS - 0.2
        t1 = b["end"] + (GAP_SECS if i < len(beats) - 1 else 0.0)
        dur = t1 - t0
        vis = b["visual"]
        inner = ""
        # Golpes largos de foto: dos imágenes con destello a mitad.
        n_img = 3 if vis == "cards" else (2 if vis == "photo" and dur > 6.0 else 1)
        src_imgs = images_for(segments, b["src_start"], b["src_end"], n_img)
        if vis == "cards":
            cards = []
            for k, p in enumerate(src_imgs):
                rot = [-9, 2, 10][k % 3]
                cards.append(f'<div class="card fan" id="{bid}-c{k}" style="left:{8 + k * 16}%;top:{10 + k * 4}%;z-index:{k + 1}">'
                             f'{media(p, f"{bid}-c{k}i", "ci", t0, dur)}</div>')
                tw(f"#{bid}-c{k}", {"x": (-1 if k % 2 == 0 else 1) * 80 * u, "rotation": rot * 3, "opacity": 0},
                   {"x": 0, "rotation": rot, "opacity": 1}, t0 + 0.15 + k * 0.35, 0.8, "power4.out")
                tw(f"#{bid}-c{k}i", {"scale": 1.0}, {"scale": 1.12}, t0, dur, "none")
            inner = "".join(cards)
        elif vis == "number":
            num = b["number"]
            n_int = int(re.sub(r"\D", "", num) or 0)
            counting = num.isdigit() and 0 < n_int < 100000 and len(num) < 6
            r = 34 * u
            circ = 2 * math.pi * r
            # Golpe largo: a mitad, la imagen de fondo cambia con un destello.
            if dur > 6.0:
                src_imgs = images_for(segments, b["src_start"], b["src_end"], 2)
            bg_img = "".join(media(p, f"{bid}-bg{k}" if k else f"{bid}-bg", "numbg" + (" later" if k else ""), t0, dur) for k, p in enumerate(src_imgs))
            bg_img += f'<div class="numflash" id="{bid}-fl"></div>' 
            inner = (f'<div class="numwrap">{bg_img}<svg class="ring" viewBox="0 0 {2.4 * r:.0f} {2.4 * r:.0f}">'
                     f'<circle cx="{1.2 * r:.0f}" cy="{1.2 * r:.0f}" r="{r:.0f}" class="ring-bg"/>'
                     f'<circle id="{bid}-ring" cx="{1.2 * r:.0f}" cy="{1.2 * r:.0f}" r="{r:.0f}" class="ring-fg" '
                     f'style="stroke-dasharray:{circ:.0f};stroke-dashoffset:{circ:.0f}"/></svg>'
                     f'<div class="num" id="{bid}-n">{_esc(num if not counting else "0")}</div>'
                     f'<div class="numlabel" id="{bid}-l">{_esc(b["label"])}</div></div>')
            tw(f"#{bid}-bg", {"scale": 1.25, "opacity": 0}, {"scale": 1.05, "opacity": 0.35}, t0, dur, "none")
            if len(src_imgs) > 1:
                tm = t0 + dur / 2
                tw(f"#{bid}-bg1", {"opacity": 0, "scale": 1.25}, {"opacity": 0.4, "scale": 1.05}, tm, t1 - tm, "none")
                tw(f"#{bid}-fl", {"opacity": 0.75}, {"opacity": 0}, tm, 0.45, "power2.out")
                tw(f"#{bid}-n", {"scale": 1.0}, {"scale": 1.12}, tm, 0.18, "power2.out", ", yoyo: true, repeat: 1")
            tw(f"#{bid}-ring", {"strokeDashoffset": circ}, {"strokeDashoffset": 0}, t0 + 0.2, 1.6, "power2.inOut")
            tw(f"#{bid}-n", {"scale": 0.4, "opacity": 0}, {"scale": 1, "opacity": 1}, t0 + 0.2, 0.6, "back.out(2)")
            if counting:
                js.append(f'(() => {{ const o = {{v: 0}}; const el = document.getElementById("{bid}-n"); '
                          f'tl.fromTo(o, {{v: 0}}, {{v: {n_int}, duration: 1.5, ease: "power2.out", immediateRender: false, '
                          f'onUpdate: () => {{ el.textContent = Math.round(o.v); }}}}, {t0 + 0.2:.3f}); }})();')
            tw(f"#{bid}-l", {"y": 3 * u, "opacity": 0}, {"y": 0, "opacity": 1}, t0 + 1.0, 0.5)
        elif vis == "chips":
            chips = "".join(f'<span class="chip" id="{bid}-h{k}">{_esc(c)}</span>' for k, c in enumerate(b["chips"]))
            inner = (f'<div class="card small tilt" id="{bid}-p">{media(src_imgs[0], f"{bid}-pi", "ci", t0, dur)}</div>'
                     f'<div class="chips">{chips}</div>')
            tw(f"#{bid}-p", {"y": -10 * u, "opacity": 0, "rotation": -6}, {"y": 0, "opacity": 1, "rotation": -2}, t0 + 0.1, 0.7)
            tw(f"#{bid}-pi", {"scale": 1.0}, {"scale": 1.12}, t0, dur, "none")
            n = len(b["chips"])
            for k in range(n):
                tw(f"#{bid}-h{k}", {"scale": 0, "opacity": 0}, {"scale": 1, "opacity": 1}, t0 + 0.4 + k * 0.12, 0.4, "back.out(2.5)")
            # Se van "seleccionando" a lo largo de la frase.
            for k in range(n):
                ts = t0 + 1.2 + k * max(0.5, (dur - 1.8) / n)
                js.append(f'tl.fromTo("#{bid}-h{k}", {{backgroundColor: "rgba(255,255,255,0.12)", color: "{T}"}}, '
                          f'{{backgroundColor: "{A}", color: "{BG}", duration: 0.2, immediateRender: false}}, {ts:.3f});')
                tw(f"#{bid}-h{k}", {"scale": 1.0}, {"scale": 1.12}, ts, 0.15, "power2.out", ", yoyo: true, repeat: 1")
        elif vis == "checklist":
            rows = "".join(f'<div class="ck" id="{bid}-k{k}"><span class="box"><span class="tick" id="{bid}-t{k}">✓</span></span>'
                           f'<span>{_esc(it)}</span></div>' for k, it in enumerate(b["items"]))
            inner = (f'<div class="card small tilt" id="{bid}-p">{media(src_imgs[0], f"{bid}-pi", "ci", t0, dur)}</div>'
                     f'<div class="checks">{rows}</div>')
            tw(f"#{bid}-p", {"y": -10 * u, "opacity": 0, "rotation": 6}, {"y": 0, "opacity": 1, "rotation": 2}, t0 + 0.1, 0.7)
            tw(f"#{bid}-pi", {"scale": 1.0}, {"scale": 1.12}, t0, dur, "none")
            n = len(b["items"])
            for k in range(n):
                tk = t0 + 0.5 + k * max(0.7, (dur - 1.5) / n)
                tw(f"#{bid}-k{k}", {"x": -12 * u, "opacity": 0}, {"x": 0, "opacity": 1}, tk, 0.45)
                tw(f"#{bid}-t{k}", {"scale": 0, "rotation": -45}, {"scale": 1, "rotation": 0}, tk + 0.35, 0.35, "back.out(3)")
        else:  # photo
            imgs = "".join(media(p, f"{bid}-pi{k}", "ci" + (" swap" if k else ""), t0, dur) for k, p in enumerate(src_imgs))
            inner = (f'<div class="card big tilt" id="{bid}-p">{imgs}<div class="shine" id="{bid}-sh"></div>'
                     f'<div class="flash" id="{bid}-fl"></div></div>')
            tw(f"#{bid}-p", {"clipPath": "inset(50% 50% 50% 50% round 4%)", "rotation": -4, "scale": 0.9},
               {"clipPath": "inset(0% 0% 0% 0% round 4%)", "rotation": 0, "scale": 1}, t0 + 0.05, 0.8, "power4.out")
            tw(f"#{bid}-pi0", {"scale": 1.25}, {"scale": 1.05}, t0, dur, "none")
            if len(src_imgs) > 1:
                tm = t0 + dur / 2
                tw(f"#{bid}-fl", {"opacity": 0.9}, {"opacity": 0}, tm, 0.45, "power2.out")
                tw(f"#{bid}-pi1", {"opacity": 1, "scale": 1.2}, {"opacity": 1, "scale": 1.04}, tm, t1 - tm, "none")
        # Todas las tarjetas: leve giro 3D continuo + un brillo que las cruza al entrar.
        tw(f"#{bid} .tilt", {"rotationY": -7, "rotationX": 3}, {"rotationY": 7, "rotationX": -2}, t0, max(1.0, dur), "sine.inOut")
        if vis == "photo":
            tw(f"#{bid}-sh", {"xPercent": -120}, {"xPercent": 220}, t0 + 0.7, 1.1, "power2.inOut")

        html.append(f'<section id="{bid}" class="clip beat" data-start="{t0:.3f}" data-duration="{dur:.3f}" '
                    f'data-track-index="1" style="z-index:{10 + i}">{inner}</section>')
        if i > 0:
            tw(f"#{bid}", {"clipPath": "circle(0% at 50% 30%)"}, {"clipPath": "circle(150% at 50% 30%)"}, t0, 0.55, "power3.inOut")

        # Texto cinético: grupos de hasta 3 palabras, cada palabra entra al decirse.
        # Palabras clave de varias palabras ("dos mil años") → cada una cuenta.
        kw = {_norm(t) for k in b["keywords"] for t in (k or "").split() if len(_norm(t)) > 2 or _norm(t).isdigit()}
        ws = b["words"]
        groups, cur = [], []
        for w in ws:
            cur.append(w)
            if len(cur) >= 3 or w["text"].rstrip().endswith((",", ".", "?", "!", ";", ":")):
                groups.append(cur)
                cur = []
        if cur:
            groups.append(cur)
        for g, grp in enumerate(groups):
            gs = grp[0]["start"] / 1000.0
            ge = groups[g + 1][0]["start"] / 1000.0 if g + 1 < len(groups) else t1
            gid = f"{bid}g{g}"
            spans = []
            for k, w in enumerate(grp):
                hot = _norm(w["text"]) in kw
                spans.append(f'<span class="kw{" hot" if hot else ""}" id="{gid}-{k}">{_esc(w["text"].upper())}</span>')
                ws_t = w["start"] / 1000.0
                if hot:
                    tw(f"#{gid}-{k}", {"scale": 1.7, "opacity": 0, "rotation": -6}, {"scale": 1, "opacity": 1, "rotation": 0},
                       ws_t, 0.35, "back.out(2.4)")
                    # "Puñetazo": todo el bloque de texto da un golpe de escala.
                    tw(f"#{gid} .words-in", {"scale": 1.0}, {"scale": 1.07}, ws_t, 0.12, "power2.out", ", yoyo: true, repeat: 1")
                else:
                    tw(f"#{gid}-{k}", {"y": 6 * u, "opacity": 0, "filter": "blur(10px)"},
                       {"y": 0, "opacity": 1, "filter": "blur(0px)"}, ws_t, 0.28, "power3.out")
            html.append(f'<div class="clip words" id="{gid}" data-start="{gs:.3f}" data-duration="{max(0.2, ge - gs):.3f}" '
                        f'data-track-index="2"><div class="words-in">{" ".join(spans)}</div></div>')

    # ── Tarjeta final: CTA ──
    c0 = narr_end
    logo_html = f'<img class="logo" id="cta-logo" src="{asset(logo)}" alt="">' if logo and logo.exists() else ""
    qr_html = ""
    if qr and qr.get("url"):
        try:
            import qrcode
            qrcode.make(qr["url"], border=1).save(assets / "qr.png")
            qr_html = ('<div class="qr" id="cta-qr"><img src="assets/qr.png" alt="">'
                       '<div>Compra el libro<br>Link en la descripción</div></div>')
        except Exception as e:
            print(f"[promo] QR omitido: {e}", flush=True)
    html.append(f'<section id="cta" class="clip" data-start="{c0:.3f}" data-duration="{CTA_SECS:.3f}" data-track-index="1" style="z-index:500">'
                f'<div class="cta-in">{logo_html}<div class="cta-t" id="cta-t">MIRA EL VÍDEO<br><em>COMPLETO</em></div>'
                f'<div class="pill" id="cta-p">EN EL CANAL</div><div class="cta-sub" id="cta-s">{_esc(long_title)}</div>'
                f'{qr_html}<div class="arrow" id="cta-a">↓</div></div></section>')
    tw("#cta", {"clipPath": "circle(0% at 50% 50%)"}, {"clipPath": "circle(150% at 50% 50%)"}, c0, 0.6, "power3.inOut")
    if logo_html:
        tw("#cta-logo", {"scale": 0, "rotation": -30}, {"scale": 1, "rotation": 0}, c0 + 0.3, 0.6, "back.out(2)")
    tw("#cta-t", {"y": 8 * u, "opacity": 0}, {"y": 0, "opacity": 1}, c0 + 0.5, 0.6)
    tw("#cta-p", {"scale": 0, "opacity": 0}, {"scale": 1, "opacity": 1}, c0 + 0.9, 0.5, "back.out(2.5)")
    tw("#cta-p", {"scale": 1}, {"scale": 1.08}, c0 + 1.5, 0.45, "sine.inOut", ", yoyo: true, repeat: 4")
    tw("#cta-s", {"opacity": 0}, {"opacity": 1}, c0 + 1.2, 0.5)
    if qr_html:
        tw("#cta-qr", {"y": 6 * u, "opacity": 0}, {"y": 0, "opacity": 1}, c0 + 1.3, 0.5)
    tw("#cta-a", {"y": 0, "opacity": 0}, {"y": 3 * u, "opacity": 1}, c0 + 1.4, 0.5, "sine.inOut", ", yoyo: true, repeat: 4")

    # ── Portada fija (miniatura): imagen del gancho a sangre + titular, SIN animación tras
    # un fundido corto, para que cualquier fotograma sirva como miniatura del Short.
    cover_t = narr_end + CTA_SECS
    cover_img = images_for(segments, beats[0]["src_start"], beats[0]["src_end"], 1)[0] if beats else None
    hook_rows = []
    words_h = plan["hook_title"].split()
    per = 2 if len(words_h) > 3 else len(words_h) or 1
    for k in range(0, len(words_h), per):
        hook_rows.append(" ".join(words_h[k:k + per]))
    if cover_image:
        # La miniatura ya trae su texto: se pone tal cual, sin sombra ni titular encima.
        cover_inner = f'<img id="cover-i" class="cover-img flat" src="{asset(cover_image)}" alt="">'
    else:
        cover_media = media(cover_img, "cover-i", "cover-img", cover_t, COVER_SECS) if cover_img else ""
        cover_inner = (f'{cover_media}<div class="cover-shade"></div>'
                       f'<div class="cover-t">{"".join(f"<div>{_rich(r)}</div>" for r in hook_rows)}</div>')
    html.append(f'<section id="cover" class="clip" data-start="{cover_t:.3f}" data-duration="{COVER_SECS:.3f}" '
                f'data-track-index="1" style="z-index:600">{cover_inner}</section>')
    tw("#cover", {"opacity": 0}, {"opacity": 1}, cover_t, 0.15, "none")
    tw("#prog", {"opacity": 1}, {"opacity": 0}, cover_t, 0.15, "none")

    DISPLAY = '"Bebas", "Times New Roman", serif'
    css = f"""
@font-face {{ font-family: "Bebas"; src: url("assets/BebasNeue-Regular.ttf"); }}
@font-face {{ font-family: "Poppins"; src: url("assets/Poppins-Bold.ttf"); font-weight: 700; }}
html, body {{ margin: 0; background: {BG}; }}
#root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden;
  background: linear-gradient(170deg, {BG} 0%, #000 100%); }}
em {{ font-style: normal; color: {A}; }}
.clip {{ position: absolute; inset: 0; }}
.blob {{ position: absolute; width: 70%; height: 40%; border-radius: 50%; filter: blur({18 * u:.0f}px); }}
.pt {{ position: absolute; border-radius: 50%; background: {A}; box-shadow: 0 0 {u:.0f}px {A}; }}
#prog {{ position: absolute; left: 0; top: 0; width: 100%; height: {0.9 * u:.0f}px; background: {A};
  transform-origin: left center; z-index: 3000; box-shadow: 0 0 {2 * u:.0f}px {A}; }}
#hook {{ z-index: 2500; display: flex; align-items: center; justify-content: center; }}
.hook-in {{ font-family: {DISPLAY}; font-size: {17 * u:.0f}px; line-height: 0.95; color: {T}; text-align: center;
  width: 82%; text-shadow: 0 {u:.0f}px {4 * u:.0f}px rgba(0,0,0,0.9); margin-top: -{60 * u:.0f}px; }}
.hw {{ display: inline-block; }}
.beat {{ perspective: {160 * u:.0f}px; }}
.shine {{ position: absolute; top: -20%; bottom: -20%; width: 35%; left: 0; transform: rotate(18deg);
  background: linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.45) 50%, rgba(255,255,255,0) 100%); }}
.flash {{ position: absolute; inset: 0; background: #fff; opacity: 0; }}
.card .swap {{ position: absolute; inset: 0; opacity: 0; }}
.card {{ position: absolute; overflow: hidden; border-radius: {3.5 * u:.0f}px; box-shadow: 0 {3 * u:.0f}px {8 * u:.0f}px rgba(0,0,0,0.7);
  border: {0.5 * u:.1f}px solid rgba(255,255,255,0.18); }}
.card .ci {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.card.big {{ left: 6%; top: 7%; width: 78%; height: 46%; }}
.card.fan {{ width: 58%; height: 34%; }}
.card.small {{ left: 9%; top: 8%; width: 66%; height: 26%; }}
.numwrap {{ position: absolute; left: 0; right: 16%; top: 6%; height: 45%; display: flex; flex-direction: column;
  align-items: center; justify-content: center; }}
.numbg {{ position: absolute; left: 8%; top: 4%; width: 92%; height: 92%; object-fit: cover; border-radius: {4 * u:.0f}px; filter: blur(2px); }}
.numbg.later {{ opacity: 0; }}
.numflash {{ position: absolute; left: 8%; top: 4%; width: 92%; height: 92%; border-radius: {4 * u:.0f}px; background: #fff; opacity: 0; }}
.ring {{ position: absolute; width: {82 * u:.0f}px; height: {82 * u:.0f}px; transform: rotate(-90deg); }}
.ring-bg {{ fill: rgba(0,0,0,0.45); stroke: rgba(255,255,255,0.15); stroke-width: {2.2 * u:.0f}px; }}
.ring-fg {{ fill: none; stroke: {A}; stroke-width: {2.2 * u:.0f}px; stroke-linecap: butt; filter: drop-shadow(0 0 {1.5 * u:.0f}px {A}); }}
.num {{ position: relative; font-family: {DISPLAY}; font-size: {26 * u:.0f}px; color: {T}; line-height: 1; }}
.numlabel {{ position: relative; font-family: "Poppins"; font-size: {4.4 * u:.0f}px; color: {A}; text-transform: uppercase;
  letter-spacing: 0.06em; }}
.chips {{ position: absolute; left: 7%; right: 18%; top: 37%; display: flex; flex-wrap: wrap; gap: {2 * u:.0f}px; }}
.chip {{ font-family: "Poppins"; font-size: {4.6 * u:.0f}px; color: {T}; background: rgba(255,255,255,0.12);
  border: {0.3 * u:.1f}px solid rgba(255,255,255,0.25); border-radius: 999px; padding: {1.4 * u:.0f}px {3.6 * u:.0f}px; }}
.checks {{ position: absolute; left: 8%; right: 18%; top: 37%; }}
.ck {{ display: flex; align-items: center; font-family: "Poppins"; font-size: {5 * u:.0f}px; color: {T}; margin: {2.2 * u:.0f}px 0; }}
.box {{ width: {7 * u:.0f}px; height: {7 * u:.0f}px; border-radius: {1.8 * u:.0f}px; background: {A}; margin-right: {3 * u:.0f}px;
  display: flex; align-items: center; justify-content: center; flex: none; }}
.tick {{ color: {BG}; font-size: {5 * u:.0f}px; display: inline-block; }}
.words {{ z-index: 1000; }}
.words-in {{ position: absolute; left: 6%; right: 16%; top: 59%; text-align: center; font-family: {DISPLAY};
  font-size: {13 * u:.0f}px; line-height: 1.0; color: {T}; text-shadow: 0 {0.8 * u:.0f}px {3 * u:.0f}px rgba(0,0,0,0.9); }}
.kw {{ display: inline-block; }}
.kw.hot {{ color: {A}; font-size: 1.12em; }}
#cta {{ display: flex; align-items: center; justify-content: center; background: radial-gradient(ellipse at 50% 40%, {A}33 0%, {BG} 60%); }}
.cta-in {{ display: flex; flex-direction: column; align-items: center; text-align: center; width: 80%; margin-top: -{14 * u:.0f}px; }}
.logo {{ width: {30 * u:.0f}px; height: {30 * u:.0f}px; object-fit: contain; border-radius: 50%; margin-bottom: {4 * u:.0f}px;
  box-shadow: 0 0 {6 * u:.0f}px {A}88; }}
.cta-t {{ font-family: {DISPLAY}; font-size: {16 * u:.0f}px; line-height: 0.95; color: {T}; }}
.pill {{ font-family: "Poppins"; font-size: {5 * u:.0f}px; background: {A}; color: {BG}; border-radius: 999px;
  padding: {1.6 * u:.0f}px {5 * u:.0f}px; margin-top: {4 * u:.0f}px; }}
.cta-sub {{ font-family: "Poppins"; font-size: {3.6 * u:.0f}px; color: {T}; opacity: 0.85; margin-top: {4 * u:.0f}px; }}
.qr {{ margin-top: {5 * u:.0f}px; background: #F3EEE6; border-radius: {2.5 * u:.0f}px; padding: {2 * u:.0f}px;
  font-family: "Poppins"; font-size: {3 * u:.0f}px; color: #1d1512; display: flex; align-items: center; gap: {3 * u:.0f}px; text-align: left; }}
.qr img {{ width: {24 * u:.0f}px; height: {24 * u:.0f}px; }}
#cover {{ background: {BG}; }}
.cover-img {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; transform: scale(1.04); }}
.cover-img.flat {{ transform: none; }}
.cover-shade {{ position: absolute; inset: 0; background: linear-gradient(0deg, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.45) 38%,
  rgba(0,0,0,0) 62%); }}
.cover-t {{ position: absolute; left: 6%; right: 6%; bottom: 22%; text-align: center; font-family: {DISPLAY};
  font-size: {19 * u:.0f}px; line-height: 0.92; color: #fff; text-transform: uppercase;
  text-shadow: 0 {u:.0f}px {4 * u:.0f}px rgba(0,0,0,0.95); }}
.arrow {{ font-family: "Poppins"; font-size: {10 * u:.0f}px; color: {A}; margin-top: {3 * u:.0f}px; }}
"""
    index = project_dir / "index.html"
    index.write_text(f"""<!doctype html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width={W}, height={H}">
<script src="assets/gsap.min.js"></script>
<style>{css}</style>
</head>
<body>
<div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}"
     data-width="{W}" data-height="{H}" data-fps="{fps}">
{chr(10).join(html)}
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
