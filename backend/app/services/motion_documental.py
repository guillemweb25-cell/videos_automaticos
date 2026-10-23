"""
Estilo "documental" para el render motion (HyperFrames), inspirado en piezas editoriales:
fondo oscuro, imágenes como fotos impresas (polaroid con pie de foto), tipografía condensada
con UNA palabra destacada en color, cifras/fechas gigantes y textos que se van construyendo
justo cuando el narrador los dice (tiempos por palabra de AssemblyAI).

A diferencia del estilo dinámico, una escena puede abarcar VARIAS imágenes consecutivas
(campo "images"): en las escenas con foto, las nuevas caen encima de la pila; en portada y
cita se funden. Así hay pocas escenas largas que se van construyendo, como en la referencia.

Mismo contrato que motion_engine (dinámico):
  plan_scenes(paragraphs, llm_client, model)  → por párrafo, escenas con "images" (suman n_images)
  build_composition(...)                       → proyecto HyperFrames (index.html + assets/)
El render y el audio los hacen motion_engine.render_project() y motion_engine.mux_audio().

Layouts: hero (portada a sangre), photo (polaroid + columna de texto), stat (cifra gigante),
duo (dos polaroids), timeline (año · hecho), quote (cierre con frase en grande).
"""

import json
import math
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.services.motion_engine import FONTS_DIR, _esc, _group_words

LAYOUTS = ("hero", "photo", "stat", "duo", "timeline", "quote")
FADE_SECS = 0.45

# accent = palabra destacada/cifras, accent2 = segundo acento (kicker, autor de la cita).
THEMES = {
    "default": {"bg": "#14100e", "text": "#F4EDE2", "muted": "#B9AFA3",
                "accent": "#D8382C", "accent2": "#D8382C"},
    # Guía de estilo del canal: negro + dorado (título) + rojo oscuro de acento.
    "jesus": {"bg": "#100c0a", "text": "#F4EDE2", "muted": "#B8AC9C",
              "accent": "#E2B24C", "accent2": "#C9483B"},
    # Guía de estilo del canal: azul cósmico profundo + dorado vivo.
    "cabala": {"bg": "#0b1022", "text": "#F1ECE0", "muted": "#9FA8BF",
               "accent": "#F2C14E", "accent2": "#8FB3E8",
               "bg_css": "radial-gradient(ellipse at 30% 20%, #1a2a5c 0%, #0b1022 60%)"},
}


def theme_for_channel(channel_folder: str) -> Dict:
    folder = (channel_folder or "").lower()
    for key, theme in THEMES.items():
        if key != "default" and key in folder:
            return theme
    return THEMES["default"]


def scene_image_counts(scenes: List[Dict]) -> List[int]:
    return [max(1, int(s.get("images") or 1)) for s in scenes]


# ─── 1. Director ─────────────────────────────────────────────────────

SYSTEM_MSG = (
    "Eres el director de arte de un canal documental de YouTube. La narración ya existe; tú "
    "diseñas los textos que aparecen en pantalla, como en un documental editorial. Cada párrafo "
    "trae el número EXACTO de escenas S que debes devolver para él (cada escena dura ~15 s y "
    "puede mostrar varias fotos que se apilan mientras habla el narrador, así que cada escena "
    "debe cubrir una idea completa del párrafo, en orden).\n"
    "Layouts:\n"
    "- hero: imagen a sangre + titular enorme. Para la PRIMERA escena del vídeo y giros fuertes.\n"
    "- photo: foto impresa + columna de texto (title + body, y opcional title2 + body2 más tarde). "
    "Es el layout base.\n"
    "- stat: una cifra/fecha GIGANTE (number: '1531', '40', '12 OCT') + title corto + body. "
    "Úsalo siempre que la narración diga un año, fecha o cantidad importante.\n"
    "- duo: dos fotos + una frase (title).\n"
    "- timeline: 2-3 hitos 'año · hecho' (items) cuando el párrafo encadena varias fechas.\n"
    "- quote: frase final potente (title) + quote_by. Para la ÚLTIMA escena del vídeo.\n"
    "Campos: layout, kicker (2-5 palabras de contexto, ej. 'ZARAGOZA · SIGLO I', SOLO con datos "
    "que diga la narración; si no, vacío), title (2-7 palabras con EXACTAMENTE UNA palabra o expresión clave entre "
    "asteriscos, ej. 'ZARAGOZA *OBEDECE* A UNA COLUMNA'), body (máx. 20 palabras, resume, no "
    "copies frases enteras), title2/body2, caption (pie de foto de 2-5 palabras, como en un "
    "museo), number, items [{year, text}], quote_by (solo si la frase la dijo una persona "
    "concreta de la historia; si no, vacío), vintage (true si la escena ocurre entre "
    "1850 y 1960: se verá como foto antigua), at: frases EXACTAS de 3-6 palabras copiadas de la "
    "narración del párrafo que marcan cuándo aparece cada texto: {body, number, title2, items: [...]}.\n"
    "Reglas: idioma de la narración, sin emojis, nada inventado que no diga el texto (ni fechas "
    "ni lugares). Las cifras SIEMPRE con dígitos ('150 salmos', no 'ciento cincuenta'). Cada escena con un título DISTINTO. No repitas el mismo layout más de dos veces "
    "seguidas.\n"
    "Responde SOLO JSON: {\"paragraphs\": [[escena, ...], ...]}, una lista por párrafo con "
    "EXACTAMENTE S escenas."
)


