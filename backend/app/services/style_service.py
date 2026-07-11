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
    "deformed body, anatomical nonsense, "
    # Weighted anti-nudity (SDXL Juggernaut tends to ignore unweighted tokens):
    "(nudity:2.0), (naked:2.0), (nude:2.0), (nsfw:2.0), (topless:2.0), "
    "(bare chest:1.9), (bare breasts:1.9), (exposed breasts:1.9), (nipples:1.9), "
    "(visible nipples:1.9), (uncovered torso:1.8), (bare torso:1.8), "
    "(cleavage:1.6), (low cut top:1.6), (revealing clothing:1.6), (lingerie:1.7), "
    "(see-through clothing:1.7), (sheer fabric:1.6), (transparent fabric:1.6), "
    "(buttocks:1.8), (erotic:1.9), (sexual:1.9), (explicit:1.9), (genitals:2.0)"
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
            "Epic mystical wealth-and-abundance imagery in golden tones; "
            "dramatic explosions of golden light, cascading gold coins, glowing sacred geometry "
            "(metatron's cube, flower of life, hexagrams, vesica piscis), divine light beams piercing dark cosmic backgrounds; "
            "high-saturation gold and amber palette with deep navy or black backgrounds for contrast; "
            "volumetric god-rays, sparkling particles, energy vortices, prosperity and breakthrough mood; "
            "photorealistic with magical fantasy elements, cinematic, 8k, HDR; "
            "prefer SYMBOLIC OBJECTS (coins, contracts, keys, sacred geometry, crystals, scrolls, gold bars, "
            "modern luxury items like cars and houses, businessmen) over abstract scenery; "
            "if humans appear they MUST be confident adults (30s–60s) only, never children, never youth; "
            "no on-image text or digits."
        ),
        "negative_prompt": (
            NEGATIVE_BASE
            + ", literal numbers in image, garbled digits, illegible text, dark depressing mood, horror, dull flat lighting, "
            "(naked:2.0), (nude:2.0), (topless:2.0), (nudity:2.0), (bare chest:1.9), (bare breasts:1.9), "
            "(nipples:1.9), (exposed breasts:1.9), (cleavage:1.7), (low cut top:1.7), (revealing clothing:1.7), "
            "(lingerie:1.8), (underwear visible:1.8), (sheer fabric:1.6), (transparent fabric:1.6), "
            "(bikini:1.7), (sexy outfit:1.7), (seductive pose:1.6), (sensual:1.6), (erotic:2.0), (sexual:2.0), (nsfw:2.0), "
            "(child:1.7), (children:1.7), (kid:1.7), (kids:1.7), (minor:1.7), (baby:1.7), "
            "(toddler:1.7), (infant:1.7), (teen:1.6), (teenager:1.6), (young face:1.5), (youthful features:1.5), "
            "(juvenile:1.5), (small child:1.6), (boy:1.4), (girl:1.4), "
            "crystal ball, tarot cards, witch hat, comic style, illustration, drawing, anime, "
            "soft pastel mystical, dreamy, watercolor, low contrast, washed out"
        ),
        "post_note": (
            "Visualize the FEELING / OUTCOME of the Grabovoi sequence (wealth, abundance, breakthrough, "
            "luxury, prosperity, healing) using EPIC GOLDEN visuals: cascading gold coins, sacred geometry, "
            "luxury cars, modern office contracts, businessmen handshakes, golden light explosions. "
            "Numerical sequence goes ONLY as text overlay on thumbnail (never inside the image). "
            "STRICT NO-CHILDREN RULE: never show children, teenagers, young faces or youthful features. "
            "If a person is needed, default to a confident adult professional (40s–60s). "
            "STRICT CLOTHING RULE (mandatory): all human characters MUST be fully clothed in modest "
            "professional or business attire (blazers, suits, blouses, dresses with high necklines, "
            "elegant smart-casual outfits). NEVER show nudity, partial nudity, exposed torso, bare "
            "chest, cleavage, low-cut tops, lingerie, swimwear, sheer fabrics or any sexually "
            "suggestive imagery. When describing a woman, ALWAYS explicitly mention her outfit "
            "(e.g. 'wearing a navy blazer over a high-neck blouse', 'in an elegant business dress')."
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
        "image_style_prompt": (
            "Epic cinematic religious photography, soft natural lighting, golden-hour or "
            "candlelit atmosphere, period-accurate textures, majestic reverent mood, high "
            "contrast, photorealistic, 8k, sharp focus on faces and respectful expressions."
        ),
        "negative_prompt": (
            NEGATIVE_BASE
            + ", text, watermarks, frames, borders, cartoon, anime, plastic CGI, "
            "stained glass, kitsch glow, church murals, framed paintings, lens flare, "
            "bright starburst sun, "
            # Weighted tokens against wet-clothing nudity (the failure mode that
            # triggered SDXL when the LLM wrote 'clothing soaked and clinging'):
            "(wet clothes clinging:1.8), (clinging wet fabric:1.8), "
            "(transparent wet shirt:1.8), (wet see-through tunic:1.8), "
            "(soaked revealing fabric:1.7), "
            "(loincloth:1.7), (shirtless:1.7), (bare chested men:1.7), "
            "(bare chested women:2.0), (topless men:1.8), (semi-nude:1.8), "
            "(open robe revealing skin:1.7), (low neckline tunic:1.6)"
        ),
        "post_note": (
            "Respectful, reverent tone. "
            "\n\nUNIVERSAL TECHNICAL PROHIBITIONS (these are not content, they are pure "
            "engineering rules to prevent SDXL failure modes): "
            "1) NEVER write 'soaked clothing', 'wet clothing clinging', 'clinging fabric', "
            "'wet tunic', 'soaked and clinging', 'fabric clinging to body'. If the narration "
            "mentions rain, water or wet conditions, write instead 'wearing heavy "
            "water-darkened opaque garments, layered, completely covered, with rain dripping "
            "off thick outerwear'. "
            "2) NEVER bare chests, NEVER loincloths, NEVER topless figures of any gender, "
            "NEVER exposed torsos, NEVER cleavage. Hands and face are the only exposed skin. "
            "\n\nERA AND WARDROBE COME EXCLUSIVELY FROM THE NARRATION. Read the phrase, "
            "identify the year, place and culture mentioned, and depict period-accurate, "
            "culture-accurate, fully-covered clothing for THAT specific context. Do NOT "
            "default to any biblical/ancient/Levantine aesthetic just because the channel or "
            "style sounds religious. The style only dictates lighting, colour and mood — "
            "never wardrobe, architecture or epoch."
        ),
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
        "post_note": (
            "DREAM INTERPRETATION — strict anti-literal rule: when the narration mentions a "
            "dream action or symbol, do NOT depict that action literally. The image must show "
            "the SYMBOLIC / PSYCHOLOGICAL meaning, not the dream content. If the narration says "
            "'kiss', do not draw people kissing; if it says 'fall', do not draw a person "
            "falling; same for chase, drowning, teeth, snake, etc. "
            "Translate the symbol into an abstract visual metaphor — pick one of these "
            "metaphor families and stick to ONE per image: natural element (trees, water, sky, "
            "rivers, mountains, fog), architectural element (doors, mirrors, staircases, "
            "corridors, windows, archways), pure light/abstract (flames, particles, geometric "
            "shapes, glowing orbs, sacred geometry, threads of light). "
            "Variety: for the same paragraph, each image must use a DIFFERENT metaphor family. "
            "Never repeat the same composition or focal element across images of one paragraph. "
            "STRICT NO-PEOPLE PREFERENCE: avoid human figures as the focal subject. Do NOT "
            "depict couples, faces, kisses, hugs, or anyone performing the dream action. "
            "If a human element is unavoidable, only a small distant fully-clothed silhouette "
            "from behind, fully covered head to toe in robes or dark clothing, never close-up, "
            "never a face, never any visible skin beyond hands. "
            "STRICT CLOTHING / NO-NUDITY: every figure (human or symbolic) is FULLY CLOTHED. "
            "No bare skin on torso, chest, arms, legs. No transparent or sheer fabrics. No "
            "lingerie, swimwear, low-cut, or revealing clothing. Default to flowing dark robes "
            "or full-length silhouettes."
        ),
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
    },
    "koreano_minhwa": {
        "display_name": "Korean Historical Illustration",
        "image_style_prompt": (
            "Korean historical illustration painting style, traditional ink and wash with "
            "rich earth tones, painterly brushwork visible, hand-painted aesthetic, "
            "warm earthen palette of deep browns, ochre, terracotta, muted reds and beige, "
            "soft golden backlight with subtle godrays, atmospheric depth with warm golden haze, "
            "narrative dramatic composition, expressive faces with clear emotions, "
            "illustration book aesthetic for adult historical narratives; no on-image text"
        ),
        "negative_prompt": (
            NEGATIVE_BASE
            + ", photorealistic, photography, 3d render, computer game art, "
            "western cartoon, anime style, manga, manhwa, webtoon, cel shading, screentone, "
            "neon colors, oversaturated, blue cosmic background, sacred geometry, "
            "modern clothing, electronic devices, cars, contemporary architecture, "
            "low quality, blurry, deformed, cluttered composition"
        ),
        "post_note": "Painterly ink-wash brushwork visible; warm earthen palette; soft golden backlight.",
    },
    "lallamavioleta": {
        "display_name": "La Llama Violeta (Saint Germain)",
        "image_style_prompt": (
            "Cinematic mystical photorealistic 3D render, dramatic spiritual atmosphere, "
            "deep violet and gold colour palette (#7B2CBF, #9D4EDD, #C77DFF, #FFD700), "
            "dramatic divine light beams from above, a transmuting VIOLET FLAME OF FIRE "
            "(burning spiritual fire, plasma, glowing embers — NOT an animal) surrounding "
            "or emanating from the focal subject, dark cosmic background with subtle "
            "violet sacred geometry, bokeh effect with violet-gold particles, "
            "high contrast violet-gold-dark, ascension energy, professional composition, "
            "8k resolution, hyper-detailed textures; no on-image text"
        ),
        "negative_prompt": (
            "(llama animal:1.6), (alpaca:1.5), (vicuna:1.5), (guanaco:1.4), (camelid:1.5), "
            "lama glama, andean animal, camel, fur animal, wool animal, livestock, "
            "farm animal, zoo animal, quadruped, hooves, animal snout, four-legged creature, "
            + NEGATIVE_BASE
            + ", cartoon, anime, manga, cel shading, flat colors, "
            "western cartoon, disney style, pixar style, comic book, "
            "bright backgrounds, pastel colors, washed-out, desaturated, "
            "modern clothing, electronic devices, cars, contemporary architecture, "
            "neon green, hot pink, lime yellow, "
            "low quality, blurry, deformed, cluttered composition, "
            "ugly, plastic CGI, cheap rendering"
        ),
        "post_note": (
            "Photorealistic mystical 3D render; deep violet + gold palette; dramatic divine "
            "lighting; transmuting violet flame as recurring visual motif; dark cosmic backgrounds. "
            "CRITICAL DISAMBIGUATION: in this channel the Spanish word 'llama' and the term "
            "'Llama Violeta' ALWAYS mean a VIOLET FLAME OF FIRE (spiritual fire, plasma, burning "
            "violet energy) — they NEVER mean the Andean llama animal (lama glama, alpaca, "
            "camelid). NEVER depict any animal. Whenever the narration says 'llama', render "
            "burning violet fire/flame, never a creature."
        ),
    },
    "zencrayon": {
        "display_name": "Zen Crayon 3D (kids drawing)",
        "image_style_prompt": (
            "ais-crayz, whimsical child's drawing turned into a soft 3D render, playful "
            "claymation style, chunky rounded shapes, soft matte plasticine clay texture, harmonious muted "
            "natural color palette, soft storybook lighting, cute and friendly, clear simple composition"
        ),
        "negative_prompt": (
            "(from behind:1.3), (back turned:1.3), (rear view:1.3), (facing away:1.2), back of head, "
            "(oversaturated:1.3), (rainbow colors:1.3), (neon colors:1.3), garish, "
            "(crayons:1.7), (crayon sticks:1.7), (colored pencils:1.6), (pencils:1.5), "
            "(box of crayons:1.5), drawing crayons, wax crayon objects, scattered crayons, "
            "(photorealistic:1.3), realistic photograph, gritty, horror, scary, creepy, "
            "dark gloomy, text, watermark, signature, logo, blurry, low quality, jpeg artifacts, "
            "extra fingers, deformed hands, bad anatomy, "
            "(nudity:2.0), (nsfw:2.0), (nude:2.0), (bare breasts:1.9)"
        ),
        "post_note": (
            "Whimsical 'kids crayon drawing turned 3D' channel. Depict each concept as a cute, "
            "friendly 3D-rendered scene that looks like a child's crayon drawing brought to life: "
            "chunky rounded characters and objects, waxy crayon textures, bright saturated colors, "
            "soft lighting, storybook charm. Keep it warm, playful, clear and family-friendly. "
            "ALWAYS start the prompt with the trigger word 'ais-crayz'. 1-2 characters, fully "
            "clothed, no nudity, nothing scary or gory."
        ),
    },
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
    "koreano": "koreano_minhwa",
    "korean": "koreano_minhwa",
    "minhwa": "koreano_minhwa",
    "llamavioleta": "lallamavioleta",
    "violeta": "lallamavioleta",
    "saintgermain": "lallamavioleta",
    "saint_germain": "lallamavioleta",
    "zenesp": "zencrayon",
    "zennesp": "zencrayon",
    "zen": "zencrayon",
    "zendoodle": "zencrayon",
    "crayon": "zencrayon",
    "zen_crayon": "zencrayon",
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
    def _resolve_style_guide_path(base_dir: Path) -> Optional[Path]:
        """Walks up from base_dir looking for style-guide.md.

        Layouts seen in the wild:
            cache/<channel>/<video>/                       → guide at parent
            cache/<user>/<channel>/<video>/                → guide at parent
        Older comments referenced parent.parent, but in practice the guide always
        lives one level up from the video dir (in the channel directory).
        """
        for candidate in (base_dir.parent, base_dir.parent.parent):
            p = candidate / "style-guide.md"
            if p.exists():
                return p
        return None

    @staticmethod
    def get_custom_thumbnail_rules(base_dir: Path) -> Optional[str]:
        """Reads style-guide.md from channel base dir and extracts the thumbnail section."""
        guide_path = StyleService._resolve_style_guide_path(base_dir)
        if not guide_path:
            return None

        try:
            content = guide_path.read_text(encoding="utf-8")
            # Match the actual section heading (## ... SISTEMA DE THUMBNAILS at start of
            # its own line), not occurrences of the phrase inside other sections such as
            # the table of contents.
            pattern = r"^##[^\n]*SISTEMA DE THUMBNAILS[^\n]*$(.*?)(?=^## |\Z)"
            match = re.search(pattern, content, re.DOTALL | re.MULTILINE | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        except Exception as e:
            print(f"Warning: Failed to read style-guide.md: {e}")

        return None

    @staticmethod
    def get_custom_niche_rules(base_dir: Path) -> Optional[str]:
        """Reads style-guide.md from channel base dir and extracts the top niche/objective info.
        Returns everything before the first level-2 header (`## ` at start of line),
        so level-3 subsections (`### ...`) inside the niche block are preserved."""
        guide_path = StyleService._resolve_style_guide_path(base_dir)
        if not guide_path:
            return None

        try:
            content = guide_path.read_text(encoding="utf-8")
            # Stop at the first level-2 header, anchored at start of line (MULTILINE).
            # Earlier this used (?=##) which incorrectly matched `###` substrings inside
            # the niche block and truncated content.
            pattern = r"\A(.*?)(?=^## )"
            match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
            if match:
                return match.group(1).strip()
            # No level-2 header at all → return whole file
            return content.strip()
        except Exception:
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
        guide_path = StyleService._resolve_style_guide_path(base_dir)
        if not guide_path: return None
        return StyleService._extract_section(guide_path.read_text(encoding="utf-8"), "## 🎯 FÓRMULAS DE TÍTULOS PROBADAS")

    @staticmethod
    def get_custom_description_rules(base_dir: Path) -> Optional[str]:
        guide_path = StyleService._resolve_style_guide_path(base_dir)
        if not guide_path: return None
        return StyleService._extract_section(guide_path.read_text(encoding="utf-8"), "### CHATGPT/CLAUDE - Generación de Descripciones")

    @staticmethod
    def get_custom_tag_rules(base_dir: Path) -> Optional[str]:
        guide_path = StyleService._resolve_style_guide_path(base_dir)
        if not guide_path: return None
        return StyleService._extract_section(guide_path.read_text(encoding="utf-8"), "### CHATGPT/CLAUDE - Generación de Tags")

    @staticmethod
    def get_custom_language_rules(base_dir: Path) -> Optional[str]:
        guide_path = StyleService._resolve_style_guide_path(base_dir)
        if not guide_path: return None
        return StyleService._extract_section(guide_path.read_text(encoding="utf-8"), "## 🗣️ TERMINOLOGÍA Y LENGUAJE")
