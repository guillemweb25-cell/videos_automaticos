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
            
            img_resized = base.resize((nw, nh), Image.LANCZOS)
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
        
        # 4. Apply Overlay
        if overlay_video_path and overlay_video_path.exists():
            from moviepy.video.io.VideoFileClip import VideoFileClip
            from moviepy.video.fx.all import mask_color, loop, resize
            
            overlay_clip = VideoFileClip(str(overlay_video_path))
            
            # Loop overhead handling
            if overlay_clip.duration < t_cursor:
                overlay_clip = overlay_clip.fx(loop, duration=t_cursor)
            else:
                overlay_clip = overlay_clip.subclip(0, t_cursor)
            
            # Apply alpha keying for pitch black background #000000 
            # thr=30 grabs near-blacks. Lower opacity to make artifacts less blinding.
            overlay_clip = (
                overlay_clip
                .fx(resize, newsize=out_size)
                .fx(mask_color, color=[0, 0, 0], thr=30, s=5)
                .set_opacity(0.65)
                .set_start(0)
            )
            video = CompositeVideoClip([video, overlay_clip], size=out_size).set_duration(t_cursor)
        
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

        print(f"[render] Writing video to {out_path} ({t_cursor:.1f}s, {fps}fps) ...", flush=True)
        video.write_videofile(
            str(tmp_render),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            threads=4,
            preset="medium",
            ffmpeg_params=[
                "-crf", "22",
                "-pix_fmt", "yuv420p",
                "-tune", "stillimage",
                "-movflags", "+faststart",
                "-g", str(max(1, fps * 2)),
            ],
            verbose=True,
            temp_audiofile=str(out_path.parent / "__tmp_audio__.m4a"),
            remove_temp=True,
        )

        # ── Post-process: normalize loudness with ffmpeg ──
        print("[render] Normalizing audio loudness...", flush=True)
        norm_cmd = [
            "ffmpeg", "-y",
            "-i", str(tmp_render),
            "-c:v", "copy",
            "-af", "loudnorm=I=-14:TP=-1:LRA=11",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(out_path),
        ]
        result = subprocess.run(norm_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[render] loudnorm warning: {result.stderr[-500:]}", flush=True)
            # Fallback: just rename tmp to final
            tmp_render.rename(out_path)
        else:
            tmp_render.unlink(missing_ok=True)

        print(f"[render] Done! {out_path} ({out_path.stat().st_size / 1024 / 1024:.1f} MB)", flush=True)
