from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fastapi.staticfiles import StaticFiles
from app.config import get_settings
from app.routers import auth, channels, youtube, video_gen, settings, payments, admin

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
app.include_router(payments.router, prefix="/payments", tags=["payments"])
app.include_router(admin.router)


@app.on_event("startup")
def recover_interrupted_videos():
    """Background tasks (asyncio.create_task / run_in_executor) don't survive
    api restarts. Any video left in an in-progress state is dead — mark it as
    failed with a clear message so the user can retry from the reviewer.
    """
    from app.database import SessionLocal
    from app.models.video import Video
    INPROGRESS = ("generating_audio", "generating_images", "rendering", "creating", "script", "audio", "images", "seo")
    db = SessionLocal()
    try:
        stuck = db.query(Video).filter(Video.status.in_(INPROGRESS)).all()
        for v in stuck:
            print(f"[startup] Video {v.id} was stuck in '{v.status}' — marking as failed for recovery", flush=True)
            prev = v.status
            if prev == "rendering":
                v.status = "images_ready"
                v.last_error = "Render interrumpido por reinicio del backend. Pulsa Imágenes → Finalizar y Renderizar para reintentar."
            elif prev in ("generating_images",):
                v.status = "audio_ready"
                v.last_error = "Generación de imágenes interrumpida por reinicio. Pulsa ▶ Auto-imágenes (usará la caché existente)."
            elif prev in ("generating_audio", "audio"):
                v.status = "draft"
                v.last_error = "Generación de audio interrumpida por reinicio. Continúa el pipeline desde el formulario."
            else:
                v.status = "failed"
                v.last_error = f"Pipeline interrumpido en estado '{prev}' por reinicio del backend."
        if stuck:
            db.commit()
            print(f"[startup] Recovered {len(stuck)} interrupted video(s).", flush=True)
    except Exception as e:
        print(f"[startup] WARNING: could not recover interrupted videos: {e}", flush=True)
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {"status": "ok"}
