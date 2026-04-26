import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from moviepy.editor import (
    VideoClip, ImageClip, AudioFileClip, AudioClip, 
    CompositeVideoClip, concatenate_audioclips
)
from moviepy.audio.AudioClip import CompositeAudioClip
from PIL import Image

# Pillow 10+ compatibility patch for MoviePy 1.0.3
if not hasattr(Image, 'ANTIALIAS'):
    try:
        Image.ANTIALIAS = Image.Resampling.LANCZOS
    except AttributeError:
        Image.ANTIALIAS = getattr(Image, 'LANCZOS', 1)

import subprocess

class RenderingEngine:
    @staticmethod
    def _qtime(x: float, fps: int) -> float:
        if fps <= 0: return x
        frame = 1.0 / float(fps)
        return round(x / frame) * frame

    @staticmethod
    def make_kenburns_clip(
        img_path: Path,
        duration: float,
        out_size: Tuple[int, int],
        z0: float = 1.0,
        z1: float = 1.15,
        mode: str = "linear"
    ) -> VideoClip:
        W, H = out_size
        
        if img_path.suffix.lower() == '.mp4':
            from moviepy.video.io.VideoFileClip import VideoFileClip
            
            v_clip = VideoFileClip(str(img_path))
            
            w, h = v_clip.size
            base_scale = max(W/w, H/h)
            
            def center_crop_fl(get_frame, t):
                # t follows the duration we set on the clip
                # clamp t for source video
                safe_t = min(t, v_clip.duration - 0.05) if v_clip.duration > 0 else 0
                frame = get_frame(safe_t)
                
                # Apply Ken Burns zoom logic
                u = t / max(duration, 0.001)
                if mode == "pingpong":
                    z = z0 + (z1 - z0) * (u*2 if u <= 0.5 else (1-u)*2)
                else:
                    z = z0 + (z1 - z0) * u
                
                scale = base_scale * z
                
                img = Image.fromarray(frame).resize((int(w * scale), int(h * scale)), Image.BILINEAR)
                arr = np.array(img)
                ch, cw = arr.shape[:2]
                x1 = max(0, (cw - W) // 2)
                y1 = max(0, (ch - H) // 2)
                return arr[y1:y1+H, x1:x1+W]

            final_clip = v_clip.subclip(0, min(duration, v_clip.duration)).set_duration(duration).fl(center_crop_fl)
            
            # Use original audio if present
            if v_clip.audio:
                # Cut original audio if duration < clip length. 
                # If duration > clip length, it will end naturally.
                final_clip = final_clip.set_audio(v_clip.audio.subclip(0, min(duration, v_clip.duration)).set_duration(duration))
                
            return final_clip

        base = Image.open(img_path).convert("RGB")
        W0, H0 = base.size
        base_scale = max(W / W0, H / H0)

        def make_frame(t: float):
            u = t / max(duration, 0.001)
            if mode == "pingpong":
                z = z0 + (z1 - z0) * (u*2 if u <= 0.5 else (1-u)*2)
            else:
                z = z0 + (z1 - z0) * u
            
            scale = base_scale * z
            nw, nh = int(W0 * scale), int(H0 * scale)
            
            # Using BILINEAR instead of LANCZOS for a huge speed boost during per-frame resizing
            img_resized = base.resize((nw, nh), Image.BILINEAR)
            arr = np.array(img_resized)
            
            x1 = (nw - W) // 2
            y1 = (nh - H) // 2
            return arr[y1:y1+H, x1:x1+W]

        return VideoClip(make_frame, duration=duration)

    @staticmethod
    def render_simple_slideshow(
        image_paths: List[Path],
        durations: List[float],
        audio_paths: List[Path],
        out_path: Path,
        out_size: Tuple[int, int] = (1080, 1920), 
        fps: int = 24,
        bg_music_path: Optional[Path] = None,
        overlay_video_path: Optional[Path] = None,
        bg_music_volume: float = 0.06,
        voice_volume: float = 1.6
    ):
        clips = []
        t_cursor = 0.0
        
        # 1. Main visual clips
        for i, (img_p, dur) in enumerate(zip(image_paths, durations)):
            clip = RenderingEngine.make_kenburns_clip(
                img_path=img_p,
                duration=dur,
                out_size=out_size
            ).set_start(t_cursor)
            clips.append(clip)
            t_cursor += dur

        # 2. Check for thumbnail
        thumbnail_path = out_path.parent / "thumbnail.png"
        if thumbnail_path.exists():
            thumb_dur = 3.0
            thumb_clip = RenderingEngine.make_kenburns_clip(
                img_path=thumbnail_path,
                duration=thumb_dur,
                out_size=out_size,
                z0=1.0, z1=1.05
            ).set_start(t_cursor).fadein(0.5)
            clips.append(thumb_clip)
            t_cursor += thumb_dur

        # 3. Check for logo in channel directory
        channel_dir = out_path.parent.parent.parent
        logo_path = channel_dir / "logo.png"
        if logo_path.exists():
            logo_dur = 2.5
            logo_clip = ImageClip(str(logo_path)) \
                .set_duration(logo_dur) \
                .resize(width=out_size[0] * 0.7) \
                .set_position("center") \
                .on_color(size=out_size, color=(0,0,0), pos="center") \
                .set_start(t_cursor) \
                .fadein(0.5)
            clips.append(logo_clip)
            t_cursor += logo_dur
        
        if clips:
            clips[-1] = clips[-1].fadeout(1.0)
            
        video = CompositeVideoClip(clips, size=out_size).set_duration(t_cursor)
        
        video = CompositeVideoClip(clips, size=out_size).set_duration(t_cursor)
        
        # NOTE: Overlay and Audio normalization are handled in FFmpeg post-process for maximum speed.
        # MoviePy's mask_color is too slow for 1080p+ renders.
        
        # ── Audio: boost voice + duck music ──
        audio_clips = [AudioFileClip(str(p)) for p in audio_paths]
        voiceover = None
        if audio_clips:
            voiceover = concatenate_audioclips(audio_clips)
            if voice_volume != 1.0:
                voiceover = voiceover.volumex(voice_volume)
        
        final_audio = voiceover
        if bg_music_path and bg_music_path.exists():
            bg_music = AudioFileClip(str(bg_music_path)).volumex(bg_music_volume)
            if bg_music.duration < t_cursor:
                n_loops = int(np.ceil(t_cursor / bg_music.duration))
                bg_music = concatenate_audioclips([bg_music] * n_loops)
            bg_music = bg_music.subclip(0, t_cursor).audio_fadeout(2.0)
            if voiceover:
                final_audio = CompositeAudioClip([voiceover, bg_music])
            else:
                final_audio = bg_music
        
        if final_audio:
            video = video.set_audio(final_audio)

        # ── Render with moviepy (verbose=True for Docker-visible progress) ──
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_render = out_path.parent / "__tmp_render__.mp4"
        stats_path = out_path.parent / "render_stats.txt"

        import datetime
        start_time = datetime.datetime.now()
        with open(stats_path, "a") as f:
            f.write(f"\n--- RENDER START: {start_time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")

        from proglog import ProgressBarLogger
        class SimpleProgressLogger(ProgressBarLogger):
            def __init__(self):
                super().__init__()
                self.last_pct = -1
            def callback(self, **kwargs):
                # The bar we care about is usually named 'chunk' or 't' in MoviePy
                bars = self.state.get('bars', {})
                if not bars: return
                
                # Get the first active bar
                bar = next(iter(bars.values()))
                index = bar.get('index', 0)
                total = bar.get('total', 1)
                if total > 0:
                    pct = int(index * 100 / total)
                    if pct > self.last_pct:
                        print(f"[render] Progress: {pct}%", flush=True)
                        self.last_pct = pct

        print(f"[render] Writing video to {out_path} ({t_cursor:.1f}s, {fps}fps) ...", flush=True)
        video.write_videofile(
            str(tmp_render),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            threads=8,
            preset="superfast",
            ffmpeg_params=[
                "-crf", "22",
                "-pix_fmt", "yuv420p",
                "-tune", "stillimage",
                "-movflags", "+faststart",
                "-g", str(max(1, fps * 2)),
            ],
            verbose=False,
            logger=SimpleProgressLogger(),
            temp_audiofile=str(out_path.parent / "__tmp_audio__.m4a"),
            remove_temp=True,
        )
        print(f"[render] MoviePy render finished. Proceeding to post-process...", flush=True)

        # ── Post-process: Apply Overlay (if any) + Normalize loudness with ffmpeg ──
        print("[render] Post-processing (Overlay + Loudnorm)...", flush=True)
        
        # Base command for loudnorm
        norm_filter = "loudnorm=I=-14:TP=-1:LRA=11"
        
        if overlay_video_path and overlay_video_path.exists():
            # Use FFmpeg filter_complex to key out black and overlay. This is 100x faster than MoviePy mask_color.
            # [1:v]colorkey=black:0.1:0.1[ck];[0:v][ck]overlay=shortest=1[outv]
            # We also scale the overlay to match output size if needed.
            ov_cmd = [
                "ffmpeg", "-y",
                "-i", str(tmp_render),
                "-i", str(overlay_video_path),
                "-filter_complex", 
                f"[1:v]scale={out_size[0]}:{out_size[1]},colorkey=black:0.3:0.1[ovl];"
                f"[0:v][ovl]overlay=shortest=1[v_out];"
                f"[0:a]{norm_filter}[a_out]",
                "-map", "[v_out]",
                "-map", "[a_out]",
                "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                str(out_path),
            ]
        else:
            ov_cmd = [
                "ffmpeg", "-y",
                "-i", str(tmp_render),
                "-c:v", "copy",
                "-af", norm_filter,
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                str(out_path),
            ]
            
            
        import subprocess
        # Run without capture_output to see ffmpeg progress in logs
        result = subprocess.run(ov_cmd)
        if result.returncode != 0:
            print(f"[render] Post-process error (ffmpeg failed)", flush=True)
            # Fallback: just rename tmp to final
            tmp_render.rename(out_path)
        else:
            tmp_render.unlink(missing_ok=True)

        end_time = datetime.datetime.now()
        total_time = end_time - start_time
        with open(stats_path, "a") as f:
            f.write(f"--- RENDER END: {end_time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
            f.write(f"--- TOTAL DURATION: {total_time} ---\n")

        print(f"[render] Done! {out_path} ({out_path.stat().st_size / 1024 / 1024:.1f} MB)", flush=True)
