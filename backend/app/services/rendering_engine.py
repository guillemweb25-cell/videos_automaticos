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
    def apply_qr_overlay(
        video_path: Path,
        out_size: Tuple[int, int],
        affiliate_url: str,
        affiliate_label: Optional[str] = None,
        on_secs: int = 30,
        period_secs: int = 60,
    ) -> Path:
        """Compone un panel con un código QR (+ etiqueta) y lo superpone en la
        esquina SUPERIOR DERECHA del vídeo, visible los primeros `on_secs`
        segundos de cada `period_secs` (por defecto 30s sí / 30s no). El QR va
        arriba para no tapar los subtítulos (que van abajo). Modifica el vídeo
        in situ (deja el resultado en `video_path`).
        """
        if not affiliate_url or not video_path.exists():
            return video_path
        try:
            import qrcode
        except Exception as e:
            print(f"[qr] librería 'qrcode' no disponible ({e}); se omite el QR", flush=True)
            return video_path

        from PIL import ImageDraw, ImageFont
        W, H = out_size

        # 1) QR (negro sobre blanco, con quiet-zone). Tamaño ~18% del ancho.
        qr = qrcode.QRCode(border=2, box_size=10,
                           error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(affiliate_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        qr_side = max(140, int(W * 0.18))
        qr_img = qr_img.resize((qr_side, qr_side), Image.NEAREST)

        # 2) Etiqueta (texto sobre el QR). Se quitan emojis/símbolos que la fuente
        #    no sabe dibujar (saldrían como cuadros). Poppins tiene minúsculas+dígitos.
        # Permite que el usuario escriba "\n" literal en el campo de texto para
        # forzar un salto de línea en la etiqueta.
        # La etiqueta del QR es fija; avisa de que el enlace clicable está en la
        # descripción (útil para quien ve en móvil y no puede escanear). Si algún día
        # se quiere por canal, basta con pasar affiliate_label.
        raw_label = (affiliate_label or "").replace("\\n", "\n").strip() or "Compra el libro\nLink en la descripción"
        label = "".join(ch for ch in raw_label if ord(ch) < 0x2500 or ch == "\n")
        fonts_dir = Path(__file__).parent.parent / "fonts"
        _font_file = None
        for fp in (fonts_dir / "Poppins-Bold.ttf",
                   Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")):
            if fp.exists():
                try:
                    ImageFont.truetype(str(fp), 20); _font_file = str(fp); break
                except Exception:
                    continue

        def _load_font(sz):
            if _font_file:
                try:
                    return ImageFont.truetype(_font_file, sz)
                except Exception:
                    pass
            return ImageFont.load_default()

        pad = int(qr_side * 0.10)
        _md = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        # La etiqueta puede ser más ancha que el QR (hasta un tope) para no cortar
        # URLs. Palabras más largas que el ancho se parten por caracteres.
        text_w_cap = max(qr_side, int(W * 0.30))

        def _wrap(font, maxw):
            out: list[str] = []
            for para in label.split("\n"):
                cur = ""
                for word in para.split(" "):
                    # Parte palabras que por sí solas no caben (p.ej. una URL larga).
                    while _md.textlength(word, font=font) > maxw and len(word) > 1:
                        lo, hi = 1, len(word)
                        while lo < hi:
                            mid = (lo + hi + 1) // 2
                            if _md.textlength(word[:mid], font=font) <= maxw:
                                lo = mid
                            else:
                                hi = mid - 1
                        if cur:
                            out.append(cur); cur = ""
                        out.append(word[:lo]); word = word[lo:]
                    t = (cur + " " + word).strip()
                    if not cur or _md.textlength(t, font=font) <= maxw:
                        cur = t
                    else:
                        out.append(cur); cur = word
                if cur:
                    out.append(cur)
            return out

        # Elige tamaño de fuente: encoge si salen demasiadas líneas (para no crecer
        # el panel en vertical). El ancho nunca se corta gracias a _wrap.
        font_size = max(18, int(qr_side * 0.14))
        font = _load_font(font_size)
        lines: list[str] = _wrap(font, text_w_cap) if label else []
        while label and len(lines) > 3 and font_size > 14:
            font_size -= 2
            font = _load_font(font_size)
            lines = _wrap(font, text_w_cap)

        line_gap = int(font_size * 0.25)
        asc = font.getbbox("Ay")[3]
        line_h = asc + line_gap
        text_block_h = (line_h * len(lines) + pad) if lines else 0

        widest = int(max((_md.textlength(l, font=font) for l in lines), default=0))
        panel_w = max(qr_side, widest) + pad * 2
        panel_h = qr_side + pad * 2 + text_block_h
        # Panel oscuro semitransparente con esquinas redondeadas.
        panel = Image.new("RGBA", (panel_w, panel_h), (0, 0, 0, 0))
        pd = ImageDraw.Draw(panel)
        radius = int(pad * 1.2)
        pd.rounded_rectangle([0, 0, panel_w - 1, panel_h - 1], radius=radius,
                             fill=(0, 0, 0, 170))
        # Etiqueta arriba, centrada.
        yy = pad // 2
        for ln in lines:
            lw = _md.textlength(ln, font=font)
            pd.text(((panel_w - lw) // 2, yy), ln, font=font, fill=(255, 255, 255, 255),
                    stroke_width=max(1, font_size // 12), stroke_fill=(0, 0, 0, 255))
            yy += line_h
        # QR debajo del texto, centrado, sobre una tarjeta blanca (contraste + escaneable).
        qr_y = pad + text_block_h
        card = Image.new("RGBA", (qr_side + pad, qr_side + pad), (255, 255, 255, 255))
        card.paste(qr_img, (pad // 2, pad // 2))
        panel.alpha_composite(card, ((panel_w - card.width) // 2, qr_y - pad // 2))

        panel_path = video_path.parent / "qr_overlay.png"
        panel.save(panel_path)

        # 3) Overlay ffmpeg temporizado, esquina superior derecha con margen.
        margin = int(W * 0.03)
        enable = f"lt(mod(t\\,{period_secs})\\,{on_secs})"
        tmp = video_path.parent / "__qr_tmp__.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(panel_path),
            "-filter_complex",
            f"[0:v][1:v]overlay=W-w-{margin}:{margin}:enable='{enable}'[v]",
            "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(tmp),
        ]
        print(f"[qr] Superponiendo QR ({on_secs}s/{period_secs}s) -> {affiliate_url}", flush=True)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[qr] ffmpeg falló, se deja el vídeo sin QR: {result.stderr[-600:]}", flush=True)
            tmp.unlink(missing_ok=True)
            return video_path
        video_path.unlink(missing_ok=True)
        tmp.rename(video_path)
        print("[qr] QR aplicado correctamente.", flush=True)
        return video_path

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

        progress_file = out_path.parent / "render_progress.txt"

        from proglog import ProgressBarLogger
        class SimpleProgressLogger(ProgressBarLogger):
            """MoviePy progress only covers the write_videofile phase.
            We cap reported percentage at 90 so the remaining 10 is reserved
            for post-process (overlay/loudnorm) and subtitle burn-in stages
            that come AFTER MoviePy finishes. The endpoint writes 100 only
            after everything is done.
            """
            def __init__(self, progress_file_path):
                super().__init__()
                self.last_pct = -1
                self.progress_file_path = progress_file_path
            def callback(self, **kwargs):
                bars = self.state.get('bars', {})
                if not bars: return

                bar = next(iter(bars.values()))
                index = bar.get('index', 0)
                total = bar.get('total', 1)
                if total > 0:
                    raw = int(index * 100 / total)
                    pct = min(90, int(raw * 0.9))  # scale 0-100 → 0-90
                    if pct > self.last_pct:
                        print(f"[render] Progress: {pct}% (write_videofile)", flush=True)
                        self.last_pct = pct
                        try:
                            self.progress_file_path.write_text(str(pct))
                        except Exception:
                            pass

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
            logger=SimpleProgressLogger(progress_file),
            temp_audiofile=str(out_path.parent / "__tmp_audio__.m4a"),
            remove_temp=True,
        )
        print(f"[render] MoviePy render finished. Proceeding to post-process...", flush=True)

        # ── Post-process: Apply Overlay (if any) + Normalize loudness with ffmpeg ──
        print("[render] Post-processing (Overlay + Loudnorm)...", flush=True)
        try:
            progress_file.write_text("92")
        except Exception:
            pass
        
        # Base command for loudnorm
        norm_filter = "loudnorm=I=-14:TP=-1:LRA=11"
        
        if overlay_video_path and overlay_video_path.exists():
            # Use FFmpeg filter_complex to key out black and overlay. This is 100x faster than MoviePy mask_color.
            # IMPORTANT: -stream_loop -1 on the overlay makes it loop infinitely. Without it,
            # if the overlay is shorter than the main video, "shortest=1" would truncate the
            # ENTIRE output to the overlay's length (bug we hit).
            ov_cmd = [
                "ffmpeg", "-y",
                "-i", str(tmp_render),
                "-stream_loop", "-1", "-i", str(overlay_video_path),
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

        # Post-process complete. Subtitles (if requested) come after this in video_gen.
        try:
            progress_file.write_text("96")
        except Exception:
            pass

        print(f"[render] Done! {out_path} ({out_path.stat().st_size / 1024 / 1024:.1f} MB)", flush=True)
