import os
import re
from typing import List, Optional
from openai import OpenAI

class SEOEngine:
    def __init__(self, api_key: Optional[str] = None):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def generate_description(self, script_snippet: str, lang: str = "es", custom_rules: Optional[str] = None) -> str:
        """Generates a rich video description."""
        rules_text = f"\nFOLLOW THESE CHANNEL-SPECIFIC DESCRIPTION RULES AND STRUCTURE:\n{custom_rules}\n" if custom_rules else ""
        system_msg = (
            "You are a YouTube SEO expert. Generate a long, high-quality video description. "
            f"{rules_text}"
            "Include a hook, a detailed summary, and key takeaways. "
            "The total length MUST NOT exceed 5000 characters. No emojis unless rules specify them."
        )
        user_msg = f"Language: {lang}\nScript snippet:\n{script_snippet}\n\nWrite an SEO description with key points."
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.7
        )
        response_txt = response.choices[0].message.content or ""
        return response_txt.strip()[:5000]

    def generate_video_title(self, script_snippet: str, lang: str = "es", custom_rules: Optional[str] = None) -> str:
        """Generates a high-CTR video title."""
        rules_text = f"\nAPPLY THESE CHANNEL-SPECIFIC TITLE FORMULAS AND RULES:\n{custom_rules}\n" if custom_rules else ""
        system_msg = (
            "You are a YouTube SEO expert specializing in high-click-through-rate (CTR) titles. "
            f"{rules_text}"
            "Generate one single compelling video title. "
            "Use psychological triggers (curiosity, fear of missing out, direct benefit). "
            "Max 100 characters. Output ONLY the text, no quotes or emojis."
        )
        user_msg = f"Language: {lang}\nScript snippet:\n{script_snippet}\n\nWrite an optimized YouTube title."
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.8
        )
        return (response.choices[0].message.content or "").strip()[:100]

    def generate_video_questions_tags(self, script_snippet: str, count: int = 10, lang: str = "es", custom_rules: Optional[str] = None) -> str:
        """Generates question-based tags for YouTube."""
        rules_text = f"\nFOLLOW THESE CHANNEL-SPECIFIC TAG RULES:\n{custom_rules}\n" if custom_rules else ""
        system_msg = (
            "You are a YouTube SEO expert. Generate a long string of tags separated by commas. "
            f"{rules_text}"
            "The tags should be the 15 most common questions people ask that this video answers. "
            "Separate questions with commas. Total length MUST be under 500 characters. "
            "Output ONLY the comma-separated questions."
        )
        user_msg = f"Language: {lang}\nCount: {count}\nContext:\n{script_snippet}"
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.6
        )
        return (response.choices[0].message.content or "").strip()[:500]

    def generate_hashtags(self, script_snippet: str, count: int = 5, lang: str = "es", custom_rules: Optional[str] = None) -> List[str]:
        """Generates a list of hashtags."""
        rules_text = f"\nFOLLOW THESE CHANNEL-SPECIFIC HASHTAG RULES:\n{custom_rules}\n" if custom_rules else ""
        system_msg = (
            "You are a YouTube expert. Generate relevant hashtags for a YouTube video. "
            f"{rules_text}"
            "Output ONLY the hashtags separated by spaces."
        )
        user_msg = f"Language: {lang}\nCount: {count}\nContext:\n{script_snippet}"
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.5
        )
        response_txt = response.choices[0].message.content or ""
        raw = response_txt.strip()
        tags = re.split(r"[,\s]+", raw)
        clean_tags = []
        for t in tags:
            t = t.strip()
            if not t: continue
            if not t.startswith("#"): t = "#" + t
            clean_tags.append(t)
        return clean_tags[:count]

    def generate_thumbnail_hook(self, script_snippet: str, lang: str = "es", custom_rules: Optional[str] = None, channel_name: Optional[str] = None) -> str:
        """Generates a catchy short hook for a YouTube thumbnail."""
        
        # Determine niche/style based on channel name
        is_jesus = channel_name and ("jesus" in channel_name.lower() or "jesús" in channel_name.lower())
        
        if is_jesus:
            niche_desc = "Christian/Spiritual channel. The hook must be DIVINE, SOLEMN, and PROFOUND."
            format_desc = (
                "The hook MUST be in 3 parts separated by '...'. "
                "Part 1: A category or label (e.g. 'EL MISTERIO', 'LA REVELACIÓN'). "
                "Part 2: The main shocking title (e.g. 'EL APOCALIPSIS', 'JUAN VIO ESTO'). "
                "Part 3: A small curiosity or result (e.g. 'nadie te lo contó', 'mira el final'). "
                "Example: 'LA REVELACIÓN...EL APOCALIPSIS...mira el final'"
            )
        else:
            niche_desc = "Mystery and Horror channel. The hook must be SHOCKING, AGGRESSIVE, and IRRESISTIBLE."
            format_desc = (
                "The hook must be 2-5 words long, in ALL CAPS. "
                "Use '...' to separate the hook into two parts for a two-line layout. "
                "Example: 'ESTABA... ALLÍ', 'NO MIRES... ATRÁS'."
            )

        system_msg = (
            f"You are an expert YouTube CLICKBAIT strategist for a {niche_desc}. "
            "Your goal is to create an IRRESISTIBLE hook. "
            "Use psychological triggers like 'THE FORBIDDEN', 'THE UNKNOWN', 'LETHAL', 'TERRIFYING', 'SECRET' (adapted to the niche). "
            f"{format_desc} "
            f"{f'Additional brand rules: {custom_rules}' if custom_rules else ''} "
            f"The output must be in {'SPANISH' if lang == 'es' else 'the requested language'}. "
            "Output ONLY the text, no quotes or emojis."
        )
        user_msg = f"Script snippet:\n{script_snippet}\n\nWrite a short thumbnail hook."
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.8
        )
        return (response.choices[0].message.content or "").strip()[:80]

    def generate_thumbnail_visual_prompt(self, script_snippet: str, style_desc: str, thumbnail_hook: str = "", custom_rules: Optional[str] = None, include_text_in_prompt: bool = False) -> str:
        """Generates a highly descriptive visual prompt for AI image generators."""
        rules_text = f"\nFOLLOW THESE SPECIFIC STYLE RULES:\n{custom_rules}\n" if custom_rules else ""
        
        text_instruction = ""
        if include_text_in_prompt:
            text_instruction = (
                f"IMPORTANT: Explicitly describe the EXACT text to be included as 'The text \"{thumbnail_hook}\" is written in...'. "
                "Use double quotes for the text itself. Mention it should be 'large, bold, and modern font'. "
                "Describe the font color, outline, and placement based on the provided style rules if available. "
            )
        else:
            text_instruction = (
                "IMPORTANT: Do NOT describe any text or letters in the image. "
                "Instead, describe a composition that leaves a clear, empty area (on the left or center) "
                "where text will be overlayed later. Ensure the main subject is positioned to the side."
            )

        system_msg = (
            "You are a creative visual director for high-impact YouTube thumbnails. "
            "Generate a highly descriptive visual prompt in English for an AI image generator. "
            "The prompt should describe a cinematic, professional composition. "
            "Describe central characters with specific emotions, dramatic lighting, and vibrant colors. "
            f"{rules_text}"
            f"{text_instruction}"
            "CRITICAL RULES: Output ONLY the final AI visual prompt. Do NOT use any line breaks or paragraphs (single block of text). "
            "The prompt MUST BE UNDER 1000 CHARACTERS in total length."
        )
        user_msg = (
            f"Style/Niche: {style_desc}\n"
            f"Thumbnail Hook (MUST INCLUDE THIS TEXT): {thumbnail_hook}\n"
            f"Context Snippet:\n{script_snippet}\n"
            f"Generate an expert visual prompt for a professional thumbnail."
        )
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.7
        )
        return (response.choices[0].message.content or "").strip()[:2000]
