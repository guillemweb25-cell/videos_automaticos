import json
import random
import asyncio
import httpx
from pathlib import Path
from typing import Optional, Dict, Any
from app.config import get_settings

settings = get_settings()

class ComfyService:
    def __init__(self, comfy_url: Optional[str] = None):
        url = comfy_url or settings.COMFY_URL
        self.comfy_url = url.rstrip("/")
        self.client_id = f"video-auto-{random.randint(1000, 9999)}"

    async def run_workflow(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "prompt": workflow,
            "client_id": self.client_id,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            print(f"[DEBUG] Sending workflow to ComfyUI at {self.comfy_url}/prompt")
            # Log first checkpoint found for debug
            for node in workflow.values():
                if "ckpt_name" in node.get("inputs", {}):
                    print(f"[DEBUG] Target Checkpoint: {node['inputs']['ckpt_name']}")
                    break

            r = await client.post(f"{self.comfy_url}/prompt", json=payload)
            if r.status_code != 200:
                print(f"[DEBUG] ComfyUI Error Response: {r.text}")
            r.raise_for_status()
            return r.json()

    async def wait_for_result(self, prompt_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            while True:
                r = await client.get(f"{self.comfy_url}/history/{prompt_id}")
                r.raise_for_status()
                data = r.json()

                if prompt_id in data:
                    hist = data[prompt_id]
                    if hist["status"]["completed"]:
                        return hist

                await asyncio.sleep(1.0)

    async def download_image(self, filename: str, img_type: str = "output") -> bytes:
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.get(
                f"{self.comfy_url}/view",
                params={"filename": filename, "type": img_type},
            )
            r.raise_for_status()
            return r.content

    async def generate_image(self, workflow: Dict[str, Any], out_path: Path) -> Dict[str, Any]:
        """
        Executes a workflow and saves the resulting image to out_path.
        Returns a dict with metadata (like seed).
        """
        # Extract seed from workflow for metadata return
        seed = None
        for node in workflow.values():
            if "seed" in node.get("inputs", {}):
                seed = node["inputs"]["seed"]
                break
            elif "noise_seed" in node.get("inputs", {}):
                seed = node["inputs"]["noise_seed"]
                break

        # 1. Send workflow
        r = await self.run_workflow(workflow)
        prompt_id = r["prompt_id"]

        # 2. Wait for result
        hist = await self.wait_for_result(prompt_id)

        # 3. Find first output node with images
        if not hist.get("outputs"):
            raise RuntimeError(f"No outputs found in ComfyUI history for prompt {prompt_id}")
            
        node_id, node_output = next(iter(hist["outputs"].items()))
        if "images" not in node_output:
            raise RuntimeError(f"No images in output of node {node_id}")
            
        img_info = node_output["images"][0]
        filename = img_info["filename"]
        img_type = img_info.get("type", "output")

        # 4. Download
        data = await self.download_image(filename, img_type)

        # 5. Save
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        
        return {"out_path": out_path, "seed": seed}

    def prepare_workflow(self, 
        base_workflow: Dict[str, Any], 
        prompt: str, 
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        positive_node_id: Optional[str] = None,
        negative_node_id: Optional[str] = None,
        latent_node_id: Optional[str] = None,
        seed_node_id: Optional[str] = None,
        seed: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Injects parameters into a workflow dictionary.
        Tries to find nodes by ID, then by Title, then by Class Type.
        """
        workflow = json.loads(json.dumps(base_workflow)) # Deep copy

        # 1. Find Positive Prompt Node
        pos_node = None
        if positive_node_id and positive_node_id in workflow:
            pos_node = workflow[positive_node_id]
        else:
            # Search by title "Positive" or class CLIPTextEncode
            for node in workflow.values():
                title = node.get("_meta", {}).get("title", "").lower()
                if title == "positive":
                    pos_node = node
                    break
            if not pos_node:
                for node in workflow.values():
                    if node.get("class_type") == "CLIPTextEncode" and "text" in node.get("inputs", {}):
                        # Use the first one found if no title matches
                        pos_node = node
                        break
        
        if pos_node:
            existing_text = pos_node["inputs"].get("text", "")
            # Put the user prompt first to give it more weight
            pos_node["inputs"]["text"] = f"{prompt}, {existing_text}" if existing_text else prompt

        # 2. Find Negative Prompt Node
        neg_node = None
        if negative_node_id and negative_node_id in workflow:
            neg_node = workflow[negative_node_id]
        else:
            for node in workflow.values():
                title = node.get("_meta", {}).get("title", "").lower()
                if title == "negative":
                    neg_node = node
                    break
        
        if neg_node and negative_prompt:
            existing_neg = neg_node["inputs"].get("text", "")
            # Append negative prompt
            neg_node["inputs"]["text"] = f"{existing_neg}, {negative_prompt}" if existing_neg else negative_prompt

        # 3. Find Latent Node (Width/Height)
        latent_node = None
        if latent_node_id and latent_node_id in workflow:
            latent_node = workflow[latent_node_id]
        else:
            for node in workflow.values():
                if node.get("class_type") in ("EmptyLatentImage", "EmptySD3LatentImage"):
                    latent_node = node
                    break
        
        if latent_node:
            latent_node["inputs"]["width"] = width
            latent_node["inputs"]["height"] = height

        # 4. Find and Randomize Seed Nodes (Can be multiple)
        if seed is None:
            seed = settings.COMFY_SEED if settings.COMFY_SEED is not None else random.randrange(0, 2**63)
        
        if seed_node_id and seed_node_id in workflow:
            node = workflow[seed_node_id]
            seed_key = "seed" if "seed" in node["inputs"] else "noise_seed"
            node["inputs"][seed_key] = seed
        else:
            for node in workflow.values():
                if "seed" in node.get("inputs", {}) or "noise_seed" in node.get("inputs", {}):
                    seed_key = "seed" if "seed" in node["inputs"] else "noise_seed"
                    node["inputs"][seed_key] = seed

        # 5. Safety: Ensure we have a SaveImage node instead of just PreviewImage
        # If no SaveImage is found, convert PreviewImage nodes to SaveImage
        has_save = any(n.get("class_type") == "SaveImage" for n in workflow.values())
        if not has_save:
            for node_id, node in workflow.items():
                if node.get("class_type") == "PreviewImage":
                    node["class_type"] = "SaveImage"
                    node["inputs"]["filename_prefix"] = "ComfyUI_Auto"

        # 6. Windows Path Normalization: If ComfyUI is on Windows, replace / with \\ in ckpt_name
        if settings.COMFY_IS_WINDOWS:
            for node in workflow.values():
                if "ckpt_name" in node.get("inputs", {}):
                    current_path = node["inputs"]["ckpt_name"]
                    if isinstance(current_path, str):
                        node["inputs"]["ckpt_name"] = current_path.replace("/", "\\")

        return workflow
