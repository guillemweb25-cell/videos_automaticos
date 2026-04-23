from pydantic import field_validator
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List, Union, Any

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "mysql+pymysql://appuser:apppassword@db:3306/videos_automaticos"

    # JWT
    JWT_SECRET_KEY: str = "change-me-to-a-random-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # CORS
    CORS_ORIGINS: Any = [
        "http://localhost:5173",
        "http://localhost:8501",
        "http://localhost:3000",
        "http://localhost:8500",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return v
        return []

    # External APIs
    OPENAI_API_KEY: str | None = None
    LEONARDO_API_KEY: str | None = None
    ELEVEN_API_KEY: str | None = None
    ASSEMBLYAI_API_KEY: str | None = None
    COMFY_URL: str = "http://192.168.1.184:8188"

    # Stripe
    STRIPE_SECRET_KEY: str | None = None
    STRIPE_WEBHOOK_SECRET: str | None = None
    FRONTEND_URL: str = "http://localhost:5173"
    VIDEO_COST_CREDITS: int = 50

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }

@lru_cache()
def get_settings() -> Settings:
    return Settings()
