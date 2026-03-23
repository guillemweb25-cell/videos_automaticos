# Nano Banana Pro Integration Walkthrough

The codebase has been successfully updated to support Leonardo AI's **Nano Banana Pro** model (`gemini-image-2`).

## Changes Made
1. **Added the Model to Video Generation Router:**
   - Updated `backend/app/routers/video_gen.py` to include `"gemini-image-2"` in the `leonardo_models` list. 
   - This ensures it appears in the frontend model selection dropdown for users.

2. **Updated the Leonardo V2 Image Engine Integration:**
   - Modified `backend/app/services/image_engine.py` to correctly route requests for `"gemini-image-2"` through the V2 Leonardo API instead of V1.
   - Enhanced the V2 request payload to inject the `"guidances":["image_reference"]` block whenever an `init_image_id` is supplied. This resolves the previous limitation and enables Image Guidance (essential for "add image" functionality) when using Nano Banana Pro and other V2 models.
3. **Fixed V2 Model Override Bug:**
   - Modified `generate_leonardo_v2` logic in `image_engine.py`. Previously, it incorrectly rejected any `model_id` containing a hyphen (`-`) and forcefully fell back to `gpt-image-1.5`.
   - Changed the validation to explicitly whitelist valid V2 models (including `gemini-image-2`), preventing Nano Banana Pro from being overridden.
4. **Fixed Vertical Video Resolution for FLUX Models (Nano Banana Pro):**
   - Leonardo's Nano Banana Pro strictly enforces hardcoded "Megapixel buckets" instead of calculated aspect ratios.
   - Any mathematically correct vertical resolution (like `1024x1536` or even `768x1344`) was silently rejected by Leonardo's V2 validation logic and padded back to a default `1024x1024` square.
   - Refactored `_normalize_size` to detect `gemini-image-2` and forcibly apply exactly `848x1264` for vertical 2:3 requests, replicating the exact native constraint extracted from the Leonardo web dashboard.

## Verification
- Python syntax for the modified scripts was verified.
- The `gemini-image-2` ID is correctly synchronized with Leonardo AI's documentation for the V2 endpoint.

## Next Steps
You can now create videos or add images directly using Nano Banana Pro. When you restart your backend service, the new model will appear in your frontend!

---

## Video Overlays: implementation 📼
Implemented a fully dynamic video overlay integration.
- **Dynamic File Loading**: The `/videos/overlays` endpoint reads `.mp4`, `.mov`, and `.webm` files directly from the `/overlay` mapped volume directory.
- **Chroma Key Compositing**: Utilizing MoviePy's `vfx.mask_color` effect targeting `#000000` pitch black, allowing white film grain and dust to layer over the slides seamlessly without hiding them.
- **UI Integration**: Included new hooks and components within the React application to display the overlay selector during video creation.
