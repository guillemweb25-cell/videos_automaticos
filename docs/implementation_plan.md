# Video Overlays Feature

## User Review Required
> [!IMPORTANT]
> The overlay feature requires specific blending if the background is black. Since standard MP4 files do not contain an alpha channel (transparency), most retro overlays use a black background. We will use a chroma-key filter (`vfx.mask_color` targeting black `#000000`) or standard opacity to make it see-through. Does your `overlay_retro_01.mp4` have a black background, or a green screen?

## Proposed Changes

### Backend Component

#### [MODIFY] [video_gen.py](file:///home/guillem/code/videos_automaticos/backend/app/routers/video_gen.py)
- Create a new endpoint `GET /videos/overlays` that reads the `/home/guillem/code/videos_automaticos/overlay` directory and returns a list of `.mp4` and `.mov` filenames.
- Update `render_video` function signature to accept an optional query parameter: `overlay: Optional[str] = None`.
- Pass this overlay filename down to `RenderingEngine.render_simple_slideshow`.

#### [MODIFY] [rendering_engine.py](file:///home/guillem/code/videos_automaticos/backend/app/services/rendering_engine.py)
- Update `render_simple_slideshow` to accept `overlay_filename`.
- If present, instantiate `VideoFileClip(overlay_filename)`.
- Resize it to the output resolution `out_size`.
- Loop the clip infinitely to match the total duration `t_cursor` using `vfx.loop`.
- Apply a transparency effect (either `mask_color` for black backgrounds, or a soft opacity blend) so the main video is visible through it.
- Append it to the `CompositeVideoClip` layers list before rendering audio.

### Frontend Component

#### [MODIFY] [api.ts](file:///home/guillem/code/videos_automaticos/frontend/src/api.ts)
- Add a new service method `getOverlays()` that queries `/videos/overlays`.
- Update the `renderVideo` signature to include `overlay?: string`.

#### [MODIFY] [VideoCreator.tsx](file:///home/guillem/code/videos_automaticos/frontend/src/components/VideoCreator.tsx)
- Load the list of overlays via `useEffect`.
- Next to the "Add Subtitles" toggle switch, add a styled `<select>` element.
- Options should be "None (Sin overlay)" and then the filenames.
- Pass the selected string to `api.renderVideo` upon clicking Render.

## Verification Plan
1. Launch the modified frontend and visit a generated item.
2. Select `overlay_retro_01.mp4` from the new dropdown.
3. Click "Render Video" and wait for MoviePy processing.
4. Verify the final `.mp4` has the film damage visually burning on top of the images, maintaining synchronized subtitles.
