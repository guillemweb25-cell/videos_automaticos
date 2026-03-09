from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.routers import auth, channels, youtube, video_gen

settings = get_settings()

app = FastAPI(
    title="Videos Automáticos API",
    description="API para la creación automática de vídeos",
    version="0.1.0",
)

print(f"DEBUG: CORS_ORIGINS loaded: {settings.CORS_ORIGINS}")

# Static files for cache
app.mount("/cache", StaticFiles(directory="cache"), name="cache")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(channels.router)
app.include_router(youtube.router)
app.include_router(video_gen.router, prefix="/videos", tags=["video-gen"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
