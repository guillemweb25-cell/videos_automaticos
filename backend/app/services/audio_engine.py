import base64
import json
import time
import requests
from pathlib import Path
from typing import List, Optional
from pydub import AudioSegment
from mutagen.mp3 import MP3
from moviepy.editor import AudioFileClip
from app.config import get_settings
from app.services.elevenlabs_voices import ELEVEN_VOICES

# TikTok voices available
VOICES = [
    "es_mx_002", "es_002", "en_us_001", "en_us_006", "en_us_g08_sonya",
    "en_us_ghostface", "en_us_chewbacca", "en_us_c3po", "en_us_stitch", "en_us_stormtrooper", "en_us_rocket",
    "en_au_001", "en_au_002", "en_uk_001", "en_uk_003", "en_us_002", "en_us_007", "en_us_009", "en_us_010",
    "fr_001", "fr_002", "de_001", "de_002", "br_001", "br_003", "br_004", "br_005",
    "id_001", "jp_001", "jp_003", "jp_005", "jp_006", "kr_002", "kr_003", "kr_004",
    "en_female_f08_salut_damour", "en_male_m03_lobby", "en_female_f08_warmy_breeze", "en_male_m03_sunshine_soon",
    "en_male_narration", "en_male_funny", "en_female_emotional",
]

ENDPOINTS = [
    "https://tiktok-tts.weilnet.workers.dev/api/generation",
    "https://tiktoktts.com/api/tiktok-tts",
]

class AudioEngine:
    @staticmethod
    def get_duration(p: Path) -> float:
        """Returns duration in seconds using mutagen or moviepy fallback."""
        try:
            return float(MP3(str(p)).info.length)
        except Exception:
            try:
                with AudioFileClip(str(p)) as clip:
                    return float(clip.duration)
            except Exception as e:
                raise RuntimeError(f"Could not read duration from {p}: {e}")

    @staticmethod
    def synthesize_tiktok(text: str, voice: str, out_path: Path, gap_ms: int = 0) -> None:
        """Synthesizes text using TikTok TTS."""
        if not text.strip():
            raise ValueError("Empty text for TTS")
        
        parts = AudioEngine._split_text(text, 299)
        tmp_dir = out_path.parent / "__tts_tmp__"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        
        chunk_paths = []
        try:
            for i, part in enumerate(parts):
                b64 = AudioEngine._generate_chunk_with_retry(part, voice)
                chunk_path = tmp_dir / f"{out_path.stem}_{i:03d}.mp3"
                chunk_path.write_bytes(base64.b64decode(b64))
                chunk_paths.append(chunk_path)
                time.sleep(0.5) # throttle
            
            AudioEngine._concat_chunks(chunk_paths, out_path, gap_ms)
        finally:
            for p in chunk_paths:
                p.unlink(missing_ok=True)
            if tmp_dir.exists():
                try: tmp_dir.rmdir()
                except: pass

    @staticmethod
    def synthesize_elevenlabs(text: str, voice: str, out_path: Path, api_key: Optional[str] = None) -> None:
        """Synthesizes text using ElevenLabs TTS."""
        if not text.strip():
            raise ValueError("Empty text for TTS")
        
        settings = get_settings()
        key = api_key or settings.ELEVEN_API_KEY
        if not key:
            raise RuntimeError("ELEVEN_API_KEY not configured")
            
        voice_id = ELEVEN_VOICES.get(voice, voice)
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.85,
                "similarity_boost": 0.95,
            }
        }
        headers = {
            "xi-api-key": key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }
        
        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            raise RuntimeError(f"ElevenLabs error {resp.status_code}: {resp.text}")
            
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(resp.content)

    @staticmethod
    def _split_text(s: str, limit: int) -> List[str]:
        parts = []
        while s:
            if len(s) <= limit:
                parts.append(s)
                break
            cut = s.rfind(" ", 0, limit)
            if cut < 0: cut = limit
            parts.append(s[:cut].strip())
            s = s[cut:].lstrip()
        return parts

    @staticmethod
    def _generate_chunk_with_retry(text: str, voice: str) -> str:
        last_err = None
        for endpoint in ENDPOINTS:
            try:
                r = requests.post(endpoint, json={"text": text, "voice": voice}, timeout=30)
                if not r.ok:
                    continue
                data = r.json()
                for key in ["data", "audio", "vocal", "result"]:
                    if key in data and isinstance(data[key], str):
                        v = data[key]
                        return v.split("base64,")[-1] if "base64," in v else v
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"TikTok TTS service unavailable or invalid response. Last error: {last_err}")

    @staticmethod
    def _concat_chunks(paths: List[Path], out_path: Path, gap_ms: int) -> None:
        final = AudioSegment.silent(duration=0)
        for p in paths:
            seg = AudioSegment.from_file(p, format="mp3")
            final += seg
            if gap_ms > 0:
                final += AudioSegment.silent(duration=gap_ms)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        final.export(out_path, format="mp3")
