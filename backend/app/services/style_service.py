from typing import Dict, List, TypedDict, Optional, Any
from pathlib import Path
import re

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
    "mutation, gross proportions, backwards feet, inverted limbs, floating limbs, "
    "elongated limbs, disproportionate arms, long arms, lanky, rubbery limbs, "
    "deformed body, anatomical nonsense, nudity, naked, nsfw, nipple, breast, buttocks, "
    "erotic, sexual, explicit, genitals"
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
            "Photorealistic biblical epic; historically coherent wardrobe; modest fully-clothed characters, completely covered bodies; desert/stone landscapes; "
            "golden-hour or moonlit lighting; immersive, reverent; no on-image text"
        ),
        "negative_prompt": NEGATIVE_BASE + ", stained glass, church murals, framed paintings, nudity, shirtless, naked",
        "post_note": "Respectful tone; no kitsch glow; CLOTHING STRICTNESS: You MUST explicitly describe the clothing for ALL characters (e.g., 'wearing a thick woolen tunic', 'fully clothed in period-accurate robes'). NEVER leave clothing unspecified. ABSOLUTELY NO nakedness, no bare chests, no exposed skin other than face/hands.",
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
        "display_name": "Terror Cómic (México)",
        "image_style_prompt": "Dark horror atmosphere, heavy shadows, night time, eerie lighting, comic book horror style, detailed ink, dramatic shading",
        "negative_prompt": NEGATIVE_BASE + ", bright, happy, sunshine, photorealistic, photography",
    },
    "sombras_realismo_sucio": {
        "extends": "epic_base",
        "display_name": "Realismo Sucio (México)",
        "image_style_prompt": (
            "Gritty realistic Mexican rural setting; desolate dusty roads, weathered faces, "
            "rustic textures; dramatic shadows, cinematic chiaroscuro; "
            "hyper-realistic, high contrast, filmic texture; no comic style, no drawing"
        ),
        "negative_prompt": NEGATIVE_BASE + ", illustration, drawing, painting, comic, anime, sketch, cartoony",
    },
    "sombras_cinematico": {
        "extends": "sombras_realismo_sucio",
        "display_name": "Realismo Cinemático",
    },
    "sombras_cinematico_ultra": {
        "extends": "sombras_realismo_sucio",
        "display_name": "Realismo Cinemático (Ultra)",
    },
    "grabovoi_aurora": {
        "display_name": "Aurora Borealis",
        "image_style_prompt": "Beautiful aurora borealis lights, mystical atmosphere, vibrant colors, grabovoi style",
        "negative_prompt": NEGATIVE_BASE,
    },
    "grabovoi_mystic": {
        "display_name": "Grabovoi Mystic",
        "image_style_prompt": (
            "Mystical spiritual photography with cosmic-energy aesthetic; "
            "divine golden light beams, ethereal glows, floating golden particles and sparkles, "
            "sacred geometry patterns subtly visible, abundance/prosperity mood, "
            "deep velvet sky with nebulae and soft starlight, photorealistic with magical elements, "
            "soft volumetric lighting, gold and deep-blue color grading, depth of field bokeh, "
            "inspiring uplifting tone, no on-image text or digits."
        ),
        "negative_prompt": NEGATIVE_BASE + ", literal numbers in image, garbled digits, illegible text, dark depressing mood, horror, dull flat lighting",
        "post_note": (
            "Visualize the FEELING / OUTCOME of the Grabovoi sequence (abundance, healing, love, "
            "protection, etc.) rather than literal numbers. Numerical sequence goes only as text overlay "
            "on thumbnail. Focus on cosmic/mystical metaphors. Avoid clichés (crystal balls, tarot)."
        ),
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
    },
    "cabala_legacy_master": {
        "extends": "biblical_base",
        "display_name": "Cabala Legacy Master",
        "image_style_prompt": (
            "Masterpiece cinematic vision, hyper-realistic mystical atmosphere; "
            "ancient sandstone sanctuaries with intricate hand-carved spiritual engravings; "
            "blinding ethereal light emanations, shimmering crystalline diffraction, and divine cosmic dust particles; "
            "glowing Hebrew letters of liquid fire floating in a dramatic chiaroscuro composition; "
            "interconnected golden threads of reality; Unreal Engine 5 render style, 8k, "
            "extremely detailed textures, epic high-end legacy film grading; profound spiritual immersion; no on-image text"
        ),
    },
    "biblical_classic": {
        "display_name": "Biblical Classic",
        "image_style_prompt": "Epic cinematic biblical photography, modest fully-clothed characters, all bodies covered with tunics, soft natural lighting, historically accurate textures and fully-covered robes, desert landscapes of ancient Judea, majestic atmosphere, high contrast, photorealistic, 8k, sharp focus on faces and respectful expressions.",
        "negative_prompt": NEGATIVE_BASE + ", modern architecture, technology, cars, electrical lines, text, watermarks, frames, borders, cartoon, anime, plastic CGI, extra limbs, deformed hands, stained glass, kitsch glow, church murals, framed paintings, distorted anatomy, low quality, lens flare, bright starburst sun, nudity, naked, shirtless, bare skin.",
        "post_note": "Respectful tone; CLOTHING STRICTNESS: You MUST explicitly describe the clothing for ALL characters (e.g., 'wearing a thick woolen tunic', 'fully clothed in period-accurate robes'). NEVER leave clothing unspecified. ABSOLUTELY NO nakedness, no bare chests, no exposed skin other than face/hands."
    },
    "onirico_suenos": {
        "display_name": "Onírico (Sueños)",
        "image_style_prompt": (
            "Surreal oniric atmosphere, ethereal soft lighting, mystical glowing particles, "
            "dream-like composition, hazy backgrounds, blurred edges, floating elements, "
            "soft pastel accents amidst deep shadows, transcendental and symbolic; "
            "hyper-detailed but mystical; cinematic film grain; masterpiece"
        ),
        "negative_prompt": NEGATIVE_BASE + ", sharp edges, harsh lighting, boring, realistic photography, ordinary life",
    },
    "anime_hentai": {
        "display_name": "Anime / Hentai",
        "image_style_prompt": (
            "High-quality anime illustration, vibrant colors, clean lineart, "
            "cel shaded, cinematic anime lighting, detailed eyes, expressive characters, "
            "masterpiece, anime key visual style; no on-image text"
        ),
        "negative_prompt": NEGATIVE_BASE + ", photorealistic, realistic, 3d render, western cartoon, fat, muscular, ugly, old, low quality, bad anatomy",
        "post_note": "Keep features clean and stylized.",
    }
}

