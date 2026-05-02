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
        self.grok_api_key = grok_api_key or os.getenv("GROK_API_KEY")
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
            "You are a creative visual director who turns narration paragraphs into AI image prompts. "
            "Your #1 PRIORITY is VISUAL FIDELITY TO THE SPECIFIC PARAGRAPH given to you. "
            "The image must depict the EXACT concept the narrator is explaining at this moment, "
            "not a generic scene of the video's overall theme. "

            "WORKFLOW: "
            "1. READ the narration paragraph carefully. "
            "2. IDENTIFY the SPECIFIC concept being explained (the psychological dynamic, the exact event, the metaphor invoked). "
            "3. DESIGN a visual metaphor that depicts THAT specific concept. "
            "4. APPLY the style guidelines AS A VISUAL WRAPPER (lighting, color grading, composition mood) — never as content driver. "
            "WHAT (from narration) > HOW (from style). Always. "

            "ANTI-CLICHÉ RULES — VIOLATE ONLY IF THE PARAGRAPH EXPLICITLY MENTIONS THESE: "
            "- DO NOT add rain, storms, water cascades, weather imagery unless the narration explicitly invokes them. "
            "- DO NOT add religious iconography (crosses, churches, cathedrals, halos, virgin/angelic robes) unless the narration explicitly mentions them. "
            "- DO NOT add fantasy/occult elements: glowing rune portals, etched magical symbols, druidic robes, hooded mystics, floating spell orbs, visible magic spells, witch/wizard staging. "
            "- DO NOT add abstract symbolic objects (orbs in hands, etched stones, shimmering crystals, glowing books) as a substitute for depicting the paragraph's actual concept. The metaphor must come from the narration, not from generic 'mystical' tropes. "
            "- DO NOT default to 'lone person looking pensively into distance' — if the paragraph is about a relational/psychological dynamic, depict that dynamic (e.g., interaction between two figures, projection, mirror). "
            "- DO NOT introduce elements absent from the narration just because they fit the channel's general vibe. "
            "- For psychology/dream content, prefer GROUNDED metaphors (real settings, real-life situations subtly distorted) over fantasy/mystical ones. The unconscious is human, not magical. "

            f"{rules_text}"

            "CHRONOLOGY & VARIETY: "
            "- Maintain character consistency (age, face, clothing) across the video, but CHANGE composition, angle, and specific interaction every prompt. "
            "- If 'Recent History' shows a setting was used, MOVE the camera or CHANGE the scene. "
            "- IF THE VIDEO INVOLVES SUPERNATURAL/CELESTIAL BEINGS (Angels, Demons, Spirits), DESCRIBE their supernatural features (wings, glowing aura, ethereal light) so they don't render as ordinary humans. "

            "ANATOMICAL CORRECTNESS: "
            "- Two arms, two legs, five fingers per hand. "
            "- Feet point in natural direction (no inverted/backwards). "
            "- Limbs connect naturally to torso. Realistic proportions. "
            "- Simple, natural poses. AVOID jumping, running, acrobatics, twisted torsos, lifted legs. "
            "- For elderly characters: slow, gentle, stable movements. "

            f"\nSTYLE SPECIFIC RULES:\n{style.get('post_note', '')}\n"

            "OUTPUT FORMAT: "
            "- Describe scene, framing (close-up / wide / over-shoulder...), lighting, composition. "
            "- English. Each prompt under 800 characters. One prompt per line. No bullet points, no numbering."
        )

        history_msg = f"\nRecent History (avoid repeating these compositions):\n" + "\n".join(recent_history[:5]) if recent_history else ""
        context_msg = f"\nOverall Video Theme (background only — DO NOT use this to invent scenes; use ONLY the paragraph below):\n{full_context[:800]}..." if full_context else ""

        user_msg = (
            f"### PARAGRAPH TO VISUALIZE (this is the ONLY source of WHAT to depict):\n"
            f"\"{text}\"\n\n"
            f"### YOUR JOB:\n"
            f"Describe the SPECIFIC concept of this paragraph using a visual metaphor. "
            f"Do NOT generalize to the channel's broad theme. Do NOT add elements (weather, religious symbols, etc.) absent from the paragraph above.\n"
            f"{context_msg}\n"
            f"{history_msg}\n\n"
            f"### STYLE WRAPPER (only HOW it looks, never WHAT is in it):\n"
            f"{style_prompt}\n\n"
            f"Output {n} unique prompt(s) that depict the SPECIFIC concept of the paragraph above, dressed in the style above."
        )

        
        response = self.openai_client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=1.0
        )

        content = response.choices[0].message.content.strip()
        print(f"[generate_prompts] LLM raw response (first 200 chars): {content[:200]!r}", flush=True)
        # Filter and truncate prompts to 800 chars
        prompts = []
        for p in content.split("\n"):
            p = p.strip("-• ").strip()
            if len(p.split()) > 3:
                prompts.append(p[:800])
        print(f"[generate_prompts] Returning {len(prompts[:n])} prompt(s); first: {(prompts[0][:120] if prompts else 'NONE')!r}", flush=True)
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

    async def generate_thumbnail(self, hook: str, visual_prompt: str, out_path: Path, size: str = "1024x1792", model_id: Optional[str] = None, negative_prompt: Optional[str] = None, mode: str = "QUALITY", channel_name: Optional[str] = None, workflow_name: Optional[str] = None) -> None:
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
            biblical_keywords = ["biblical", "jesus", "apostle", "god", "divine", "revelation", "prophecy", "bible", "sacred", "angel", "miracle", "christ", "mary"]
            
            workflow = workflow_name
            if not workflow:
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

        # Font configuration: prefer bundled condensed display fonts (Anton, Bebas Neue)
        # for that "PENTECOSTES" look, fall back to system fonts.
        bundled_fonts_dir = Path(__file__).parent.parent / "fonts"
        font_paths_heavy = [
            str(bundled_fonts_dir / "Anton-Regular.ttf"),       # condensed display
            str(bundled_fonts_dir / "BebasNeue-Regular.ttf"),   # alt condensed
            "/usr/share/fonts/truetype/msttcorefonts/ariblk.ttf",
            "/usr/share/fonts/truetype/msttcorefonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        font_paths_bold = [
            "/usr/share/fonts/truetype/msttcorefonts/arialbd.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            str(bundled_fonts_dir / "Anton-Regular.ttf"),
        ]

        font_path_heavy = next((p for p in font_paths_heavy if Path(p).exists()), None)
        font_path_bold = next((p for p in font_paths_bold if Path(p).exists()), font_path_heavy)

        def draw_text_with_outline(draw_obj, text_str, pos, font_obj, fill_color, outline_color, outline_width=4, align="left"):
            x, y = pos
            if align == "center":
                bbox = draw_obj.textbbox((0, 0), text_str, font=font_obj)
                w = bbox[2] - bbox[0]
                x = (width - w) // 2
            # Pillow stroke_width is faster and cleaner than the bruteforce loop
            draw_obj.text(
                (x, y), text_str, font=font_obj, fill=fill_color,
                stroke_width=outline_width, stroke_fill=outline_color,
            )
            return x, y

        def make_vertical_gradient(size: Tuple[int, int], top_color: Tuple[int, int, int], bottom_color: Tuple[int, int, int]) -> Image.Image:
            """Returns an RGBA image filled with a vertical gradient from top_color to bottom_color."""
            w, h = size
            grad = Image.new("RGB", (1, h))
            for y in range(h):
                t = y / max(1, h - 1)
                r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
                g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
                b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
                grad.putpixel((0, y), (r, g, b))
            return grad.resize((w, h)).convert("RGBA")

        def draw_text_with_gradient(canvas, text_str, pos, font_obj, top_color, bottom_color, outline_color="black", outline_width=8, align="center"):
            """Stamp text with a vertical gradient fill + black outline.
            Uses Pillow's stroke_width for the outline pass and a mask-paste for the gradient."""
            x, y = pos
            bbox = canvas.getchannel("A").info if False else None  # noop, kept for readability
            tmp_draw = ImageDraw.Draw(canvas)
            tb = tmp_draw.textbbox((0, 0), text_str, font=font_obj, stroke_width=outline_width)
            text_w = tb[2] - tb[0]
            text_h = tb[3] - tb[1]
            if align == "center":
                x = (width - text_w) // 2 - tb[0]

            # 1) outline pass directly on the canvas (black stroke, transparent fill)
            tmp_draw.text(
                (x, y), text_str, font=font_obj,
                fill=(0, 0, 0, 0),
                stroke_width=outline_width, stroke_fill=outline_color,
            )

            # 2) gradient fill: render text alpha as a mask, paste a gradient through it
            mask = Image.new("L", canvas.size, 0)
            ImageDraw.Draw(mask).text((x, y), text_str, font=font_obj, fill=255)
            gradient = make_vertical_gradient(canvas.size, top_color, bottom_color)
            canvas.paste(gradient, (0, 0), mask)

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
            # 3-line style: top label · big gradient title · italic-ish subtitle
            parts = text.split("...")
            label = parts[0].strip().upper() if len(parts) > 0 else "MENSAJE DE"
            title = parts[1].strip().upper() if len(parts) > 1 else ""
            subtitle = parts[2].strip().lower() if len(parts) > 2 else ""

            base_dim = min(width, height)
            size_top = int(base_dim * 0.08)
            size_center = int(base_dim * 0.22)  # bigger to match reference
            size_bottom = int(base_dim * 0.06)

            max_w = width * 0.95

            font_top = get_fitting_font(label, font_path_heavy, max_w, size_top)
            font_center = get_fitting_font(title, font_path_heavy, max_w, size_center)
            font_bottom = get_fitting_font(subtitle, font_path_bold, max_w, size_bottom)

            # Top label: white with thick black outline
            draw_text_with_outline(
                draw, label, (0, int(height * 0.18)),
                font_top, "white", "black", outline_width=4, align="center",
            )

            # Center title: yellow → orange gradient with thick black outline
            if title:
                draw_text_with_gradient(
                    img, title, (0, int(height * 0.42)),
                    font_center,
                    top_color=(255, 224, 90),    # warm yellow
                    bottom_color=(255, 130, 30), # orange
                    outline_color="black",
                    outline_width=10,
                    align="center",
                )
                # rebind draw to the (now mutated) canvas for any subsequent ops
                draw = ImageDraw.Draw(img)

            # Bottom subtitle: white with thinner outline
            if subtitle:
                draw_text_with_outline(
                    draw, subtitle, (0, int(height * 0.74)),
                    font_bottom, "white", "black", outline_width=3, align="center",
                )

        elif style == "sombras":
            # 2-line stacked layout for "Sombras del Norte" horror/mystery thumbnails:
            #   line1 (top, big, gradient yellow→orange, condensed) + ellipsis
            #   line2 (below, italic white, smaller) preceded by ellipsis
            if "..." in text:
                parts = text.split("...", 1)
                line1 = parts[0].strip() + "..."
                line2 = ("..." + parts[1].strip()) if parts[1].strip() else ""
            else:
                words = text.split()
                if len(words) > 4:
                    line1 = " ".join(words[:len(words) // 2]) + "..."
                    line2 = "..." + " ".join(words[len(words) // 2:])
                else:
                    line1 = text
                    line2 = ""

            base_dim = min(width, height)
            size_1 = int(base_dim * 0.16)
            size_2 = int(base_dim * 0.11)  # bigger so the italic line carries more weight

            max_w = width * 0.95

            font1 = get_fitting_font(line1.upper(), font_path_heavy, max_w, size_1)

            # Italic font for the subtitle line. Bold italic if available, otherwise fall back.
            italic_candidates = [
                "/usr/share/fonts/truetype/liberation/LiberationSans-BoldItalic.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
                font_path_bold,  # last-resort fallback
            ]
            font_path_italic = next((p for p in italic_candidates if p and Path(p).exists()), font_path_bold)
            font2 = get_fitting_font(line2.upper(), font_path_italic, max_w, size_2)

            # Stack near the top so the title reads above the main subject in the artwork.
            # Measure the rendered bbox of line1 (with stroke) to position line2 cleanly below it.
            y_line1 = int(height * 0.08)
            outline_w_1 = 8
            line1_bbox = draw.textbbox((0, y_line1), line1.upper(), font=font1, stroke_width=outline_w_1)
            line1_bottom = line1_bbox[3]
            gap = int(size_2 * 0.25)  # breathing room between lines
            y_line2 = line1_bottom + gap

            if line1:
                draw_text_with_gradient(
                    img, line1.upper(), (0, y_line1),
                    font1,
                    top_color=(255, 224, 90),
                    bottom_color=(255, 105, 20),  # stronger orange at the bottom
                    outline_color="black",
                    outline_width=outline_w_1,
                    align="center",
                )
                draw = ImageDraw.Draw(img)

            if line2:
                # Solid warm orange to echo the gradient's bottom tone, thicker outline
                draw_text_with_outline(
                    draw, line2.upper(), (0, y_line2),
                    font2, (255, 140, 30), "black", outline_width=6, align="center",
                )

        else:
            # Default 2-line style (generic / fallback)
            if "..." in text:
                parts = text.split("...", 1)
                line1 = parts[0].strip() + "..."
                line2 = ("..." + parts[1].strip()) if parts[1].strip() else ""
            else:
                words = text.split()
                if len(words) > 4:
                    line1 = " ".join(words[:len(words) // 2])
                    line2 = " ".join(words[len(words) // 2:])
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

            is_vertical = height > width
            align_mode = "center" if is_vertical else "left"
            draw_x = 0 if is_vertical else margin_x

            if line1:
                _, draw_y = draw_text_with_outline(draw, line1.upper(), (draw_x, curr_y), font1, "yellow", "black", outline_width=6, align=align_mode)
                curr_y = draw_y + int(font_size_1 * 1.1)

            if line2:
                draw_text_with_outline(draw, line2.upper(), (draw_x, curr_y), font2, "#FF8C00", "black", outline_width=6, align=align_mode)

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
        
    def generate_grok_video(self, prompt: str, image_path: Path, out_path: Path, duration: int = 8, orientation: str = "vertical") -> dict:
        """
        Uses xAI grok-imagine-video to generate an mp4 video out of an image.
        Returns an approximate cost object.
        """
        if not self.grok_api_key:
            raise RuntimeError("GROK_API_KEY not configured")

        import base64
        ext = image_path.suffix.lower()
        mime = "image/png" if ext == ".png" else ("image/webp" if ext == ".webp" else "image/jpeg")
        img_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        data_uri = f"data:{mime};base64,{img_b64}"

        clean_prompt = prompt.replace("\n", " ").strip()
        if len(clean_prompt) > 1500:
            clean_prompt = clean_prompt[:1497] + "..."

        headers = {
            "Authorization": f"Bearer {self.grok_api_key}",
            "Content-Type": "application/json",
        }

        # Step 1: Start generation
        # NOTE 1: El campo REST es "image" y espera un struct ImageUrl: {"url": "..."}.
        # (no string plano: xAI rechaza con 422 "expected struct ImageUrl").
        # NOTE 2: No enviamos aspect_ratio en image-to-video — la doc de xAI dice que
        # sobrescribe (estira) la imagen origen. Sin él, Grok hereda el aspect natural.
        payload = {
            "model": "grok-imagine-video",
            "prompt": clean_prompt,
            "image": {"url": data_uri},
            "duration": duration,
            "resolution": "720p",
        }

        resp = requests.post("https://api.x.ai/v1/videos/generations", headers=headers, json=payload, timeout=60)
        if resp.status_code != 200:
            print(f"!!! GROK VIDEO GEN ERROR ({resp.status_code}) !!! {resp.text}", flush=True)
            raise RuntimeError(f"Grok video generation failed ({resp.status_code}): {resp.text}")

        request_id = resp.json().get("request_id")
        if not request_id:
            raise RuntimeError("Grok video generation: no request_id returned")

        print(f"[grok-video] Request started: {request_id}", flush=True)

        # Step 2: Poll until done (up to 10 minutes)
        t0 = time.time()
        timeout_s = 600
        while time.time() - t0 < timeout_s:
            time.sleep(5)
            poll_resp = requests.get(f"https://api.x.ai/v1/videos/{request_id}", headers=headers, timeout=30)
            if poll_resp.status_code != 200:
                print(f"[grok-video] Poll error ({poll_resp.status_code}): {poll_resp.text}", flush=True)
                continue
            data = poll_resp.json()
            status = data.get("status")
            print(f"[grok-video] Status: {status}", flush=True)
            if status == "done":
                video_url = (data.get("video") or {}).get("url")
                if not video_url:
                    raise RuntimeError(f"Grok video done but no URL: {data}")
                self._download_image(video_url, out_path)
                # Approximate cost: 720p ~= $0.10/s, 480p ~= $0.05/s. Using 0.10 for default 720p.
                cost_amount = 0.10 * duration
                return {"amount": cost_amount, "model": "grok-imagine-video"}
            if status == "failed":
                raise RuntimeError(f"Grok video generation failed: {data}")
            if status == "expired":
                raise RuntimeError("Grok video generation request expired")

        raise TimeoutError("Grok video generation timeout (10 min)")

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