def _clean(s, n: int) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()[:n]


def _fallback_scenes(text: str, n_images: int, first: bool) -> List[Dict]:
    """Sin LLM (o si falla): una escena cada ~3 imágenes, titulada con frases distintas."""
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x.strip()]
    n_scenes = max(1, math.ceil(n_images / 3))
    scenes = []
    for k in range(n_scenes):
        words = (sentences[k] if k < len(sentences) else (sentences[-1] if sentences else "")).split()[:5]
        if words:
            words[-1] = f"*{words[-1].strip('.,;:!?')}*"
        scenes.append({"layout": "hero" if first and k == 0 else "photo", "title": " ".join(words).upper()})
    return scenes


def _n_scenes(p: Dict) -> int:
    """~15 s por escena (sin pasarse del número de imágenes)."""
    secs = float(p.get("secs") or p["n_images"] * 8)
    return max(1, min(p["n_images"], round(secs / 15.0)))


def _distribute(n_images: int, wanted: List[int]) -> List[int]:
    """Reparte n_images entre las escenas respetando lo pedido por el LLM si cuadra."""
    k = len(wanted)
    if sum(wanted) == n_images and all(w >= 1 for w in wanted):
        return wanted
    base, extra = divmod(n_images, k)
    return [base + (1 if i < extra else 0) for i in range(k)]


def _normalize_scene(s: Dict) -> Dict:
    at = s.get("at") if isinstance(s.get("at"), dict) else {}
    items = []
    for it in (s.get("items") or [])[:3]:
        # Un hito sin cifra en el "año" es relleno del LLM ("año · mes").
        if isinstance(it, dict) and it.get("text") and re.search(r"\d", str(it.get("year") or "")):
            items.append({"year": _clean(it.get("year"), 12), "text": _clean(it.get("text"), 60)})
    try:
        images = max(1, int(s.get("images") or 1))
    except (TypeError, ValueError):
        images = 1
    scene = {
        "layout": s.get("layout") if s.get("layout") in LAYOUTS else "photo",
        "images": images,
        "kicker": _clean(s.get("kicker"), 40),
        "title": _clean(s.get("title"), 70),
        "body": _clean(s.get("body"), 160),
        "caption": _clean(s.get("caption"), 40),
        "number": _clean(s.get("number"), 10),
        "title2": _clean(s.get("title2"), 50),
        "body2": _clean(s.get("body2"), 140),
        "items": items,
        "quote_by": _clean(s.get("quote_by"), 50),
        "vintage": bool(s.get("vintage")),
        "at": {
            "body": _clean(at.get("body"), 80), "number": _clean(at.get("number"), 80),
            "title2": _clean(at.get("title2"), 80),
            "items": [_clean(a, 80) for a in (at.get("items") or [])][:3],
        },
    }
    return scene


def _fix_layout(scene: Dict) -> Dict:
    lay = scene["layout"]
    # La cifra gigante tiene que ser una cifra ("MILLONES" no) y de más de un carácter.
    num = scene["number"]
    if lay == "stat" and (len(num.replace(" ", "")) < 2 or not re.search(r"\d", num)):
        lay = "photo"
    # Un título que solo repite la cifra ("20" bajo un "20") sobra.
    if lay == "stat" and _norm(scene["title"].replace("*", "")) == _norm(num):
        scene["title"] = ""
    # Siempre una palabra destacada: si el LLM no la marca, la más larga.
    for key in ("title", "title2"):
        t = scene[key]
        if t and "*" not in t:
            ws = t.split()
            k = max(range(len(ws)), key=lambda x: len(ws[x].strip(".,;:!?¿¡")))
            ws[k] = f"*{ws[k]}*"
            scene[key] = " ".join(ws)
    if lay == "timeline" and len(scene["items"]) < 2:
        lay = "photo"
    if lay in ("hero", "quote", "duo") and not scene["title"]:
        lay = "photo"
    if lay == "duo" and scene["images"] < 2:
        lay = "photo"
    # Rellenos que el LLM a veces copia del prompt o inventa.
    scene["kicker"] = " · ".join(
        p for p in (x.strip() for x in scene["kicker"].split("·"))
        if p and _norm(p) not in ("epoca", "lugar", "fecha", "contexto"))
    if _norm(scene["quote_by"]) in ("narrador", "elnarrador", "anonimo", "voz", "vozenoff"):
        scene["quote_by"] = ""
    scene["layout"] = lay
    return scene


