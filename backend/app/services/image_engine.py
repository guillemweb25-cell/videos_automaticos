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
        self.leonardo_v1_url = "https://cloud.leonardo.ai/api/rest/v1"
        self.leonardo_v2_url = "https://cloud.leonardo.ai/api/rest/v2"

    def generate_prompts(self, text: str, style_name: str, n: int = 1, full_context: str = "") -> List[str]:
        """Generates visual prompts from narration text using GPT, with optional full video context."""
        style = StyleService.get_style(style_name)
        style_prompt = style.get("image_style_prompt", "")
        
        system_msg = (
            "You are a creative visual director for high-end cinematic content. "
            "Generate cinematic AI image prompts that are photorealistic and elegant. "
            "STRICT RULES for anatomical correctness: "
            "- Ensure human figures have exactly two arms, two legs, and five fingers per hand. "
            "- Avoid awkward or impossible poses. Body proportions must be realistic. "
            "- Faces should be natural, expressive, and detailed. "
            "STRICT RULES for continuity: "
            "- If generating multiple prompts (n > 1), maintain absolute visual consistency. "
            "- Use the same character descriptions (age, hair color, clothing style). "
            "- Keep the same environmental setting, lighting, and color palette. "
            "PROMPT SPECIFICATIONS: "
            "- Describe the scene, lighting (e.g., volumetric, soft natural), and composition (e.g., medium shot). "
            "- No on-image text, captions, or watermarks. "
            "- ALL prompts MUST be in English. "
            "- Each prompt MUST be under 800 characters. "
            "- Output each prompt on a new line."
        )
        
        context_msg = f"\nOverall Video Context:\n{full_context}" if full_context else ""
        user_msg = f"Narration: {text}{context_msg}\n\nStyle: {style_prompt}\n\nGenerate {n} unique prompts that are relevant to the narration while respecting the overall video context."
        
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
        resp = requests.post(f"{self.leonardo_v1_url}/init-image", headers=headers, json=payload)
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

    def generate_leonardo_image(self, prompt: str, out_path: Path, size: str = "1024x1792", negative_prompt: Optional[str] = None, model_id: Optional[str] = None, init_image_id: Optional[str] = None, mode: str = "QUALITY") -> Optional[Dict[str, Any]]:
        """Generates an image using Leonardo.ai with optional model selection and image guidance. Defaults to V2."""
        # Check if we should use V2 (default) or V1
        use_v2 = os.getenv("LEONARDO_API_VERSION", "v2").lower() == "v2"
        
        if (use_v2 and not model_id) or model_id == "gpt-image-1.5": # V2 is optimized for gpt-image-1.5
            return self.generate_leonardo_v2(prompt, out_path, size=size, init_image_id=init_image_id, mode=mode)
            
        # V1 logic
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
        
        # Alchemy and Prompt Magic logic for V1
        use_alchemy = os.getenv("LEONARDO_ALCHEMY", "true").lower() == "true"
        # Newer models like Kino 2.1 (Lucid) or XL don't support Prompt Magic
        incompatible_with_prompt_magic = [
            "7b592283-e8a7-4c5a-9ba6-d18c31f258b9", 
            "b24e16ff-06e3-43eb-8d33-4416c2d75876",
            "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3"
        ]
        
        if mode == "FAST":
            use_alchemy = False
            payload["promptMagic"] = False
            cost_amount = 0.012
        else:
            # QUALITY / ULTRA
            payload["promptMagic"] = target_model not in incompatible_with_prompt_magic
            cost_amount = 0.0852
            
        payload["alchemy"] = use_alchemy
        
        resp = requests.post(f"{self.leonardo_v1_url}/generations", headers=headers, json=payload)
        if resp.status_code != 200:
            print(f"Leonardo API Error ({resp.status_code}): {resp.text}")
            resp.raise_for_status()
        
        gen_id = resp.json()["sdGenerationJob"]["generationId"]
        
        # 2. Poll for completion
        img_url = self._poll_leonardo(gen_id, headers)
        
        # 3. Download
        self._download_image(img_url, out_path)
        
        return {"amount": cost_amount}

    def generate_leonardo_v2(self, prompt: str, out_path: Path, size: str = "1024x1792", init_image_id: Optional[str] = None, mode: str = "QUALITY") -> Optional[Dict[str, Any]]:
        """Generates an image using Leonardo.ai V2 API with GPT Image-1.5 model."""
        if not self.leonardo_api_key:
            raise RuntimeError("LEONARDO_API_KEY not configured")

        width, height = self._normalize_size(size)
        
        headers = {
            "Authorization": f"Bearer {self.leonardo_api_key}",
            "Content-Type": "application/json",
            "accept": "application/json"
        }
        
        payload = {
            "model": "gpt-image-1.5",
            "parameters": {
                "prompt": prompt,
                "width": width,
                "height": height,
                "quantity": 1,
                "mode": mode if mode in ["FAST", "QUALITY", "ULTRA"] else "QUALITY",
                "prompt_enhance": "OFF"
            },
            "public": False
        }

        if init_image_id:
            payload["parameters"]["guidances"] = {
                "image_reference": [
                    {
                        "image": {
                            "id": init_image_id,
                            "type": "UPLOADED"
                        },
                        "strength": "MID"
                    }
                ]
            }
        
        resp = requests.post(f"{self.leonardo_v2_url}/generations", headers=headers, json=payload)
        if resp.status_code != 200:
            print(f"Leonardo V2 API Error ({resp.status_code}): {resp.text}")
            resp.raise_for_status()
        
        resp_data = resp.json()
        # V2 can return structure: {"generate": {"generationId": "..."}}
        # or {"generations": {"id": "..."}} depending on specific endpoint/version variations
        gen_id = None
        if "generate" in resp_data:
            gen_id = resp_data["generate"].get("generationId")
        elif "generations" in resp_data:
            gen_id = resp_data["generations"].get("id")
            
        if not gen_id:
            raise RuntimeError(f"Leonardo V2 failed to return a generation ID: {resp.text}")
        
        cost_info = resp_data.get("generate", {}).get("cost") or resp_data.get("generations", {}).get("cost")
        
        # 2. Poll for completion (V2 polling might be slightly different but usually same endpoint structure)
        img_url = self._poll_leonardo_v2(gen_id, headers)
        
        # 3. Download
        self._download_image(img_url, out_path)
        
        # Define costs for V2 based on mode
        v2_costs = {
            "FAST": 0.012,
            "QUALITY": 0.0852,
            "ULTRA": 0.0852 # Or whatever the user provided
        }
        
        return {"amount": v2_costs.get(mode, 0.0852)}

    def _normalize_size(self, size: str):
        if size == "1792x1024": return 1536, 1024
        if size == "1024x1792": return 1024, 1536
        return 1024, 1024

    def _poll_leonardo(self, gen_id: str, headers: dict, timeout=300) -> str:
        t0 = time.time()
        while time.time() - t0 < timeout:
            resp = requests.get(f"{self.leonardo_v1_url}/generations/{gen_id}", headers=headers)
            resp.raise_for_status()
            data = resp.json()["generations_by_pk"]
            if data["status"] == "COMPLETE":
                return data["generated_images"][0]["url"]
            if data["status"] in ["FAILED", "ERROR"]:
                raise RuntimeError(f"Leonardo generation failed: {data}")
            time.sleep(3)
        raise TimeoutError("Leonardo timeout")

    def _poll_leonardo_v2(self, gen_id: str, headers: dict, timeout=300) -> str:
        """Polls for completion using V2 style response."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            # Note: V2 might still use the same polling endpoint, checking status
            resp = requests.get(f"{self.leonardo_v1_url}/generations/{gen_id}", headers=headers)
            resp.raise_for_status()
            data = resp.json().get("generations_by_pk")
            if not data:
                # If v1 poll doesn't work for v2 job, we might need to adjust
                # But typically they share the same backend for results
                print(f"DEBUG: Poll V2 response: {resp.text}")
                data = resp.json().get("generations")
            
            if data and data.get("status") == "COMPLETE":
                images = data.get("generated_images", [])
                if images:
                    return images[0]["url"]
            
            if data and data.get("status") in ["FAILED", "ERROR"]:
                raise RuntimeError(f"Leonardo V2 generation failed: {data}")
            
            time.sleep(3)
        raise TimeoutError("Leonardo V2 timeout")

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
