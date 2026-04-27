import os
import time
from pathlib import Path
from PIL import Image

def optimize_image(img_path: Path):
    """Compresses large images to optimized JPEG format to save space."""
    try:
        original_size = img_path.stat().st_size
        
        # Skip if already small (e.g. < 400KB)
        if original_size < 400 * 1024:
            return False

        with Image.open(img_path) as img:
            # Convert to RGB (remove alpha channel if exists)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Sane max resolution: 1920 on the long side
            max_dim = 1920
            if max(img.size) > max_dim:
                scale = max_dim / max(img.size)
                new_size = (int(img.width * scale), int(img.height * scale))
                img = img.resize(new_size, Image.LANCZOS)
            
            # Save as JPEG with 85% quality
            # NOTE: We keep the original filename even if it ends in .png to avoid breaking database references
            img.save(img_path, "JPEG", quality=85, optimize=True)
            
            new_size_bytes = img_path.stat().st_size
            reduction = (original_size - new_size_bytes) / 1024 / 1024
            
            if reduction > 0.05:
                print(f"[OPT] {img_path.relative_to(Path.cwd())}: {original_size/1024/1024:.1f}MB -> {new_size_bytes/1024/1024:.1f}MB (-{reduction:.1f}MB)")
            return True
    except Exception as e:
        # print(f"Error optimizing {img_path}: {e}")
        return False

def cleanup_old_videos(cache_dir: Path, days: int = 15):
    """Deletes MP4 files in 'output' folders that are older than specified days."""
    now = time.time()
    cutoff = now - (days * 24 * 60 * 60)
    deleted_count = 0
    freed_space = 0

    print(f"--- Cleaning up MP4s older than {days} days ---")
    
    # We specifically look for .mp4 files inside 'output' directories
    for mp4_path in cache_dir.glob("**/output/*.mp4"):
        try:
            mtime = mp4_path.stat().st_mtime
            if mtime < cutoff:
                size = mp4_path.stat().st_size
                mp4_path.unlink()
                deleted_count += 1
                freed_space += size
                print(f"[DEL] Removed old video: {mp4_path.relative_to(cache_dir)} ({size/1024/1024:.1f} MB)")
        except Exception as e:
            print(f"[ERR] Could not delete {mp4_path}: {e}")
            
    return deleted_count, freed_space

def main():
    base_dir = Path.cwd()
    cache_dir = base_dir / "cache"
    
    if not cache_dir.exists():
        print("Cache directory not found.")
        return

    # 1. Cleanup old videos
    del_count, space_mb = cleanup_old_videos(cache_dir, days=15)
    print(f"\nFinished video cleanup: Deleted {del_count} videos, freed {space_mb/1024/1024:.1f} MB.\n")

    # 2. Optimize images
    print("--- Optimizing large images in cache ---")
    img_count = 0
    # Search for png and jpg
    for ext in ["**/*.png", "**/*.jpg", "**/*.jpeg"]:
        for img_path in cache_dir.glob(ext):
            if optimize_image(img_path):
                img_count += 1
                
    print(f"\nFinished image optimization: Compressed {img_count} images.")

if __name__ == "__main__":
    main()
