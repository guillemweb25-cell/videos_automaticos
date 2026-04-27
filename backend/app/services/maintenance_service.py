import os
import time
import shutil
from pathlib import Path
from PIL import Image
from typing import Dict, Any

class MaintenanceService:
    @staticmethod
    def cleanup_cache(days: int = 15) -> Dict[str, Any]:
        """
        Performs cache maintenance:
        1. Deletes MP4 files in 'output' folders older than X days.
        2. Optimizes large images (>400KB) to JPEG.
        """
        # Inside docker, the path is relative to /app or absolute
        base_dir = Path("/app")
        cache_dir = base_dir / "cache"
        
        if not cache_dir.exists():
            # Fallback for local dev
            cache_dir = Path("cache")
            if not cache_dir.exists():
                return {"error": "Cache directory not found", "deleted_videos": 0, "optimized_images": 0}

        # 1. Video Cleanup
        now = time.time()
        cutoff = now - (days * 24 * 60 * 60)
        deleted_count = 0
        freed_space = 0

        for mp4_path in cache_dir.glob("**/output/*.mp4"):
            try:
                mtime = mp4_path.stat().st_mtime
                if mtime < cutoff:
                    size = mp4_path.stat().st_size
                    mp4_path.unlink()
                    deleted_count += 1
                    freed_space += size
            except:
                pass

        # 2. Image Optimization
        optimized_count = 0
        total_reduction = 0
        
        for ext in ["**/*.png", "**/*.jpg", "**/*.jpeg"]:
            for img_path in cache_dir.glob(ext):
                try:
                    original_size = img_path.stat().st_size
                    if original_size < 400 * 1024:
                        continue

                    with Image.open(img_path) as img:
                        # Convert to RGB
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                        
                        # Max resolution
                        max_dim = 1920
                        if max(img.size) > max_dim:
                            scale = max_dim / max(img.size)
                            new_size = (int(img.width * scale), int(img.height * scale))
                            img = img.resize(new_size, Image.LANCZOS)
                        
                        img.save(img_path, "JPEG", quality=85, optimize=True)
                        
                        new_size_bytes = img_path.stat().st_size
                        total_reduction += (original_size - new_size_bytes)
                        optimized_count += 1
                except:
                    pass

        return {
            "deleted_videos": deleted_count,
            "freed_space_mb": round(freed_space / 1024 / 1024, 2),
            "optimized_images": optimized_count,
            "image_reduction_mb": round(total_reduction / 1024 / 1024, 2),
            "status": "success"
        }
