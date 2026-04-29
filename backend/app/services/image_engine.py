import os
import json
import time
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI
from app.services.style_service import StyleService
from app.services.comfy_service import ComfyService
import asyncio
from PIL import Image, ImageDraw, ImageFont, ImageFilter

class ImageEngine:
    def __init__(self, openai_api_key: Optional[str] = None, leonardo_api_key: Optional[str] = None, grok_api_key: Optional[str] = None, provider: str = "openai"):
        self.provider = provider.lower()
        base_url = None
        
        if self.provider == "grok":
            base_url = "https://api.x.ai/v1"
            api_key = grok_api_key or os.getenv("GROK_API_KEY")
            self.model = "grok-4.20-beta"
        else:
            api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
            self.model = "gpt-4o-mini"

        self.openai_client = OpenAI(api_key=api_key, base_url=base_url)
        self.leonardo_api_key = leonardo_api_key or os.getenv("LEONARDO_API_KEY")
        self.leonardo_v1_url = "https://cloud.leonardo.ai/api/rest/v1"
        self.leonardo_v2_url = "https://cloud.leonardo.ai/api/rest/v2"
        self.comfy_service = ComfyService()
        self.comfy_url = os.getenv("COMFY_URL")

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
            "- ABSOLUTELY AVOID: jumping, running, high-impact movements, acrobatics. "
            "- POSE RESTRICTION: Keep poses simple and natural. AVOID complex limb arrangements like lifting legs, crossing legs in mid-air, or extremely twisted torsos. "
            f"\nSTYLE SPECIFIC RULES:\n{style.get('post_note', '')}\n"

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
            model=self.model,
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
            "- POSE RESTRICTION: Keep poses simple and natural. AVOID complex limb arrangements like lifting legs, crossing legs in mid-air, or extremely twisted torsos. "
            f"\nSTYLE SPECIFIC RULES:\n{style.get('post_note', '')}\n"
            "Output ONLY the prompt text in English."
        )
        
        user_msg = (
            f"Previous Scene Prompt: {previous_prompt}\n\n"
            f"New Narration: {text}\n\n"
            f"Style: {style_prompt}\n\n"
            "Generate a prompt for the next shot that logically follows the previous one while being relevant to the new narration."
        )
        
        response = self.openai_client.chat.completions.create(
            model=self.model,
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

    async def generate_leonardo_image(self, prompt: str, out_path: Path, size: str = "1024x1792", negative_prompt: Optional[str] = None, model_id: Optional[str] = None, init_image_id: Optional[str] = None, mode: str = "QUALITY", seed: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Generates an image using Leonardo.ai with optional model selection and image guidance. Defaults to V2."""
        use_v2 = os.getenv("LEONARDO_API_VERSION", "v2").lower() == "v2"
        
        # Determine if we should use V2
        # Clean model_id in case it has trailing spaces
        mid = (model_id or "").strip()
        v2_model_names = ["gpt-image-1.5", "phoenix", "phoenix-v2", "gemini-image-2"]
        # Phoenix UUID de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3 can be used in V1 sometimes,
        # but Leonardo is pushing for V2 on newer models.
        
        is_explicit_v2 = mid in v2_model_names
        
        if (use_v2 and not mid) or is_explicit_v2:
            print(f"Routing to Leonardo V2: model={mid or 'default'}")
            return await self.generate_leonardo_v2(prompt, out_path, size=size, negative_prompt=negative_prompt, init_image_id=init_image_id, mode=mode, model_id=mid, seed=seed)

            
        # V1 logic
        if not self.leonardo_api_key:
            raise RuntimeError("LEONARDO_API_KEY not configured")

        target_model = model_id or "de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3"
        width, height = self._normalize_size(size, model_id=target_model)
        
        headers = {
            "Authorization": f"Bearer {self.leonardo_api_key}",
            "Content-Type": "application/json"
        }
        
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

        if seed is not None:
            payload["seed"] = seed

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
        img_data = self._poll_leonardo(gen_id, headers)
        img_url = img_data["url"]
        
        # 3. Download
        self._download_image(img_url, out_path)
        
        return {"amount": cost_amount, "seed": img_data.get("seed")}

    async def generate_comfy_image(self, prompt: str, out_path: Path, size: str = "1024x1024", negative_prompt: Optional[str] = None, workflow_name: str = "Comic-Horror.json", seed: Optional[int] = None) -> Dict[str, Any]:
        """Generates an image using local ComfyUI via ComfyService."""
        # Use absolute path inside Docker container
        workflow_path = Path("/app/workflows") / workflow_name
        
        if not workflow_path.exists():
            workflow_path = Path("workflows") / workflow_name

        if not workflow_path.exists():
            raise FileNotFoundError(f"Workflow {workflow_name} not found.")

        # 1. Load the base workflow JSON
        with open(workflow_path, "r") as f:
            base_workflow = json.load(f)

        # 2. Prepare dimensions
        try:
            w, h = map(int, size.split("x"))
        except:
            w, h = 1024, 1024

        # 3. Inject parameters into workflow
        workflow = self.comfy_service.prepare_workflow(
            base_workflow,
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=w,
            height=h,
            seed=seed
        )

        print(f"Executing ComfyUI workflow: {workflow_name}")
        
        # 4. Execute
        result = await self.comfy_service.generate_image(workflow, out_path)
        
        return {"amount": 0.0, "seed": result.get("seed")}

    async def generate_leonardo_v2(self, prompt: str, out_path: Path, size: str = "1024x1792", negative_prompt: Optional[str] = None, init_image_id: Optional[str] = None, mode: str = "QUALITY", model_id: Optional[str] = None, seed: Optional[int] = None) -> Optional[Dict[str, Any]]:

        """Generates an image using Leonardo.ai V2 API with GPT Image-1.5 model."""
        if not self.leonardo_api_key:
            raise RuntimeError("LEONARDO_API_KEY not configured")

        # Ensure model is valid for V2. If it's a UUID, it might be V1.
        valid_v2_models = ["gpt-image-1.5", "phoenix", "phoenix-v2", "gemini-image-2"]
        v2_model = model_id if model_id in valid_v2_models else "gpt-image-1.5"

        width, height = self._normalize_size(size, model_id=v2_model)
        
        headers = {
            "Authorization": f"Bearer {self.leonardo_api_key}",
            "Content-Type": "application/json",
            "accept": "application/json"
        }
        
        # SANITIZE PROMPT: Leonardo V2 strongly rejects prompts longer than 1000 chars or containing line breaks
        clean_prompt = prompt.replace("\n", " ")
        if len(clean_prompt) > 900:
            clean_prompt = clean_prompt[:897] + "..."
            
        # ALIGN WITH OFFICIAL GPT-1.5 DOCUMENTATION
        payload = {
            "model": v2_model,
            "parameters": {
                "prompt": clean_prompt,
                "width": width,
                "height": height,
                "quantity": 1,
                "mode": mode,
                "prompt_enhance": "OFF",
                "seed": seed if seed is not None else random.randint(0, 2**31-1)
            },
            "public": False
        }
        
        # Only add negative if not empty
        if negative_prompt and negative_prompt.strip():
            payload["parameters"]["negative_prompt"] = negative_prompt
            
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
        
        # 2. Poll for completion (Leonardo retrieval endpoint is always in V1)
        img_data = self._poll_leonardo(gen_id, headers)
        img_url = img_data["url"]
        
        # 3. Download
        self._download_image(img_url, out_path)
        
        # Define costs for V2 based on mode
        v2_costs = {
            "FAST": 0.012,
            "QUALITY": 0.0852,
            "ULTRA": 0.0852 # Or whatever the user provided
        }
        
        return {"amount": v2_costs.get(mode, 0.0852), "seed": img_data.get("seed")}
        

    def _normalize_size(self, size: str, model_id: Optional[str] = None) -> tuple[int, int]:
        """Normalizes dimensions to Leonardo compatible sizes.
        V2 models (GPT-1.5) support specific resolutions: 
        1:1 (1024x1024), 2:3 (1024x1536), 3:2 (1536x1024)
        Nano Banana Pro strictly uses precise FLUX buckets like 848x1264 directly from UI.
        """
        try:
            w, h = map(int, size.split("x"))
            ratio = w / h
            
            # Standard rounding to multiple of 8
            w = (w // 8) * 8
            h = (h // 8) * 8
            
            is_nano = model_id == "gemini-image-2"
            
            # If it's a V2 compatible size (we assume we are calling it for V2 mostly now)
            # 16:9 / 3:2 exact UI buckets for Nano Banana Pro constraint
            if ratio > 1.3:
                return (1376, 768) if is_nano else (1536, 1024)
            # 9:16 / 2:3 exact UI buckets for Nano Banana Pro constraint 
            elif ratio < 0.8:
                return (848, 1264) if is_nano else (1024, 1536)
            else:
                return 1024, 1024
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
                return {
                    "url": data["generated_images"][0]["url"],
                    "seed": data.get("seed")
                }
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

    async def generate_thumbnail(self, hook: str, visual_prompt: str, out_path: Path, size: str = "1024x1792", model_id: Optional[str] = None, negative_prompt: Optional[str] = None, mode: str = "QUALITY", channel_name: Optional[str] = None) -> None:
        """Generates a professional thumbnail. Blends visual prompt with text instructions. 
        """

        # Add quality and detail keywords
        if "8k" not in visual_prompt.lower():
            visual_prompt += ", extreme detail, 8k resolution, cinematic lighting"
        
        # Add hand boosters if hands are mentioned
        if "hand" in visual_prompt.lower() or "finger" in visual_prompt.lower() or "gesturing" in visual_prompt.lower():
            visual_prompt += ", (perfect hands:1.2), (detailed fingers:1.3), natural hand pose"
        
        # Add age boosters if child/young age mentioned
        vp_lower = visual_prompt.lower()
        if any(x in vp_lower for x in ["child", "girl", "boy", "ten", "aged 10", "young"]):
            if "child" not in visual_prompt.lower():
                visual_prompt += ", (child:1.4), (small child:1.2), youthful features"
            else:
                visual_prompt = visual_prompt.replace("child", "(child:1.5)")
        
        # Detect channel style
        style = "default"
        if channel_name and ("jesus" in channel_name.lower() or "jesús" in channel_name.lower()):
            style = "jesus"
        elif channel_name and "sombras" in channel_name.lower():
            style = "sombras"

        # Ensure the subject is on the right to leave space for text on the left
        if "right side" not in visual_prompt.lower() and style != "jesus":
            visual_prompt = f"Subject on the right side of the frame, empty space on the left for text overlay. {visual_prompt}"

        # Generate base image
        if self.comfy_url:
            # Dynamic workflow selection
            vp_lower = visual_prompt.lower()
            biblical_keywords = ["biblical", "jesus", "apostle", "god", "divine", "revelation", "prophecy", "bible", "sacred"]
            if any(k in vp_lower for k in biblical_keywords):
                workflow = "Biblical-Epic-Ultra.json"
            elif "anime" in vp_lower or "illustration" in vp_lower or "hentai" in vp_lower:
                workflow = "Anime-Illustration-Ultra.json"
            elif "photorealistic" in vp_lower or "cinematic horror" in vp_lower or "film still" in vp_lower:
                workflow = "Cinematic-Horror-Ultra.json"
            else:
                workflow = "Comic-Horror-Ultra.json"
            
            await self.generate_comfy_image(
                prompt=visual_prompt, 
                out_path=out_path, 
                size=size, 
                negative_prompt=negative_prompt,
                workflow_name=workflow
            )
        else:
            target_model = model_id or "gpt-image-1.5"
            thumb_size = size
            if "x" not in size or not size:
                thumb_size = "1024x1024"
            self.generate_leonardo_image(visual_prompt, out_path, size=thumb_size, model_id=target_model, negative_prompt=negative_prompt, mode=mode)
            
        # Save a "clean" copy before applying text
        clean_path = out_path.parent / "thumbnail-clean.png"
        import shutil
        shutil.copy2(out_path, clean_path)

        # Apply text overlay using Python
        self._apply_thumbnail_text_overlay(out_path, hook, channel_name=channel_name)

    def apply_text_to_thumbnail(self, base_dir: str, hook: str, channel_name: Optional[str] = None) -> str:
        """Re-applies text overlay to an existing clean thumbnail."""
        out_path = Path(base_dir) / "output" / "thumbnail.png"
        clean_path = Path(base_dir) / "output" / "thumbnail-clean.png"
        
        if not clean_path.exists():
            if out_path.exists():
                # If clean doesn't exist, we use the current one as base (not ideal but works as fallback)
                import shutil
                shutil.copy2(out_path, clean_path)
            else:
                raise FileNotFoundError("No se encontró una miniatura base para aplicar el texto.")
        
        # Always start from the clean version
        import shutil
        shutil.copy2(clean_path, out_path)
        
        # Apply text
        self._apply_thumbnail_text_overlay(out_path, hook, channel_name=channel_name)
        return f"cache/{os.path.relpath(out_path, 'cache')}"

    def _apply_thumbnail_text_overlay(self, image_path: Path, text: str, channel_name: Optional[str] = None):
        """Applies text overlay following the channel style guide."""
        if not image_path.exists():
            return

        img = Image.open(image_path).convert("RGBA")
        width, height = img.size
        draw = ImageDraw.Draw(img)

        # Detect channel style
        style = "default"
        if channel_name and ("jesus" in channel_name.lower() or "jesús" in channel_name.lower()):
            style = "jesus"
        elif channel_name and "sombras" in channel_name.lower():
            style = "sombras"

        # Font configuration (Fallback paths)
        font_paths = [
            "/usr/share/fonts/truetype/msttcorefonts/arialbd.ttf",
            "/usr/share/fonts/truetype/msttcorefonts/ariblk.ttf", # Arial Black
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        ]
        
        font_path_bold = next((p for p in font_paths if Path(p).exists()), None)
        # Try to find a specifically thick one for Bebas Neue substitute
        font_path_heavy = next((p for p in font_paths if "ariblk" in p and Path(p).exists()), font_path_bold)

        def draw_text_with_outline(draw_obj, text_str, pos, font_obj, fill_color, outline_color, outline_width=4, align="left"):
            x, y = pos
            if align == "center":
                # Calculate width using textbbox
                bbox = draw_obj.textbbox((0, 0), text_str, font=font_obj)
                w = bbox[2] - bbox[0]
                x = (width - w) // 2
            
            # Draw outline
            for adj in range(-outline_width, outline_width + 1):
                for adj_y in range(-outline_width, outline_width + 1):
                    draw_obj.text((x + adj, y + adj_y), text_str, font=font_obj, fill=outline_color)
            # Draw main text
            draw_obj.text((x, y), text_str, font=font_obj, fill=fill_color)
            return x, y

        def get_fitting_font(text_str, font_path, max_width, start_size):
            size = start_size
            font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
            if not font_path: return font
            while size > 10:
                bbox = draw.textbbox((0, 0), text_str, font=font)
                if (bbox[2] - bbox[0]) <= max_width:
                    break
                size -= 4
                font = ImageFont.truetype(font_path, size)
            return font

        if style == "jesus":
            # 3-line style for Jesus channel
            parts = text.split("...")
            label = parts[0].strip().upper() if len(parts) > 0 else "MENSAJE DE"
            title = parts[1].strip().upper() if len(parts) > 1 else ""
            subtitle = parts[2].strip().lower() if len(parts) > 2 else ""

            # Use min(width, height) to avoid massive fonts on vertical videos
            base_dim = min(width, height)
            size_top = int(base_dim * 0.08)
            size_center = int(base_dim * 0.18)
            size_bottom = int(base_dim * 0.07)
            
            max_w = width * 0.95

            font_top = get_fitting_font(label, font_path_bold, max_w, size_top)
            font_center = get_fitting_font(title, font_path_heavy, max_w, size_center)
            font_bottom = get_fitting_font(subtitle, font_path_bold, max_w, size_bottom)

            # Draw Top (18% from top)
            draw_text_with_outline(draw, label, (0, int(height * 0.18)), font_top, "white", "black", outline_width=4, align="center")
            
            # Draw Center
            if title:
                draw_text_with_outline(draw, title, (0, int(height * 0.45)), font_center, "#FFD700", "black", outline_width=8, align="center")
            
            # Draw Bottom (28% from bottom / 72% from top)
            if subtitle:
                draw_text_with_outline(draw, subtitle, (0, int(height * 0.72)), font_bottom, "white", "black", outline_width=4, align="center")

        else:
            # Default 2-line style (Sombras or generic)
            if "..." in text:
                parts = text.split("...", 1)
                line1 = parts[0].strip() + "..."
                line2 = ("..." + parts[1].strip()) if parts[1].strip() else ""
            else:
                words = text.split()
                if len(words) > 4:
                    line1 = " ".join(words[:len(words)//2])
                    line2 = " ".join(words[len(words)//2:])
                else:
                    line1 = text
                    line2 = ""

            base_dim = min(width, height)
            font_size_1 = int(base_dim * 0.15)
            font_size_2 = int(base_dim * 0.13)
            
            max_w = width * 0.95
            
            font1 = get_fitting_font(line1.upper(), font_path_bold, max_w, font_size_1)
            font2 = get_fitting_font(line2.upper(), font_path_bold, max_w, font_size_2)

            margin_x = int(width * 0.025)
            curr_y = int(height * 0.35)

            # Colors based on style
            color1, color2 = ("yellow", "#FF8C00") # Default
            if style == "sombras":
                color1, color2 = ("#ff3333", "#33ff33") # Red and Green for horror

            # Always center for vertical videos to look better, left for horizontal
            is_vertical = height > width
            align_mode = "center" if is_vertical else "left"
            draw_x = 0 if is_vertical else margin_x

            if line1:
                _, draw_y = draw_text_with_outline(draw, line1.upper(), (draw_x, curr_y), font1, color1, "black", outline_width=6, align=align_mode)
                curr_y = draw_y + int(font_size_1 * 1.1)

            if line2:
                draw_text_with_outline(draw, line2.upper(), (draw_x, curr_y), font2, color2, "black", outline_width=6, align=align_mode)

        # Save back
        img.convert("RGB").save(image_path, "PNG")
        print(f"[thumbnail] Applied {style} text overlay to {image_path.name}")

    def _download_image(self, url: str, out_path: Path):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        # Add Referer if it's a known protected domain (like Grok)
        if "grok.com" in url or "x.ai" in url:
            headers["Referer"] = "https://grok.com/"
            
        resp = requests.get(url, stream=True, headers=headers)
        resp.raise_for_status()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)

    def generate_leonardo_video(self, prompt: str, image_path: Path, out_path: Path, duration: int = 8, video_model: str = "VEO3FAST", orientation: str = "vertical") -> dict:
        """
        Uses Leonardo VEO3 to generate an mp4 video out of an image.
        Returns the approx cost object.
        """
        if not self.leonardo_api_key:
            raise RuntimeError("LEONARDO_API_KEY not configured")

        init_image_id = self.upload_init_image(image_path)
        if not init_image_id:
            raise RuntimeError("Could not upload init image to Leonardo for video generation")
            
        headers = {
            "Authorization": f"Bearer {self.leonardo_api_key}",
            "Content-Type": "application/json",
            "accept": "application/json"
        }
        
        # Sanitize prompt
        clean_prompt = prompt.replace("\n", " ").strip()
        if len(clean_prompt) > 900:
            clean_prompt = clean_prompt[:897] + "..."
            
        resolution = "RESOLUTION_1080" if video_model == "VEO3" else "RESOLUTION_720"
        
        if orientation == "vertical":
            w = 1080 if video_model == "VEO3" else 720
            h = 1920 if video_model == "VEO3" else 1280
        elif orientation == "horizontal":
            w = 1920 if video_model == "VEO3" else 1280
            h = 1080 if video_model == "VEO3" else 720
        else: # square/default
            w = 1080 if video_model == "VEO3" else 768
            h = 1080 if video_model == "VEO3" else 768
            
        payload = {
            "prompt": clean_prompt,
            "imageId": init_image_id,
            "imageType": "UPLOADED",
            "resolution": resolution,
            "duration": duration,
            "model": video_model,
            "isPublic": False
        }

        resp = requests.post(f"{self.leonardo_v1_url}/generations-image-to-video", headers=headers, json=payload)
        
        if resp.status_code != 200:
            print(f"!!! LEONARDO VIDEO GEN ERROR ({resp.status_code}) !!!")
            print(f"!!! RESPONSE TEXT: {resp.text}")
            resp.raise_for_status()
            
        resp_data = resp.json()
        
        gen_id = None
        if "motionVideoGenerationJob" in resp_data:
            gen_id = resp_data["motionVideoGenerationJob"].get("generationId")
        elif "motion_generation_job" in resp_data:
            gen_id = resp_data["motion_generation_job"].get("generationId")
        elif "generations" in resp_data:
            gen_id = resp_data["generations"].get("id")
            
        if not gen_id:
            # Maybe it returns {"generationId": "..."} directly
            gen_id = resp_data.get("generationId")
            
        if not gen_id:
            print(f"!!! NO GENERATION ID IN RESPONSE: {resp_data}")
            raise RuntimeError(f"Leonardo Video Gen failed to return a generation ID: {resp_data}")

        # 3. Poll for completion using V1 poll endpoint but looking for video URL
        video_url = self._poll_leonardo_video(gen_id, headers)
        
        # 4. Download Video
        self._download_image(video_url, out_path)
        
        cost_amount = 0.08 if video_model == "VEO3FAST" else 0.20 # Approximate costs
        return {"amount": cost_amount}
        
    def _poll_leonardo_video(self, gen_id: str, headers: dict, timeout=600) -> str:
        """Polls for video generation completion."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            resp = requests.get(f"{self.leonardo_v1_url}/generations/{gen_id}", headers=headers)
            resp.raise_for_status()
            data = resp.json().get("generations_by_pk")
            
            if data and data.get("status") == "COMPLETE":
                images = data.get("generated_images", [])
                if images:
                    # Look for motionMP4URL first, fallback to url
                    return images[0].get("motionMP4URL") or images[0].get("url")
            
            if data and data.get("status") in ["FAILED", "ERROR"]:
                raise RuntimeError(f"Leonardo Video generation failed: {data}")
            
            time.sleep(5)
        raise TimeoutError("Leonardo Video generation timeout")
