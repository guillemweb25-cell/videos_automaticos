import os
import tempfile
from fastapi import FastAPI, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
import torch
from TTS.api import TTS
from pathlib import Path

# Accept Coqui TOS automatically
os.environ["COQUI_TOS_AGREED"] = "1"

app = FastAPI(title="Local ElevenLabs - XTTS API")

print("Loading XTTSv2 model...")
device = "cuda" if torch.cuda.is_available() else "cpu"
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
print(f"Model loaded on {device}")

def remove_file(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception as e:
        print(f"Failed to remove file {path}: {e}")

@app.get("/voices")
def get_voices():
    seed_dir = Path("audio_seeds")
    voices = []
    if seed_dir.exists():
        for f in seed_dir.glob("*"):
            if f.suffix in [".mp3", ".wav", ".m4a", ".ogg"]:
                voices.append(f.stem)
    return JSONResponse(content={"voices": sorted(voices)})

@app.post("/generate")
async def generate_audio(
    background_tasks: BackgroundTasks,
    text: str = Form(...),
    language: str = Form("es"),
    voice_id: str = Form(...)
):
    try:
        # Resolve reference audio path
        seed_dir = Path("audio_seeds")
        ref_path = None
        for ext in [".mp3", ".wav", ".m4a", ".ogg"]:
            p = seed_dir / f"{voice_id}{ext}"
            if p.exists():
                ref_path = p
                break
                
        if not ref_path:
            raise HTTPException(status_code=404, detail=f"Voice reference '{voice_id}' not found in audio_seeds/")

        output_path = tempfile.mktemp(suffix=".wav")

        print(f"Generating audio for text: {text[:50]}... in {language} with voice {voice_id}")
        
        # Generate audio using XTTSv2
        tts.tts_to_file(
            text=text,
            speaker_wav=str(ref_path),
            language=language,
            file_path=output_path
        )

        # Return the generated file and schedule its deletion
        background_tasks.add_task(remove_file, output_path)
        return FileResponse(path=output_path, media_type="audio/wav", filename="output.wav")

    except Exception as e:
        print(f"Error generating TTS: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok", "device": device}

@app.post("/trim-seeds")
def trim_seeds(duration: int = 10):
    import subprocess
    seed_dir = Path("audio_seeds")
    if not seed_dir.exists():
        return {"status": "error", "detail": "No audio_seeds directory found"}
    
    trimmed = []
    for f in seed_dir.glob("*"):
        if f.suffix.lower() in [".mp3", ".wav", ".m4a", ".ogg"]:
            tmp_path = str(f) + ".tmp.wav"
            # Extract first 'duration' seconds and force convert to high quality WAV for XTTS
            cmd = [
                "ffmpeg", "-y", "-i", str(f), 
                "-t", str(duration), 
                "-ar", "22050", # optimal sample rate for XTTS
                "-ac", "1",     # mono
                tmp_path
            ]
            try:
                subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                os.replace(tmp_path, str(f))
                trimmed.append(f.name)
            except Exception as e:
                print(f"Failed to trim {f.name}: {e}")
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                
    return {"status": "ok", "message": f"Trimmed {len(trimmed)} files to {duration} seconds.", "files": trimmed}
