import os
import json
import time
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from openai import OpenAI
from app.services.style_service import StyleService

class ImageEngine:
    def __init__(self, openai_api_key: Optional[str] = None, leonardo_api_key: Optional[str] = None):
        self.openai_client = OpenAI(api_key=openai_api_key or os.getenv("OPENAI_API_KEY"))
        self.leonardo_api_key = leonardo_api_key or os.getenv("LEONARDO_API_KEY")
        self.leonardo_url = "https://cloud.leonardo.ai/api/rest/v1"

    def generate_prompts(self, text: str, style_name: str, n: int = 1) -> List[str]:
        """Generates visual prompts from narration text using GPT."""
        style = StyleService.get_style(style_name)
        style_prompt = style.get("image_style_prompt", "")
        
        system_msg = (
            "You are a creative visual director. Generate cinematic AI image prompts. "
            "Describe the scene, lighting, and composition. No text or camera jargon. "
            "IMPORTANT: ALL prompts MUST be in English, regardless of the input language. "
            "Each prompt MUST be under 800 characters. "
            "STRICTLY follow the age and demographic described in the Style. "
            "Ensure the visual content is 100% directly relevant to the Narration text, "
            "focusing on the actions or concepts mentioned. "
            "IMPORTANT: Be very precise about the number of people and their actions. "
            "If generating multiple prompts (n > 1), ensure visual continuity (same characters, same environmental settings) "
            "across the sequence to tell a coherent story. "
            "Output each prompt on a new line."
        )
        
        user_msg = f"Narration: {text}\n\nStyle: {style_prompt}\n\nGenerate {n} unique prompts."
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.7
        )
        
        content = response.choices[0].message.content.strip()
        # Filter and truncate prompts to 800 chars
        prompts = []
        for p in content.split("\n"):
            p = p.strip("-• ").strip()
            if len(p.split()) > 3:
                prompts.append(p[:800])
        return prompts[:n]

    def generate_continuation_prompt(self, text: str, previous_prompt: str, style_name: str) -> str:
        """Generates a visual continuation prompt based on the previous scene."""
        style = StyleService.get_style(style_name)
        style_prompt = style.get("image_style_prompt", "")
        
        system_msg = (
            "You are a creative visual director. Generate a cinematic AI image prompt that continues a sequence. "
            "IMPORTANT: Maintain absolute visual continuity with the previous scene. "
            "Keep the same characters, same clothing, and same environmental settings. "
            "STRICTLY follow the age and demographic described in the Style. "
            "Output ONLY the prompt text in English."
        )
        
        user_msg = (
            f"Previous Scene Prompt: {previous_prompt}\n\n"
            f"New Narration: {text}\n\n"
            f"Style: {style_prompt}\n\n"
            "Generate a prompt for the next shot that logically follows the previous one while being relevant to the new narration."
        )
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()[:800]

    def upload_init_image(self, image_path: Path) -> str:
        """Uploads an image to Leonardo.ai and returns the initImageId."""
        if not self.leonardo_api_key:
            raise RuntimeError("LEONARDO_API_KEY not configured")

        headers = {
            "Authorization": f"Bearer {self.leonardo_api_key}",
            "Content-Type": "application/json"
        }

        # 1. Get presigned URL
        ext = image_path.suffix.lower().replace(".", "")
        if ext == "jpg": ext = "jpeg"
        
        payload = {"extension": ext}
        resp = requests.post(f"{self.leonardo_url}/init-image", headers=headers, json=payload)
        resp.raise_for_status()
        
        data = resp.json()["uploadInitImage"]
        fields = json.loads(data["fields"])
        url = data["url"]
        image_id = data["id"]

        # 2. Upload to S3
        with open(image_path, "rb") as f:
            files = {"file": f}
            s3_resp = requests.post(url, data=fields, files=files)
            s3_resp.raise_for_status()
        
        return image_id

    def generate_leonardo_image(self, prompt: str, out_path: Path, size: str = "1024x1792", negative_prompt: Optional[str] = None, model_id: Optional[str] = None, init_image_id: Optional[str] = None) -> None:
        """Generates an image using Leonardo.ai with optional model selection and image guidance."""
        if not self.leonardo_api_key:
            raise RuntimeError("LEONARDO_API_KEY not configured")

        width, height = self._normalize_size(size)
        
        headers = {
            "Authorization": f"Bearer {self.leonardo_api_key}",
            "Content-Type": "application/json"
        }
        
        target_model = model_id or "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3"
        
        payload = {
            "prompt": prompt,
            "modelId": target_model, 
            "width": width,
            "height": height,
            "num_images": 1,
            "public": False,
            "alchemy": True,
            "contrast": 3.5
        }
        
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        if init_image_id:
            payload["init_image_id"] = init_image_id
            payload["imagePrompts"] = [init_image_id]
        
        # Alchemy is a paid feature. Allow disabling it via env var if needed.
        use_alchemy = os.getenv("LEONARDO_ALCHEMY", "true").lower() == "true"
        payload["alchemy"] = use_alchemy
        
        resp = requests.post(f"{self.leonardo_url}/generations", headers=headers, json=payload)
        if resp.status_code != 200:
            print(f"Leonardo API Error ({resp.status_code}): {resp.text}")
            resp.raise_for_status()
        
        gen_id = resp.json()["sdGenerationJob"]["generationId"]
        
        # 2. Poll for completion
        img_url = self._poll_leonardo(gen_id, headers)
        
        # 3. Download
        self._download_image(img_url, out_path)

    def _normalize_size(self, size: str):
        if size == "1792x1024": return 1536, 1024
        if size == "1024x1792": return 1024, 1536
        return 1024, 1024

    def _poll_leonardo(self, gen_id: str, headers: dict, timeout=300) -> str:
        t0 = time.time()
        while time.time() - t0 < timeout:
            resp = requests.get(f"{self.leonardo_url}/generations/{gen_id}", headers=headers)
            resp.raise_for_status()
            data = resp.json()["generations_by_pk"]
            if data["status"] == "COMPLETE":
                return data["generated_images"][0]["url"]
            if data["status"] in ["FAILED", "ERROR"]:
                raise RuntimeError(f"Leonardo generation failed: {data}")
            time.sleep(3)
        raise TimeoutError("Leonardo timeout")

    def generate_thumbnail(self, hook: str, visual_prompt: str, out_path: Path, size: str = "1024x1792", model_id: Optional[str] = None) -> None:
        """Generates a professional thumbnail. Blends visual prompt with text instructions."""
        # If the visual prompt already mentions 'text', 'font', or 'hook', we use it as the base.
        # Otherwise, we append a standard text placement instruction.
        base_prompt = visual_prompt
        has_text_instruction = any(word in visual_prompt.lower() for word in ["text", "font", "reads", " hook", "written"])
        
        if not has_text_instruction and hook:
            base_prompt += (
                f". The text '{hook}' is written in a big, modern, bold, cinematic font, "
                "centered and highly legible. High contrast, vibrant colors, eye-catching composition."
            )
        
        # Ensure it mentions cinematic/8k for quality even if not in visual_prompt
        if "8k" not in base_prompt.lower():
            base_prompt += " Extreme detail, 8k resolution, cinematic lighting."

        self.generate_leonardo_image(base_prompt, out_path, size=size, model_id=model_id)

    def _download_image(self, url: str, out_path: Path):
        resp = requests.get(url, stream=True)
        resp.raise_for_status()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
