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
        
        parts = AudioEngine._split_text(text, 200)
        tmp_dir = out_path.parent / "__tts_tmp__"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        
        chunk_paths = []
        try:
            for i, part in enumerate(parts):
                print(f"Generating TikTok chunk {i+1}/{len(parts)} ({len(part)} chars)...")
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
    def synthesize_local_xtts(text: str, voice_id: str, out_path: Path, gap_ms: int = 0) -> None:
        """Synthesizes text using Local XTTS API."""
        if not text.strip():
            raise ValueError("Empty text for TTS")
            
        settings = get_settings()
        # Fallback to localhost if not set in .env
        url = getattr(settings, "LOCAL_TTS_URL", "http://192.168.1.46:8022") 
        endpoint = f"{url}/generate"
        
        # We split text if it's too long, but XTTSv2 usually handles sentences well.
        # It's safer to split to avoid VRAM OOM on the local GPU
        parts = AudioEngine._split_text(text, 250)
        tmp_dir = out_path.parent / "__tts_tmp_xtts__"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        
        chunk_paths = []
        try:
            for i, part in enumerate(parts):
                print(f"Generating XTTS chunk {i+1}/{len(parts)} ({len(part)} chars)...")
                
                data = {
                    "text": part,
                    "language": "es",
                    "voice_id": voice_id
                }
                r = requests.post(endpoint, data=data, timeout=120)
                    
                if not r.ok:
                    raise RuntimeError(f"XTTS API error {r.status_code}: {r.text}")
                    
                chunk_path = tmp_dir / f"{out_path.stem}_{i:03d}.wav"
                chunk_path.write_bytes(r.content)
                chunk_paths.append(chunk_path)
                time.sleep(0.5) # throttle to avoid overloading GPU
                
            AudioEngine._concat_chunks(chunk_paths, out_path, gap_ms)
        finally:
            for p in chunk_paths:
                p.unlink(missing_ok=True)
            if tmp_dir.exists():
                try: tmp_dir.rmdir()
                except: pass

    @staticmethod
    def _split_text(s: str, limit: int) -> List[str]:
        # Split by natural sentence boundaries to avoid TTS stuttering
        import re
        parts = []
        # First, split by major punctuation
        sentences = re.split(r'(?<=[.!?])\s+', s.strip())
        
        current_part = ""
        for sentence in sentences:
            if not sentence.strip():
                continue
                
            if len(current_part) + len(sentence) <= limit:
                current_part += (sentence + " ")
            else:
                if current_part:
                    parts.append(current_part.strip())
                # If a single sentence is longer than the limit, we have to hard-split it by commas or spaces
                if len(sentence) > limit:
                    sub_parts = re.split(r'(?<=[,;:…])\s+', sentence)
                    sub_current = ""
                    for sub in sub_parts:
                        if len(sub_current) + len(sub) <= limit:
                            sub_current += (sub + " ")
                        else:
                            if sub_current:
                                parts.append(sub_current.strip())
                            if len(sub) > limit:
                                # Absolute fallback: split by space
                                words = sub.split()
                                w_curr = ""
                                for w in words:
                                    if len(w_curr) + len(w) <= limit:
                                        w_curr += (w + " ")
                                    else:
                                        if w_curr: parts.append(w_curr.strip())
                                        w_curr = w + " "
                                if w_curr: parts.append(w_curr.strip())
                                sub_current = ""
                            else:
                                sub_current = sub + " "
                    if sub_current:
                        parts.append(sub_current.strip())
                    current_part = ""
                else:
                    current_part = sentence + " "
                    
        if current_part:
            parts.append(current_part.strip())
            
        return parts

    @staticmethod
    def _generate_chunk_with_retry(text: str, voice: str) -> str:
        last_err = None
        for endpoint in ENDPOINTS:
            try:
                r = requests.post(endpoint, json={"text": text, "voice": voice}, timeout=30)
                if not r.ok:
                    last_err = f"Status {r.status_code}: {r.text}"
                    print(f"TikTok endpoint {endpoint} failed: {last_err}")
                    continue
                data = r.json()
                for key in ["data", "audio", "vocal", "result"]:
                    if key in data and isinstance(data[key], str):
                        v = data[key]
                        return v.split("base64,")[-1] if "base64," in v else v
                last_err = f"Invalid format: {data}"
            except Exception as e:
                last_err = str(e)
                print(f"TikTok endpoint {endpoint} exception: {last_err}")
                continue
        raise RuntimeError(f"TikTok TTS service unavailable or invalid response. Last error: {last_err}")

    @staticmethod
    def _concat_chunks(paths: List[Path], out_path: Path, gap_ms: int) -> None:
        final = AudioSegment.silent(duration=0)
        for p in paths:
            fmt = p.suffix.lstrip(".")
            seg = AudioSegment.from_file(p, format=fmt if fmt else "mp3")
            final += seg
            if gap_ms > 0:
                final += AudioSegment.silent(duration=gap_ms)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        final.export(out_path, format="mp3")