def plan_scenes(paragraphs: List[Dict], llm_client=None, model: str = "gpt-4o-mini",
                chunk: int = 5) -> List[List[Dict]]:
    """paragraphs: [{"text", "n_images"}] → por párrafo, escenas cuyo "images" suma n_images.
    Nunca lanza: si el LLM falla o no cuadra, fallback."""
    plan: List[List[Dict]] = []
    for c0 in range(0, len(paragraphs), chunk):
        part = paragraphs[c0:c0 + chunk]
        raw = []
        if llm_client is not None:
            listing = "\n\n".join(
                f"PÁRRAFO {c0 + i + 1} (S = {_n_scenes(p)} escenas)"
                f"{' — PRIMER párrafo del vídeo' if c0 + i == 0 else ''}"
                f"{' — ÚLTIMO párrafo del vídeo' if c0 + i == len(paragraphs) - 1 else ''}:\n{p['text']}"
                for i, p in enumerate(part))
            try:
                resp = llm_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "system", "content": SYSTEM_MSG},
                              {"role": "user", "content": listing}],
                    temperature=0.6,
                    response_format={"type": "json_object"},
                )
                raw = json.loads(resp.choices[0].message.content or "{}").get("paragraphs") or []
            except Exception as e:
                print(f"[documental] director LLM falló en bloque {c0}: {e}; uso fallback", flush=True)
        for i, p in enumerate(part):
            n, want = p["n_images"], _n_scenes(p)
            got = [s for s in (raw[i] if i < len(raw) and isinstance(raw[i], list) else []) if isinstance(s, dict)]
            if len(got) < want:
                got += _fallback_scenes(p["text"], n, c0 + i == 0 and not got)[len(got):want]
            got = got[:want] or _fallback_scenes(p["text"], n, c0 + i == 0)[:1]
            scenes = [_normalize_scene(s) for s in got]
            # El reparto de imágenes lo hacemos nosotros (el LLM no cuenta bien).
            for s, k in zip(scenes, _distribute(n, [0] * len(scenes))):
                s["images"] = k
            plan.append([_fix_layout(s) for s in scenes])

    flat = [s for para in plan for s in para]
    # Variedad: de cada tres "photo" seguidas, la tercera pasa a portada a sangre.
    run = 0
    for s in flat:
        run = run + 1 if s["layout"] == "photo" else 0
        if run == 3 and s["title"] and not s["title2"]:
            s["layout"] = "hero"
            run = 0
    if flat:
        if flat[0]["title"]:
            flat[0]["layout"] = "hero"
        if len(flat) > 1 and flat[-1]["title"]:
            flat[-1]["layout"] = "quote"
    return plan


# ─── 2. Sincronía con la narración ───────────────────────────────────

def _norm(w: str) -> str:
    w = unicodedata.normalize("NFKD", w.lower())
    return re.sub(r"[^a-z0-9ñ]", "", "".join(c for c in w if not unicodedata.combining(c)))


def _anchor_time(anchor: str, words: List[Dict], norm_words: List[str],
                 t_lo: float, t_hi: float) -> Optional[float]:
    """Segundo en que el narrador empieza a decir `anchor` dentro de [t_lo, t_hi]."""
    toks = [t for t in (_norm(x) for x in (anchor or "").split()) if t][:4]
    if not toks or not words:
        return None
    for i, w in enumerate(words):
        ws = w["start"] / 1000.0
        if ws < t_lo - 1.0:
            continue
        if ws > t_hi:
            break
        if all(i + k < len(norm_words) and norm_words[i + k] == t for k, t in enumerate(toks)):
            return ws
    return None


# ─── 3. Composición ──────────────────────────────────────────────────

def _rich(text: str) -> str:
    """'ZARAGOZA *OBEDECE* A' → HTML escapado con <em> en la parte destacada."""
    parts = re.split(r"\*([^*]+)\*", text or "")
    return "".join(f"<em>{_esc(p)}</em>" if i % 2 else _esc(p) for i, p in enumerate(parts))


def _lines(text: str, max_chars: int) -> List[str]:
    """Corta un titular en líneas (respetando los *destacados*) para revelarlas una a una."""
    out, cur = [], []
    for w in (text or "").split():
        plain_len = len(" ".join(x.replace("*", "") for x in cur + [w]))
        if cur and plain_len > max_chars:
            out.append(" ".join(cur))
            cur = []
        cur.append(w)
    if cur:
        out.append(" ".join(cur))
    # Un destacado partido entre líneas se cierra/abre en cada una.
    fixed, open_em = [], False
    for ln in out:
        if open_em:
            ln = "*" + ln
        open_em = ln.count("*") % 2 == 1
        fixed.append(ln + ("*" if open_em else ""))
    return fixed


# Desplazamientos (en % del ancho/alto) y giros de cada foto nueva de la pila.
PILE = [(0.0, 0.0, -2.5), (2.2, 3.0, 3.0), (-1.8, 5.0, -1.2), (3.0, 1.5, 2.2), (-2.5, 3.5, -3.0)]


