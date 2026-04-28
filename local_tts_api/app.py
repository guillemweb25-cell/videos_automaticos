import os
import tempfile
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import torch
from TTS.api import TTS

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

@app.post("/generate")
async def generate_audio(
    background_tasks: BackgroundTasks,
    text: str = Form(...),
    language: str = Form("es"),
    speaker_wav: UploadFile = File(...)
):
    try:
        # Save uploaded reference audio temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
            tmp_wav.write(await speaker_wav.read())
            tmp_path = tmp_wav.name

        output_path = tempfile.mktemp(suffix=".wav")

        print(f"Generating audio for text: {text[:50]}... in {language}")
        
        # Generate audio using XTTSv2
        tts.tts_to_file(
            text=text,
            speaker_wav=tmp_path,
            language=language,
            file_path=output_path
        )

        # Cleanup reference audio
        remove_file(tmp_path)

        # Return the generated file and schedule its deletion
        background_tasks.add_task(remove_file, output_path)
        return FileResponse(path=output_path, media_type="audio/wav", filename="output.wav")

    except Exception as e:
        print(f"Error generating TTS: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok", "device": device}
