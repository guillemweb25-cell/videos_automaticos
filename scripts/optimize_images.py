import os
import sys
from pathlib import Path
from PIL import Image

def optimize_image(img_path: Path):
    try:
        # Check if already optimized (header check)
        # We can't easily check JPEG in PNG extension without opening
        with Image.open(img_path) as img:
            original_size = img_path.stat().st_size
            
            # Skip if already small (e.g. < 500KB)
            if original_size < 500 * 1024:
                return False

            # Convert to RGB
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Sane max resolution: 1920 on the long side
            max_dim = 1920
            was_resized = False
            if max(img.size) > max_dim:
                scale = max_dim / max(img.size)
                new_size = (int(img.width * scale), int(img.height * scale))
                img = img.resize(new_size, Image.LANCZOS)
                was_resized = True
            
            # Save as JPEG with 90% quality (keeping .png extension)
            img.save(img_path, "JPEG", quality=90, optimize=True)
            
            new_size_bytes = img_path.stat().st_size
            reduction = (original_size - new_size_bytes) / 1024 / 1024
            
            if reduction > 0.1: # Only print if meaningful
                print(f"Optimized {img_path.name}: {original_size/1024/1024:.1f}MB -> {new_size_bytes/1024/1024:.1f}MB (-{reduction:.1f}MB)")
            return True
    except Exception as e:
        print(f"Error optimizing {img_path}: {e}")
        return False

def main():
    cache_dir = Path("cache")
    if not cache_dir.exists():
        print("Cache directory not found.")
        return

    print("Searching for large PNG images in cache...")
    all_pngs = list(cache_dir.glob("**/*.png"))
    print(f"Found {len(all_pngs)} PNG files.")

    count = 0
    for i, img_path in enumerate(all_pngs):
        if i % 10 == 0:
            print(f"Progress: {i}/{len(all_pngs)}")
        if optimize_image(img_path):
            count += 1
    
    print(f"\nDone! Optimized {count} images.")

if __name__ == "__main__":
    main()
