from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.routers import auth, channels, youtube, video_gen, settings

settings_config = get_settings()

app = FastAPI(
    title="Videos Automáticos API",
    description="API para la creación automática de vídeos",
    version="0.1.0",
)

# Increase upload size limit to 500MB for video file uploads
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class LargeUploadMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request._body_max_size = 500 * 1024 * 1024  # 500MB
        return await call_next(request)

app.add_middleware(LargeUploadMiddleware)

# Static files for cache
app.mount("/cache", StaticFiles(directory="cache"), name="cache")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings_config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(channels.router)
app.include_router(settings.router)
app.include_router(youtube.router)
app.include_router(video_gen.public_router, prefix="/videos", tags=["video-gen-public"])
app.include_router(video_gen.router, prefix="/videos", tags=["video-gen"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
