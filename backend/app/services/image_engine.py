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

    def generate_prompts(self, text: str, style_name: str, n: int = 1, full_context: str = "", style_override: dict = None, recent_history: List[str] = [], custom_rules: Optional[str] = None) -> List[str]:
        """Generates visual prompts from narration text using GPT, with optional full video context and recent prompt history."""
        style = style_override or StyleService.get_style(style_name)
        style_prompt = style.get("image_style_prompt", "")
        rules_text = f"\nFOLLOW THESE SPECIFIC CHANNEL STYLE RULES:\n{custom_rules}\n" if custom_rules else ""
        
        system_msg = (
            "You are a creative visual director for high-end cinematic content. "
            "Generate cinematic AI image prompts that are photorealistic and elegant. "
            f"{rules_text}"
            "STRICT RULES for chronological progression: "
            "- DISCARD generic scenes. Focus ONLY on the specific action and moment described in the Narration. "
            "- If the narration describes a specific event (e.g., 'fleeing to Egypt', 'working wood'), DO NOT show a generic summary scene. "
            "- Maintain character consistency (age, face, clothes) but CHANGE the composition, angle, and specific interaction for every prompt. "
            "- VARIETY is mandatory. If you see in the 'Recent History' that a setting has been used, MOVE the camera or CHANGE the scene elements. "
            
            "STRICT RULES for anatomical correctness: "
            "- Ensure human figures have exactly two arms, two legs, and five fingers per hand. "
            "- ORIENTATION: Pay extreme attention to feet and hands. Feet must point in a natural direction. ABSOLUTELY NO inverted or backwards feet. "
            "- JOINTS: Limbs must connect naturally to the torso. Body proportions must be photorealistic. "
            "- For elderly characters, PRIORITIZE slow, gentle, and stable movements. "
            "- ABSOLUTELY AVOID: jumping, running, high-impact movements, acrobatics for seniors. "


            "PROMPT SPECIFICATIONS: "
            "- Describe the scene, lighting, and composition (e.g., close-up, wide shot, bird's eye view). "
            "- ALL prompts MUST be in English. "
            "- Each prompt MUST be under 800 characters. "
            "- Output each prompt on a new line."
        )
        
        history_msg = f"\nRecent History (Avoid repeating these scenes):\n" + "\n".join(recent_history[:5]) if recent_history else ""
        context_msg = f"\nOverall Video Concept (For mood/style only):\n{full_context[:1000]}..." if full_context else ""
        user_msg = f"Narration to visualize: {text}\n{history_msg}{context_msg}\n\nStyle: {style_prompt}\n\nGenerate {n} unique and specific prompts for this EXACT narration."

        
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

    def generate_continuation_prompt(self, text: str, previous_prompt: str, style_name: str, style_override: dict = None, custom_rules: Optional[str] = None) -> str:
        """Generates a visual continuation prompt based on the previous scene."""
        style = style_override or StyleService.get_style(style_name)
        style_prompt = style.get("image_style_prompt", "")
        rules_text = f"\nFOLLOW THESE SPECIFIC CHANNEL STYLE RULES:\n{custom_rules}\n" if custom_rules else ""
        
        system_msg = (
            "You are a creative visual director. Generate a cinematic AI image prompt that continues a sequence. "
            f"{rules_text}"
            "IMPORTANT: Maintain absolute visual continuity with the previous scene. "
            "Keep the same characters, same clothing, and same environmental settings. "
            "STRICTLY follow the age and demographic described in the Style. "
            "- For elderly characters, ensure movements are calm, slow, and realistic. No jumping or acrobatic poses. "
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
        use_v2 = os.getenv("LEONARDO_API_VERSION", "v2").lower() == "v2"
        
        # Determine if we should use V2
        # Clean model_id in case it has trailing spaces
        mid = (model_id or "").strip()
        v2_model_names = ["gpt-image-1.5", "phoenix", "phoenix-v2"]
        # Phoenix UUID de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3 can be used in V1 sometimes,
        # but Leonardo is pushing for V2 on newer models.
        
        is_explicit_v2 = mid in v2_model_names
        
        if (use_v2 and not mid) or is_explicit_v2:
            print(f"Routing to Leonardo V2: model={mid or 'default'}")
            return self.generate_leonardo_v2(prompt, out_path, size=size, negative_prompt=negative_prompt, init_image_id=init_image_id, mode=mode, model_id=mid)

            
        # V1 logic
        if not self.leonardo_api_key:
            raise RuntimeError("LEONARDO_API_KEY not configured")

        width, height = self._normalize_size(size)
        
        headers = {
            "Authorization": f"Bearer {self.leonardo_api_key}",
            "Content-Type": "application/json"
        }
        
        target_model = model_id or "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3"
        
        # Lucid Origin has a special payload format per Leonardo docs:
        # alchemy=false, ultra=false, contrast=3.5, styleUUID required, no promptMagic
        LUCID_ORIGIN_ID = "7b592283-e8a7-4c5a-9ba6-d18c31f258b9"
        is_lucid = target_model == LUCID_ORIGIN_ID
        
        if is_lucid:
            payload = {
                "prompt": prompt,
                "modelId": target_model,
                "width": width,
                "height": height,
                "num_images": 1,
                "public": False,
                "alchemy": False,
                "ultra": False,
                "contrast": 3.5,
                "styleUUID": "111dc692-d470-4eec-b791-3475abac4c46"  # Photography style
            }
            cost_amount = 0.012  # Lucid Origin is cheaper without alchemy
        else:
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
            
            if mode == "FAST":
                payload["alchemy"] = False
                payload["promptMagic"] = False
                cost_amount = 0.012
            else:
                payload["promptMagic"] = True
                cost_amount = 0.0852
        
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        if init_image_id and not is_lucid:
            payload["init_image_id"] = init_image_id
            payload["imagePrompts"] = [init_image_id]
        
        print(f"Leonardo V1 Request: model={target_model}, is_lucid={is_lucid}")
        resp = requests.post(f"{self.leonardo_v1_url}/generations", headers=headers, json=payload)
        if resp.status_code != 200:
            print(f"!!! LEONARDO V1 ERROR ({resp.status_code}) !!!")
            print(f"URL: {self.leonardo_v1_url}/generations")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            print(f"Response: {resp.text}")
            resp.raise_for_status()
        
        gen_id = resp.json()["sdGenerationJob"]["generationId"]
        
        # 2. Poll for completion
        img_url = self._poll_leonardo(gen_id, headers)
        
        # 3. Download
        self._download_image(img_url, out_path)
        
        return {"amount": cost_amount}

    def generate_leonardo_v2(self, prompt: str, out_path: Path, size: str = "1024x1792", negative_prompt: Optional[str] = None, init_image_id: Optional[str] = None, mode: str = "QUALITY", model_id: Optional[str] = None) -> Optional[Dict[str, Any]]:

        """Generates an image using Leonardo.ai V2 API with GPT Image-1.5 model."""
        if not self.leonardo_api_key:
            raise RuntimeError("LEONARDO_API_KEY not configured")

        width, height = self._normalize_size(size)
        
        headers = {
            "Authorization": f"Bearer {self.leonardo_api_key}",
            "Content-Type": "application/json",
            "accept": "application/json"
        }
        # Ensure model is valid for V2. If it's a UUID, it might be V1.
        # But we'll trust the caller for now, default to gpt-image-1.5
        v2_model = model_id if model_id and "-" not in model_id else "gpt-image-1.5"
        if model_id == "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3":
            v2_model = "phoenix"

        # EXTREME SIMPLICITY FOR V2 - No guidance, no fancy things first.
        payload = {
            "model": v2_model,
            "parameters": {
                "prompt": prompt,
                "width": width,
                "height": height,
                "quantity": 1
            },
            "public": False
        }
        
        # Only add negative if not empty
        if negative_prompt and negative_prompt.strip():
            payload["parameters"]["negative_prompt"] = negative_prompt
            
        print(f"!!! LEONARDO V2 DEBUG !!! -> URL: {self.leonardo_v2_url}/generations")
        print(f"!!! LEONARDO V2 DEBUG !!! -> Payload: {json.dumps(payload, indent=2)}")

        resp = requests.post(f"{self.leonardo_v2_url}/generations", headers=headers, json=payload)
        
        if resp.status_code != 200:
            print(f"!!! LEONARDO V2 ERROR ({resp.status_code}) !!!")
            print(f"!!! RESPONSE TEXT: {resp.text}")
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
            print(f"!!! NO GENERATION ID IN RESPONSE: {resp_data}")
            raise RuntimeError(f"Leonardo V2 failed to return a generation ID: {resp_data}")
        
        cost_info = resp_data.get("generate", {}).get("cost") or resp_data.get("generations", {}).get("cost")
        
        # 2. Poll for completion (V2 uses same retrieval endpoint but different URL base)
        img_url = self._poll_leonardo(gen_id, headers, url_base=self.leonardo_v2_url)
        
        # 3. Download
        self._download_image(img_url, out_path)
        
        # Define costs for V2 based on mode
        v2_costs = {
            "FAST": 0.012,
            "QUALITY": 0.0852,
            "ULTRA": 0.0852 # Or whatever the user provided
        }
        
        return {"amount": v2_costs.get(mode, 0.0852)}

    def _normalize_size(self, size: str) -> tuple[int, int]:
        """Normalizes dimensions to Leonardo compatible sizes (multiples of 8)."""
        try:
            w, h = map(int, size.split("x"))
            
            # Leonardo requires multiples of 8.
            # However, for GPT-1.5, we should stay within certain limits for best quality.
            # Max dimensions are usually around 1792 for one side.
            w = (w // 8) * 8
            h = (h // 8) * 8
            
            # Ensure within limits (Leonardo V2 supports up to 1024x1792 or 1792x1024)
            if w > 1792: w = 1792
            if h > 1792: h = 1792
            
            return w, h
        except:
            return 1024, 1024

    def _poll_leonardo(self, gen_id: str, headers: dict, timeout=300, url_base: Optional[str] = None) -> str:
        base = url_base or self.leonardo_v1_url
        t0 = time.time()
        while time.time() - t0 < timeout:
            resp = requests.get(f"{base}/generations/{gen_id}", headers=headers)
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

    def generate_thumbnail(self, hook: str, visual_prompt: str, out_path: Path, size: str = "1024x1792", model_id: Optional[str] = None, negative_prompt: Optional[str] = None, mode: str = "QUALITY") -> None:
        """Generates a professional thumbnail. Blends visual prompt with text instructions. 
        Defaults to gpt-image-1.5 for better text rendering.
        """

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

        # Force GPT Image 1.5 for thumbnails if not specified
        target_model = model_id or "gpt-image-1.5"
        
        # For survival: Force a safe size for thumbnail if we don't trust the incoming one
        thumb_size = size
        if "x" not in size or not size:
            thumb_size = "1024x1024"
            
        self.generate_leonardo_image(base_prompt, out_path, size=thumb_size, model_id=target_model, negative_prompt=negative_prompt, mode=mode)

    def _download_image(self, url: str, out_path: Path):
        resp = requests.get(url, stream=True)
        resp.raise_for_status()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
