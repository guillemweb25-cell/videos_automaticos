from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import auth, channels, youtube

settings = get_settings()

app = FastAPI(
    title="Videos Automáticos API",
    description="API para la creación automática de vídeos",
    version="0.1.0",
)

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


@app.get("/health")
def health_check():
    return {"status": "ok"}
