# Video Overlays Integration

- [x] Create endpoint `GET /videos/overlays` to list available overlay files
- [x] Update `POST /{video_id}/render` to accept `overlay_filename: str`
- [x] Modify `RenderingEngine` to concatenate/loop and composite the overlay clip onto the base video
- [x] Update Frontend `VideoCreator.tsx` to include an Overlay dropdown next to the subtitles toggle
- [x] Test frontend integration and the final rendering output
