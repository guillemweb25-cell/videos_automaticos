import numpy as np
from pathlib import Path
from typing import List, Tuple, Optional
from moviepy.editor import (
    VideoClip, ImageClip, AudioFileClip, AudioClip, 
    CompositeVideoClip, concatenate_audioclips
)
from moviepy.audio.AudioClip import CompositeAudioClip
from PIL import Image
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
            
            # Simple resize and crop
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
        bg_music_volume: float = 0.15
    ):
        clips = []
        t_cursor = 0.0
        
        # 1. Main visual clips
        for i, (img_p, dur) in enumerate(zip(image_paths, durations)):
            is_last = (i == len(image_paths) - 1)
            clip = RenderingEngine.make_kenburns_clip(
                img_path=img_p,
                duration=dur,
                out_size=out_size
            ).set_start(t_cursor)
            
            # Fade out the very last image clip if no logo follows
            # We will handle logo separately below
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
                z0=1.0, 
                z1=1.05
            ).set_start(t_cursor).fadein(0.5)
            clips.append(thumb_clip)
            t_cursor += thumb_dur

        # 3. Check for logo in channel directory
        # out_path is something like .../cache/0001-channel/YYYY-MM-DD-title/output/final_video.mp4
        # Channel dir is out_path.parent.parent.parent
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
        
        # Add fade out to the very last clip in the sequence
        if clips:
            clips[-1] = clips[-1].fadeout(1.0)
            
        video = CompositeVideoClip(clips, size=out_size).set_duration(t_cursor)
        
        # Audio assembly: Voiceover
        audio_clips = [AudioFileClip(str(p)) for p in audio_paths]
        voiceover = None
        if audio_clips:
            voiceover = concatenate_audioclips(audio_clips)
        
        # Background Music
        final_audio = voiceover
        if bg_music_path and bg_music_path.exists():
            bg_music = AudioFileClip(str(bg_music_path)).volumex(bg_music_volume)
            
            # Loop background music if shorter than video
            if bg_music.duration < t_cursor:
                n_loops = int(np.ceil(t_cursor / bg_music.duration))
                bg_music = concatenate_audioclips([bg_music] * n_loops)
            
            # Trim and add fadeout
            bg_music = bg_music.subclip(0, t_cursor).audio_fadeout(2.0)
            
            if voiceover:
                # Ensure voiceover is at least as long as video (padding with silence if needed)
                # but usually it's shorter. CompositeAudioClip handles different lengths.
                final_audio = CompositeAudioClip([voiceover, bg_music])
            else:
                final_audio = bg_music
        
        if final_audio:
            video = video.set_audio(final_audio)
            
        out_path.parent.mkdir(parents=True, exist_ok=True)
        video.write_videofile(
            str(out_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac",
            temp_audiofile=str(out_path.with_suffix(".m4a")),
            remove_temp=True,
            threads=4,
            logger=None
        )
