import os
import re
from typing import List, Optional
from openai import OpenAI

class SEOEngine:
    def __init__(self, api_key: Optional[str] = None):
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

    def generate_description(self, script_snippet: str, lang: str = "es") -> str:
        """Generates SEO description with key points from the script."""
        system_msg = (
            "You are an expert in SEO and YouTube copywriting. Write a persuasive video description. "
            "IMPORTANT: Start with a powerful hook. Then, include a section 'Puntos clave tratados:' "
            "with 3-5 bullet points summarizing the most important advice or facts from the script. "
            "Finally, add a call to action. No emojis. Output only the text. "
            "The total length MUST NOT exceed 5000 characters."
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

    def generate_video_title(self, script_snippet: str, lang: str = "es") -> str:
        """Generates a high-CTR SEO title."""
        system_msg = (
            "You are a YouTube SEO expert. Generate a single, high-CTR, and impactful video title. "
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

    def generate_video_questions_tags(self, script_snippet: str, count: int = 10, lang: str = "es") -> str:
        """Generates tags as common questions (max 500 chars total)."""
        system_msg = (
            "You are a YouTube SEO expert. Generate a list of search-optimized tags "
            "formatted as common questions people ask about this topic. "
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

    def generate_hashtags(self, text: str, count: int = 5, lang: str = "es") -> List[str]:
        """Generates a list of hashtags."""
        system_msg = "Generate relevant hashtags for a YouTube video. Output only the hashtags separated by spaces."
        user_msg = f"Language: {lang}\nCount: {count}\nContext:\n{text}"
        
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

    def generate_thumbnail_visual_prompt(self, script_snippet: str, style_desc: str, thumbnail_hook: str = "") -> str:
        """Generates a highly descriptive visual prompt for Leonardo.ai (Phoenix 1.0)."""
        system_msg = (
            "You are a creative visual director for high-impact YouTube thumbnails. "
            "Generate a highly descriptive visual prompt in English. "
            "The prompt should describe a cinematic, professional composition. "
            "Use techniques like 'Split composition' (comparing before/after or problem/solution) "
            "or 'Extreme close-up' if appropriate. "
            "Describe central characters with specific emotions, dramatic lighting, and vibrant colors. "
            "IMPORTANT: Describe the EXACT text to be included as 'The text \"HOOK_HERE\" is written in...'. "
            "Use double quotes for the text itself. Mention it should be 'large, bold, and modern font'. "
            "Output ONLY the visual prompt in English."
        )
        user_msg = (
            f"Style: {style_desc}\n"
            f"Thumbnail Hook (MUST INCLUDE THIS TEXT): {thumbnail_hook}\n"
            f"Script context:\n{script_snippet}\n\n"
            f"Generate a visual prompt for a professional thumbnail with large text."
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
