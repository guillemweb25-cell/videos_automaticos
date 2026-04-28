FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies required for TTS
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    git \
    ffmpeg \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Accept Coqui TOS for model download
ENV COQUI_TOS_AGREED=1

# Pre-download the XTTS_v2 model to bake it into the docker image (optional but saves time on first run)
RUN python -c "from TTS.api import TTS; TTS('tts_models/multilingual/multi-dataset/xtts_v2')"

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