ALIASES = {
    "epic": "epic_cinema",
    "epicjudea": "epic_cinema_judea",
    "horror": "sombras_horror_nocturno",
    "sombras_comic": "sombras_horror_nocturno",
    "realismo_mexicano": "sombras_realismo_sucio",
    "sombras_real": "sombras_realismo_sucio",
    "cinematico": "sombras_cinematico",
    "cinematico_ultra": "sombras_cinematico_ultra",
    "aurora": "grabovoi_aurora",
    "grabovoi": "grabovoi_mystic",
    "grabovoimystic": "grabovoi_mystic",
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
    "cabalalegacy": "cabala_legacy_master",
    "legacy": "cabala_legacy_master",
    "biblical_classic": "biblical_classic",
    "onirico": "onirico_suenos",
    "suenos": "onirico_suenos",
    "canal_personalizado": "canal_personalizado",
    "anime": "anime_hentai",
    "hentai": "anime_hentai",
}


class StyleService:
    @staticmethod
    def get_style(name: str, channel=None) -> dict:
        if name.lower() == "canal_personalizado":
            if channel and channel.image_style_prompt:
                return {
                    "display_name": f"Estilo del Canal ({channel.name})",
                    "image_style_prompt": channel.image_style_prompt,
                    "negative_prompt": channel.negative_prompt or NEGATIVE_BASE,
                    "post_note": "",
                }
            name = "epic_cinema"
            
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

    @staticmethod
    def get_custom_thumbnail_rules(base_dir: Path) -> Optional[str]:
        """Reads style-guide.md from channel base dir and extracts the thumbnail section."""
        # base_dir is usually cache/000X-channel-name/YYYY-MM-DD-video-slug
        # style-guide.md is usually in cache/000X-channel-name/style-guide.md
        guide_path = base_dir.parent.parent / "style-guide.md"
        if not guide_path.exists():
            return None
        
        try:
            content = guide_path.read_text(encoding="utf-8")
            # Extract section between "## 🎨 SISTEMA DE THUMBNAILS" and the next "##"
            pattern = r"##.*?SISTEMA DE THUMBNAILS(.*?)(?=##|$)"
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        except Exception as e:
            print(f"Warning: Failed to read style-guide.md: {e}")
        
        return None

    @staticmethod
    def get_custom_niche_rules(base_dir: Path) -> Optional[str]:
        """Reads style-guide.md from channel base dir and extracts the top niche/objective info. (everything before first ##)"""
        guide_path = base_dir.parent.parent / "style-guide.md"
        if not guide_path.exists():
            return None
        
        try:
            content = guide_path.read_text(encoding="utf-8")
            # Usually the first few lines contain niche, objective, etc.
            # We'll take everything before the first "##"
            pattern = r"^(.*?)(?=##)"
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1).strip()
        except:
            pass
        
        return None

    @staticmethod
    def _extract_section(content: str, header: str) -> Optional[str]:
        """Helper to extract content after a header until the next same-level header or double-line break."""
        level = 0
        while level < len(header) and header[level] == '#': level += 1
        # Find exact header then everything until next header of same or higher level
        # Pattern: header ... next header with same or fewer # (higher or equal level)
        next_header_pattern = f"\\n#{{1,{level}}}\\s"
        import re
        pattern = f"{re.escape(header)}(.*?)(?={next_header_pattern}|$)"
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else None

    @staticmethod
    def get_custom_title_rules(base_dir: Path) -> Optional[str]:
        guide_path = base_dir.parent.parent / "style-guide.md"
        if not guide_path.exists(): return None
        return StyleService._extract_section(guide_path.read_text(encoding="utf-8"), "## 🎯 FÓRMULAS DE TÍTULOS PROBADAS")

    @staticmethod
    def get_custom_description_rules(base_dir: Path) -> Optional[str]:
        guide_path = base_dir.parent.parent / "style-guide.md"
        if not guide_path.exists(): return None
        return StyleService._extract_section(guide_path.read_text(encoding="utf-8"), "### CHATGPT/CLAUDE - Generación de Descripciones")

    @staticmethod
    def get_custom_tag_rules(base_dir: Path) -> Optional[str]:
        guide_path = base_dir.parent.parent / "style-guide.md"
        if not guide_path.exists(): return None
        return StyleService._extract_section(guide_path.read_text(encoding="utf-8"), "### CHATGPT/CLAUDE - Generación de Tags")

    @staticmethod
    def get_custom_language_rules(base_dir: Path) -> Optional[str]:
        guide_path = base_dir.parent.parent / "style-guide.md"
        if not guide_path.exists(): return None
        return StyleService._extract_section(guide_path.read_text(encoding="utf-8"), "## 🗣️ TERMINOLOGÍA Y LENGUAJE")
