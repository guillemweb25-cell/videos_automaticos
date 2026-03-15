from typing import Dict, List, TypedDict, Optional

class StyleSpec(TypedDict, total=False):
    display_name: str
    image_style_prompt: str
    negative_prompt: str
    post_note: str
    video_style_prompt: str
    extends: str

NEGATIVE_BASE = (
    "text, captions, letters, words, watermarks, logos, frames, borders, graffiti, "
    "anime, cartoon, plastic CGI, neon oversaturation, low quality, heavy HDR, "
    "deformed anatomy, extra limbs, extra arms, deformed hands, mutated hands, "
    "fused fingers, extra fingers, missing limbs, cross-eyed, ugly, morbid, "
    "mutation, gross proportions"
)

DEFAULT_STYLE: StyleSpec = {
    "display_name": "Default Epic Cinema",
    "image_style_prompt": (
        "Photorealistic cinematic composition with natural grading, rich contrast, "
        "subtle film grain and soft halation; immersive full scene; no on-image text"
    ),
    "negative_prompt": NEGATIVE_BASE,
    "post_note": "Keep skin tones natural; very subtle grain.",
}

BASES: Dict[str, StyleSpec] = {
    "epic_base": {
        "display_name": "Epic Cinema (base)",
        "image_style_prompt": (
            "Photorealistic epic cinema; shallow depth of field; rim/back light, volumetric rays; "
            "warm highlights, deep shadows; immersive full scene; no on-image text"
        ),
        "negative_prompt": NEGATIVE_BASE,
        "post_note": "Subtle film grain; gentle highlights.",
    },
    "biblical_base": {
        "display_name": "Biblical Epic (base)",
        "image_style_prompt": (
            "Photorealistic biblical epic; historically coherent wardrobe; desert/stone landscapes; "
            "golden-hour or moonlit lighting; immersive, reverent; no on-image text"
        ),
        "negative_prompt": NEGATIVE_BASE + ", stained glass, church murals, framed paintings",
        "post_note": "Respectful tone; no kitsch glow.",
    },
    "stock_base": {
        "display_name": "Stock Photo (base)",
        "image_style_prompt": (
            "Authentic stock photography look; natural color grading (no heavy filters), "
            "soft but crisp detail; available light; candidates moments; no on-image text"
        ),
        "negative_prompt": NEGATIVE_BASE + ", brands, overprocessed HDR",
        "post_note": "Neutral grading; no aggressive filters.",
    }
}

