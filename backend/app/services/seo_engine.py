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
    def generate_thumbnail_hook(self, script_snippet: str, lang: str = "es") -> str:
        """Generates a short, catchy thumbnail hook from the script."""
        system_msg = (
            "You are a YouTube thumbnail expert. Generate a single, very short, "
            "and impactful hook or title for a thumbnail (max 30 characters). "
            "Output ONLY the text, no quotes or emojis."
        )
        user_msg = f"Language: {lang}\nScript snippet:\n{script_snippet}\n\nWrite a short thumbnail hook."
        
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.8
        )
        return (response.choices[0].message.content or "").strip()[:50]

    def generate_thumbnail_visual_prompt(self, script_snippet: str, style_desc: str, thumbnail_hook: str = "", custom_rules: Optional[str] = None) -> str:
        """Generates a highly descriptive visual prompt for Leonardo.ai (Phoenix 1.0 or GPT-1.5)."""
        rules_text = f"\nFOLLOW THESE SPECIFIC STYLE RULES:\n{custom_rules}\n" if custom_rules else ""
        
        system_msg = (
            "You are a creative visual director for high-impact YouTube thumbnails. "
            "Generate a highly descriptive visual prompt in English for an AI image generator. "
            "The prompt should describe a cinematic, professional composition. "
            "Describe central characters with specific emotions, dramatic lighting, and vibrant colors. "
            f"{rules_text}"
            "IMPORTANT: Explicitly describe the EXACT text to be included as 'The text \"HOOK_HERE\" is written in...'. "
            "Use double quotes for the text itself. Mention it should be 'large, bold, and modern font'. "
            "Describe the font color, outline, and placement based on the provided style rules if available. "
            "Output ONLY the final AI visual prompt in English."
        )
        user_msg = (
            f"Style/Niche: {style_desc}\n"
            f"Thumbnail Hook (MUST INCLUDE THIS TEXT): {thumbnail_hook}\n"
            f"Video Script context:\n{script_snippet}\n\n"
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