def build_composition(
    project_dir: Path,
    segments: List[Dict],
    scenes: List[Dict],
    words: Optional[List[Dict]],
    out_size: Tuple[int, int],
    theme: Dict,
    fps: int = 24,
    end_cards: Optional[List[Dict]] = None,
    qr: Optional[Dict] = None,
) -> Tuple[Path, float]:
    """segments: uno por imagen; scenes: con "images" (consumen segmentos consecutivos).
    qr: {"url": str, "label": str} → tarjeta QR integrada (30 s de cada minuto)."""
    W, H = out_size
    vertical = H > W
    vh = H / 100.0
    unit = (W if vertical else H) / 100.0  # tamaño de letra según el lado corto
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

    norm_words = [_norm(w["text"]) for w in (words or [])]
    sections: List[str] = []
    js: List[str] = []

    def reveal(sel: str, t: float, kind: str = "up"):
        if kind == "line":
            js.append(f'tl.fromTo("{sel}", {{yPercent: 112, opacity: 1}}, {{yPercent: 0, opacity: 1, duration: 0.6, ease: "power3.out", immediateRender: false}}, {t:.3f});')
        elif kind == "punch":
            js.append(f'tl.fromTo("{sel}", {{scale: 1.35, opacity: 0}}, {{scale: 1, opacity: 1, duration: 0.55, ease: "power4.out", immediateRender: false}}, {t:.3f});')
        else:
            js.append(f'tl.fromTo("{sel}", {{y: {int(2.2 * vh)}, opacity: 0}}, {{y: 0, opacity: 1, duration: 0.55, ease: "power2.out", immediateRender: false}}, {t:.3f});')

    def title_html(el_id: str, text: str, cls: str, max_chars: int) -> Tuple[str, List[str]]:
        ids, rows = [], []
        for k, ln in enumerate(_lines(text, max_chars)):
            lid = f"{el_id}-l{k}"
            ids.append(lid)
            rows.append(f'<span class="ln"><span class="li" id="{lid}">{_rich(ln)}</span></span>')
        return f'<div class="{cls}" id="{el_id}">{"".join(rows)}</div>', ids

    def pile(prefix: str, segs: List[Dict], caption: str, c0: float, cd: float, t_first: float,
             end: float, vintage: bool, base_cls: str, rot0: float) -> str:
        """Pila de polaroids: la primera entra en t_first y cada imagen siguiente cae encima
        repartidas a lo largo de la escena (las de debajo siguen visibles)."""
        html_out = []
        n = len(segs)
        for j, sg in enumerate(segs):
            pid = f"{prefix}{j}"
            dx, dy, r = PILE[j % len(PILE)]
            r = rot0 if j == 0 else r
            cap = f'<figcaption>{_esc(caption)}</figcaption>' if caption and j == n - 1 else ""
            html_out.append(
                f'<figure class="pol {base_cls}" id="{pid}" style="z-index:{j + 1};margin-left:{dx * W / 100:.0f}px;'
                f'margin-top:{dy * vh:.0f}px"><div class="frame">'
                f'{media(sg["path"], pid + "-i", "ph" + (" vintage" if vintage else ""), c0, cd)}</div>{cap}</figure>')
            t_in = t_first if j == 0 else max(t_first + 1.2, sg["start"] + 0.15)
            t_in = min(t_in, end - 1.0)
            js.append(f'tl.fromTo("#{pid}", {{opacity: 0, scale: 1.14, rotation: {r + 7 * (1 if j % 2 else -1)}, y: {int(3 * vh)}}}, '
                      f'{{opacity: 1, scale: 1, rotation: {r}, y: 0, duration: 0.85, ease: "power3.out", immediateRender: false}}, {t_in:.3f});')
            js.append(f'tl.fromTo("#{pid}-i", {{scale: 1.0}}, {{scale: 1.08, duration: {max(0.5, end - t_in):.3f}, ease: "none", immediateRender: false}}, {t_in:.3f});')
        return "".join(html_out)

    seg_i = 0
    total = 0.0
    for i, sc in enumerate(scenes):
        # Reaplica las reglas también a planes cacheados con versiones anteriores.
        sc = _fix_layout(_normalize_scene(sc))
        k_img = max(1, int(sc.get("images") or 1))
        segs = segments[seg_i:seg_i + k_img]
        seg_i += k_img
        if not segs:
            break
        sid = f"s{i:03d}"
        start = segs[0]["start"]
        end = segs[-1]["start"] + segs[-1]["duration"]
        dur = end - start
        lead = FADE_SECS if i > 0 else 0.0
        c0 = max(0.0, start - lead)
        cd = end - c0
        total = max(total, end)
        layout = sc["layout"]
        if layout == "duo" and len(segs) < 2:
            layout = "photo"
        side = "right" if i % 2 == 0 else "left"
        rot = [-2.5, 2.0, -1.5, 2.8, -2.0][i % 5]
        at = sc.get("at") or {}

        def when(anchor_key: str, default: float, idx: Optional[int] = None) -> float:
            a = at.get(anchor_key)
            if idx is not None:
                a = a[idx] if isinstance(a, list) and idx < len(a) else ""
            t = _anchor_time(a, words or [], norm_words, start, end - 0.8) if a else None
            t = default if t is None else t - 0.1
            return min(max(t, c0 + lead + 0.3), end - 0.9)

        # Lo primero entra durante el fundido de entrada: nunca queda el fondo vacío.
        t_title = c0 + 0.1
        title_ids: List[str] = []

        if layout in ("hero", "quote"):
            tmax = 16 if vertical else (20 if layout == "hero" else 26)
            th, title_ids = title_html(f"{sid}-t", sc["title"], "t-hero" if layout == "hero" else "t-quote", tmax)
            kick = f'<div class="kicker rv" id="{sid}-k">{_esc(sc["kicker"])}</div>' if sc["kicker"] and layout == "hero" else ""
            by = f'<div class="by rv" id="{sid}-by">{_esc(sc["quote_by"])}</div>' if layout == "quote" and sc["quote_by"] else ""
            body = f'<div class="body rv" id="{sid}-b">{_esc(sc["body"])}</div>' if layout == "hero" and sc["body"] else ""
            bgs = []
            for j, sg in enumerate(segs):
                bid = f"{sid}-i{j}"
                # Las siguientes empiezan ocultas (si no, la de encima tapa a la primera
                # desde el principio y "parpadea" al llegar su fundido).
                bgs.append(media(sg["path"], bid, "fullimg bgx" + (" vintage" if sc["vintage"] else "")
                                 + (" later" if j > 0 else ""), c0, cd))
                t_in = c0 if j == 0 else sg["start"] - 0.6
                js.append(f'tl.fromTo("#{bid}", {{scale: 1.0}}, {{scale: 1.1, duration: {end - t_in:.3f}, ease: "none", immediateRender: false}}, {t_in:.3f});')
                if j > 0:
                    js.append(f'tl.fromTo("#{bid}", {{opacity: 0}}, {{opacity: 1, duration: 1.0, ease: "power1.inOut", immediateRender: false}}, {t_in:.3f});')
            inner = (f'<div class="full">{"".join(bgs)}</div><div class="shade {layout}"></div>'
                     f'<div class="txt-{layout}">{kick}{th}{body}{by}</div>')
            if kick:
                reveal(f"#{sid}-k", t_title)
            for k, lid in enumerate(title_ids):
                reveal(f"#{lid}", t_title + 0.15 + k * 0.32, "line")
            if body:
                reveal(f"#{sid}-b", when("body", t_title + 0.6 + len(title_ids) * 0.32))
            if by:
                reveal(f"#{sid}-by", t_title + 0.5 + len(title_ids) * 0.32)

        elif layout == "duo":
            half = max(1, len(segs) // 2)
            a = pile(f"{sid}-a", segs[:half], sc["caption"], c0, cd, t_title, end, sc["vintage"], "duo-a", rot)
            b = pile(f"{sid}-b", segs[half:], "", c0, cd, t_title + 0.4, end, sc["vintage"], "duo-b", -rot)
            th, title_ids = title_html(f"{sid}-t", sc["title"], "t-col", 18 if vertical else 32)
            inner = f'{a}{b}<div class="txt-duo">{th}</div>'
            for k, lid in enumerate(title_ids):
                reveal(f"#{lid}", when("body", t_title + 1.2) + k * 0.3, "line")

        else:  # photo / stat / timeline
            pol = pile(f"{sid}-p", segs, sc["caption"], c0, cd, t_title, end, sc["vintage"], f"side-{side}", rot)
            col = []
            if layout == "stat":
                # Las cifras largas ("12 OCT", "20.000") se encogen para no invadir la foto.
                shrink = min(1.0, 4.5 / max(1, len(sc["number"])))
                col.append(f'<div class="num rv" id="{sid}-n" style="font-size:{unit * (32 if vertical else 27) * shrink:.0f}px">'
                           f'{_esc(sc["number"])}</div>')
                t_num = when("number", t_title + 0.4)
                reveal(f"#{sid}-n", t_num, "punch")
                if sc["title"]:
                    th, title_ids = title_html(f"{sid}-t", sc["title"], "t-sub", 16 if vertical else 22)
                    col.append(th)
                for k, lid in enumerate(title_ids):
                    reveal(f"#{lid}", t_num + 0.5 + k * 0.28, "line")
                if sc["body"]:
                    col.append(f'<div class="body rv" id="{sid}-b">{_esc(sc["body"])}</div>')
                    reveal(f"#{sid}-b", max(when("body", t_num + 1.2), t_num + 0.8))
            elif layout == "timeline":
                if sc["title"]:
                    th, title_ids = title_html(f"{sid}-t", sc["title"], "t-col", 16 if vertical else 18)
                    col.append(th)
                for k, lid in enumerate(title_ids):
                    reveal(f"#{lid}", t_title + 0.1 + k * 0.3, "line")
                n = len(sc["items"])
                rows = []
                for k, it in enumerate(sc["items"]):
                    rows.append(f'<div class="ev rv" id="{sid}-e{k}"><span class="yr">{_esc(it["year"])}</span>'
                                f'<span class="dot">·</span><span>{_esc(it["text"])}</span></div>')
                    default = t_title + 1.0 + k * max(1.2, (dur - 2.5) / max(1, n))
                    reveal(f"#{sid}-e{k}", when("items", default, k))
                col.append(f'<div class="events">{"".join(rows)}</div>')
            else:
                if sc["kicker"]:
                    col.append(f'<div class="kicker rv" id="{sid}-k">{_esc(sc["kicker"])}</div>')
                    reveal(f"#{sid}-k", t_title)
                if sc["title"]:
                    th, title_ids = title_html(f"{sid}-t", sc["title"], "t-col", 16 if vertical else 18)
                    col.append(th)
                for k, lid in enumerate(title_ids):
                    reveal(f"#{lid}", t_title + 0.15 + k * 0.3, "line")
                if sc["body"]:
                    col.append(f'<div class="body rv" id="{sid}-b">{_esc(sc["body"])}</div>')
                    reveal(f"#{sid}-b", when("body", t_title + 0.8 + len(title_ids) * 0.3))
                if sc["title2"]:
                    th2, ids2 = title_html(f"{sid}-t2", sc["title2"], "t-col t2", 16 if vertical else 18)
                    col.append(th2)
                    t2 = when("title2", start + dur * 0.5)
                    for k, lid in enumerate(ids2):
                        reveal(f"#{lid}", t2 + k * 0.3, "line")
                    if sc["body2"]:
                        col.append(f'<div class="body rv" id="{sid}-b2">{_esc(sc["body2"])}</div>')
                        reveal(f"#{sid}-b2", t2 + 0.6 + len(ids2) * 0.3)
            inner = f'{pol}<div class="col col-{"left" if side == "right" else "right"}">{"".join(col)}</div>'

        sections.append(
            f'<section id="{sid}" class="clip scene" style="z-index:{10 + i}" data-start="{c0:.3f}" '
            f'data-duration="{cd:.3f}" data-track-index="1">{inner}</section>')
        if i > 0:
            js.append(f'tl.fromTo("#{sid}", {{opacity: 0}}, {{opacity: 1, duration: {FADE_SECS}, ease: "power1.out", immediateRender: false}}, {c0:.3f});')

    # Tarjetas finales (miniatura + logo), como en los otros modos.
    t_cursor = total
    for k, card in enumerate(end_cards or []):
        cid = f"end{k}"
        fit = "contain" if card.get("kind") == "logo" else "cover"
        sections.append(
            f'<section id="{cid}" class="clip scene" style="z-index:{900 + k}" data-start="{t_cursor:.3f}" '
            f'data-duration="{card["duration"]:.3f}" data-track-index="1"><div class="full">'
            f'<img id="{cid}-i" class="fullimg" style="object-fit:{fit}" src="{asset(card["path"])}" alt=""></div></section>')
        js.append(f'tl.fromTo("#{cid}", {{opacity: 0}}, {{opacity: 1, duration: 0.5, immediateRender: false}}, {t_cursor:.3f});')
        js.append(f'tl.fromTo("#{cid}-i", {{scale: 1.0}}, {{scale: 1.05, duration: {card["duration"]:.3f}, ease: "none", immediateRender: false}}, {t_cursor:.3f});')
        t_cursor += card["duration"]
    if end_cards:
        js.append(f'tl.to("#root", {{opacity: 0, duration: 1.0}}, {t_cursor - 1.0:.3f});')
    narr_end = total
    total = t_cursor

    # Subtítulos discretos: frases de hasta 7 palabras, la palabra activa en color.
    caps: List[str] = []
    groups = _group_words(words or [], max_words=7, max_gap_ms=450)
    for g_i, group in enumerate(groups):
        g0 = group[0]["start"] / 1000.0
        if g0 >= narr_end:
            break
        g1 = group[-1]["end"] / 1000.0 + 0.15
        if g_i + 1 < len(groups):
            g1 = min(g1, groups[g_i + 1][0]["start"] / 1000.0)
        g1 = min(g1, narr_end)
        cid = f"c{g_i:04d}"
        spans = "".join(f'<span class="w" id="{cid}-{k}">{_esc(w["text"])}</span> ' for k, w in enumerate(group))
        caps.append(f'<div id="{cid}" class="clip cap" data-start="{g0:.3f}" data-duration="{max(0.2, g1 - g0):.3f}" '
                    f'data-track-index="2"><div class="cap-line">{spans}</div></div>')
        for k, w in enumerate(group):
            ws, we = w["start"] / 1000.0, w["end"] / 1000.0
            js.append(f'tl.fromTo("#{cid}-{k}", {{color: "{theme["text"]}"}}, {{color: "{theme["accent"]}", duration: 0.06, immediateRender: false}}, {ws:.3f});')
            if k < len(group) - 1:
                js.append(f'tl.fromTo("#{cid}-{k}", {{color: "{theme["accent"]}"}}, {{color: "{theme["text"]}", duration: 0.1, immediateRender: false}}, {max(ws + 0.06, we):.3f});')

    # Tarjeta QR (libro de afiliado): 30 s de cada minuto, empezando en el 20 (no tapa el gancho).
    qr_html = ""
    if qr and qr.get("url"):
        try:
            import qrcode
            qrcode.make(qr["url"], border=1).save(assets / "qr.png")
            label = "".join(f"<div>{_esc(x)}</div>" for x in (qr.get("label") or "Compra el libro\nLink en la descripción").split("\n"))
            qr_html = f'<div id="qr" class="qr"><img src="assets/qr.png" alt=""><div class="qr-l">{label}</div></div>'
            t = 20.0
            while t + 6 < narr_end:
                off = min(t + 30.0, narr_end - 0.5)
                js.append(f'tl.fromTo("#qr", {{opacity: 0, y: {int(-2 * vh)}}}, {{opacity: 1, y: 0, duration: 0.5, ease: "power2.out", immediateRender: false}}, {t:.3f});')
                js.append(f'tl.fromTo("#qr", {{opacity: 1}}, {{opacity: 0, duration: 0.5, immediateRender: false}}, {off:.3f});')
                t += 60.0
        except Exception as e:
            print(f"[documental] QR omitido: {e}", flush=True)

    T, M, A, A2, BG = theme["text"], theme["muted"], theme["accent"], theme["accent2"], theme["bg"]
    SCENE_BG = theme.get("bg_css") or BG
    # Bebas no tiene glifos hebreos: Times New Roman los pinta (letras como "י" en cábala).
    DISPLAY = '"Bebas", "Times New Roman", serif'
    # Medidas: horizontal = foto a un lado + columna de texto; vertical = foto arriba + texto abajo.
    if vertical:
        pol_w, pol_top = W * 0.8, H * 0.13
        geo = f"""
.pol {{ left: {(W - pol_w) / 2:.0f}px; top: {pol_top:.0f}px; width: {pol_w:.0f}px; }}
.pol .frame {{ height: {pol_w * 0.8:.0f}px; }}
.col {{ left: {W * 0.08:.0f}px; right: {W * 0.08:.0f}px; top: {pol_top + pol_w * 0.8 + H * 0.09:.0f}px; }}
.duo-a {{ left: {W * 0.05:.0f}px; top: {H * 0.08:.0f}px; width: {W * 0.62:.0f}px; }}
.duo-b {{ left: {W * 0.33:.0f}px; top: {H * 0.34:.0f}px; width: {W * 0.62:.0f}px; }}
.duo-a .frame, .duo-b .frame {{ height: {W * 0.62 * 0.75:.0f}px; }}
.txt-duo {{ left: {W * 0.08:.0f}px; right: {W * 0.08:.0f}px; top: {H * 0.66:.0f}px; }}
.txt-hero {{ left: {W * 0.08:.0f}px; right: {W * 0.08:.0f}px; bottom: {H * 0.16:.0f}px; }}
.shade.hero {{ background: linear-gradient(0deg, {BG} 8%, rgba(0,0,0,0.55) 45%, rgba(0,0,0,0.05) 75%); }}
.qr {{ right: {W * 0.05:.0f}px; top: {H * 0.03:.0f}px; }}
"""
    else:
        pol_w = W * 0.41
        pol_h = pol_w * 0.72
        pol_top = (H - pol_h) / 2 + H * 0.005
        geo = f"""
.pol {{ top: {pol_top:.0f}px; width: {pol_w:.0f}px; }}
.pol .frame {{ height: {pol_h:.0f}px; }}
.pol.side-right {{ left: {W * 0.52:.0f}px; }}
.pol.side-left {{ left: {W * 0.06:.0f}px; }}
.col {{ top: {H * 0.06:.0f}px; bottom: {H * 0.1:.0f}px; width: {W * 0.38:.0f}px; display: flex; flex-direction: column; justify-content: center; }}
.col-left {{ left: {W * 0.07:.0f}px; }}
.col-right {{ left: {W * 0.55:.0f}px; }}
.duo-a {{ left: {W * 0.07:.0f}px; top: {H * 0.08:.0f}px; width: {W * 0.4:.0f}px; }}
.duo-b {{ left: {W * 0.53:.0f}px; top: {H * 0.11:.0f}px; width: {W * 0.4:.0f}px; }}
.duo-a .frame, .duo-b .frame {{ height: {W * 0.4 * 0.62:.0f}px; }}
.txt-duo {{ left: {W * 0.07:.0f}px; right: {W * 0.07:.0f}px; top: {H * 0.7:.0f}px; }}
.txt-hero {{ left: {W * 0.06:.0f}px; width: {W * 0.58:.0f}px; bottom: {H * 0.15:.0f}px; }}
.shade.hero {{ background: linear-gradient(90deg, {BG} 0%, rgba(16,12,10,0.8) 40%, rgba(16,12,10,0.1) 80%),
  linear-gradient(0deg, rgba(16,12,10,0.75) 0%, rgba(16,12,10,0) 38%); }}
.qr {{ right: {W * 0.025:.0f}px; top: {H * 0.035:.0f}px; }}
"""
    css = f"""
@font-face {{ font-family: "Bebas"; src: url("assets/BebasNeue-Regular.ttf"); }}
@font-face {{ font-family: "Poppins"; src: url("assets/Poppins-Bold.ttf"); font-weight: 700; }}
html, body {{ margin: 0; background: {BG}; }}
#root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: {BG}; }}
#root::after {{ content: ""; position: absolute; inset: 0; z-index: 1500; pointer-events: none;
  background: radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.5) 100%); }}
.clip {{ position: absolute; inset: 0; }}
.scene {{ overflow: hidden; background: {SCENE_BG}; }}
.full {{ position: absolute; inset: 0; overflow: hidden; }}
.fullimg {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.bgx {{ position: absolute; inset: 0; }}
.bgx.later {{ opacity: 0; }}
.vintage {{ filter: grayscale(0.85) sepia(0.35) contrast(1.08) brightness(0.95); }}
.shade {{ position: absolute; inset: 0; }}
.shade.quote {{ background: radial-gradient(ellipse at center, rgba(16,12,10,0.55), rgba(16,12,10,0.88)); }}
.rv {{ opacity: 0; }}
.pol {{ position: absolute; margin: 0; opacity: 0; }}
.pol .frame {{ background: #F3EEE6; padding: {unit * 1.3:.0f}px; box-sizing: border-box; overflow: hidden;
  box-shadow: 0 {unit * 1.6:.0f}px {unit * 4:.0f}px rgba(0,0,0,0.65); }}
.pol .frame img, .pol .frame video {{ width: 100%; height: 100%; object-fit: cover; display: block; }}
.pol figcaption {{ font-family: "Poppins"; font-size: {unit * (2.6 if vertical else 1.8):.1f}px; color: {M}; margin-top: {unit * 1.3:.0f}px; }}
.col, .txt-duo, .txt-hero, .txt-quote {{ position: absolute; }}
.txt-quote {{ left: 10%; right: 10%; top: 0; bottom: 12%; display: flex; flex-direction: column;
  justify-content: center; align-items: center; text-align: center; }}
.ln {{ display: block; overflow: hidden; line-height: 0.98; padding-top: 0.04em; text-transform: uppercase; }}
.li {{ display: inline-block; opacity: 0; }}
em {{ font-style: normal; color: {A}; }}
.t-hero {{ font-family: {DISPLAY}; font-size: {unit * (12.5 if vertical else 12.5):.0f}px; color: {T}; }}
.t-quote {{ font-family: {DISPLAY}; font-size: {unit * (11 if vertical else 10.5):.0f}px; color: {T}; }}
.t-col {{ font-family: {DISPLAY}; font-size: {unit * (10 if vertical else 9.2):.0f}px; color: {T}; }}
.t-col.t2 {{ margin-top: {unit * 3.5:.0f}px; }}
.t-sub {{ font-family: {DISPLAY}; font-size: {unit * (7.5 if vertical else 6.2):.0f}px; color: {T}; margin-top: {unit:.0f}px; }}
.num {{ font-family: {DISPLAY}; font-size: {unit * (32 if vertical else 27):.0f}px; line-height: 0.88; color: {A}; }}
.kicker {{ font-family: "Poppins"; font-size: {unit * (3.6 if vertical else 2.7):.1f}px; color: {A2};
  text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: {unit * 1.4:.0f}px; }}
.body {{ font-family: "Poppins"; font-size: {unit * (4.4 if vertical else 3.15):.1f}px; line-height: 1.32; color: {T};
  margin-top: {unit * 2:.0f}px; }}
.by {{ font-family: "Poppins"; font-size: {unit * (3.6 if vertical else 2.7):.1f}px; color: {A2};
  text-transform: uppercase; letter-spacing: 0.08em; margin-top: {unit * 2.8:.0f}px; }}
.events {{ margin-top: {unit * 2.5:.0f}px; }}
.ev {{ font-family: {DISPLAY}; font-size: {unit * (7 if vertical else 5.6):.0f}px; color: {T}; line-height: 1.02; margin: {unit * 1.3:.0f}px 0; }}
.ev .yr {{ color: {A}; }}
.ev .dot {{ color: {M}; margin: 0 0.3em; }}
.cap {{ z-index: 2000; pointer-events: none; }}
.cap-line {{ position: absolute; left: 8%; right: 8%; bottom: {H * (0.06 if vertical else 0.045):.0f}px; text-align: center;
  font-family: "Poppins"; font-size: {unit * (3.8 if vertical else 3.0):.1f}px; line-height: 1.3;
  text-shadow: 0 2px 8px rgba(0,0,0,0.95), 0 0 2px rgba(0,0,0,0.9); }}
.w {{ color: {T}; }}
.qr {{ position: absolute; z-index: 1900; opacity: 0; background: #F3EEE6; border-radius: {unit * 1.2:.0f}px;
  padding: {unit * 1.1:.0f}px; display: flex; flex-direction: column; align-items: center;
  box-shadow: 0 {unit:.0f}px {unit * 3:.0f}px rgba(0,0,0,0.55); }}
.qr img {{ width: {unit * (17 if vertical else 12.5):.0f}px; height: {unit * (17 if vertical else 12.5):.0f}px; display: block; }}
.qr-l {{ font-family: "Poppins"; font-size: {unit * (2.5 if vertical else 1.75):.1f}px; color: #1d1512; text-align: center;
  line-height: 1.25; margin-top: {unit * 0.7:.0f}px; }}
{geo}
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
{chr(10).join(sections)}
{chr(10).join(caps)}
{qr_html}
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