STYLES: Dict[str, StyleSpec] = {
    "epic_cinema": {
        "extends": "epic_base",
        "display_name": "Epic Cinema",
    },
    "epic_cinema_judea": {
        "extends": "biblical_base",
        "display_name": "Epic Cinema Judea",
    },
    "stock_photo": {
        "extends": "stock_base",
        "display_name": "Stock Photo 16:9",
    },
    "deepsea": {
        "display_name": "Deep Sea Creatures",
        "image_style_prompt": (
            "Fully underwater deep-sea scene, abyssal depth. Marine creature only. "
            "Cold blue-black tones, suspended particles. Photorealistic, cinematic."
        ),
        "negative_prompt": NEGATIVE_BASE + ", human, sky, sun, landscape, boat",
    },
    "sombras_horror_nocturno": {
        "display_name": "Horror Nocturno",
        "image_style_prompt": "Dark horror atmosphere, heavy shadows, night time, eerie lighting, cinematic horror",
        "negative_prompt": NEGATIVE_BASE + ", bright, happy, sunshine",
    },
    "grabovoi_aurora": {
        "display_name": "Aurora Borealis",
        "image_style_prompt": "Beautiful aurora borealis lights, mystical atmosphere, vibrant colors, grabovoi style",
        "negative_prompt": NEGATIVE_BASE,
    },
    "cabala_luz_divina": {
        "display_name": "Cabala Luz Divina",
        "image_style_prompt": "Mystical divine light, cabala symbolism, ethereal atmosphere, spiritual glow",
        "negative_prompt": NEGATIVE_BASE,
    },
    "stock_mistic_cabala_clean": {
        "extends": "stock_base",
        "display_name": "Stock Mistic Cabala",
    },
    "senior_stock": {
        "extends": "stock_base",
        "display_name": "Senior Stock Photo",
        "image_style_prompt": (
            "Authentic stock photography of senior citizens around 70 years old; "
            "natural silver hair, gentle wrinkles, realistic skin textures; "
            "home health and wellness setting; indoor soft natural lighting; "
            "no over-processing; genuine emotions; no on-image text"
        ),
        "negative_prompt": NEGATIVE_BASE + ", young people, teenagers, children, aggressive filters, plastic skin",
    },
    "candelaria_mexico_tradicion_viva": {
        "display_name": "Candelaria México",
        "image_style_prompt": "Traditional Mexican Candelaria festival, vibrant colors, cultural celebration, photorealistic",
        "negative_prompt": NEGATIVE_BASE,
    },
    "celtico_oscuro": {
        "display_name": "Céltico Histórico",
        "image_style_prompt": (
            "Grim historically accurate 5th-century Celtic/Irish setting; rugged landscapes, "
            "damp mist, overcast skies; wool and leather textures; torchlight or cold natural light; "
            "cinematic moody atmosphere; photorealistic, raw"
        ),
        "negative_prompt": NEGATIVE_BASE + ", modern buildings, electricity, bright colors, happy tone",
    }
}

ALIASES = {
    "epic": "epic_cinema",
    "epicjudea": "epic_cinema_judea",
    "horror": "sombras_horror_nocturno",
    "aurora": "grabovoi_aurora",
    "cabala": "cabala_luz_divina",
    "deepsea": "deepsea",
    "cabalastock": "stock_mistic_cabala_clean",
    "stocksenior": "senior_stock",
    "candelaria": "candelaria_mexico_tradicion_viva",
    "stock": "stock_photo",
    "stock16x9": "stock_photo",
    "stock9x16": "stock_photo",
    "stockthumb": "stock_photo",
    "celtico": "celtico_oscuro",
}

class StyleService:
    @staticmethod
    def get_style(name: str) -> dict:
        key = ALIASES.get(name.lower(), name.lower())
        try:
            return StyleService._resolve(key)
        except:
            return StyleService._resolve("epic_cinema")

    @staticmethod
    def _resolve(name: str, seen=None) -> dict:
        if seen is None: seen = set()
        if name in seen: raise ValueError("Circular inheritance")
        seen.add(name)

        s = STYLES.get(name)
        if not s: raise KeyError(f"Style {name} not found")

        base_key = s.get("extends")
        if base_key:
            base = BASES.get(base_key) or STYLES.get(base_key)
            parent = StyleService._merge(DEFAULT_STYLE, base) if base_key in BASES else StyleService._resolve(base_key, seen)
            return StyleService._merge(parent, s)

        return StyleService._merge(DEFAULT_STYLE, s)

    @staticmethod
    def _merge(a: dict, b: dict) -> dict:
        out = a.copy()
        out.update(b or {})
        out.pop("extends", None)
        return out

    @staticmethod
    def list_styles() -> List[str]:
        return sorted(list(STYLES.keys()) + list(ALIASES.keys()))

    @staticmethod
    def get_channel_style(channel, fallback_name: str = "epic_cinema") -> dict:
        """Returns channel-specific style if configured, otherwise falls back to named style."""
        if channel and getattr(channel, "image_style_prompt", None):
            return {
                "display_name": f"Custom ({channel.name})",
                "image_style_prompt": channel.image_style_prompt,
                "negative_prompt": channel.negative_prompt or NEGATIVE_BASE,
                "post_note": "",
            }
        return StyleService.get_style(fallback_name)
