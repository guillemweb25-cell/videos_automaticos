"""Traducción/mejora de prompts vía LLM, con elección de proveedor OpenAI o Grok
(xAI). Best-effort: si falta clave o falla, devuelve el texto original.

Reutilizable por el estudio de personajes (characters.py) y el vídeo LTX
(video_ltx.py). Las claves vienen de UserSettings (por usuario) o del entorno.
"""
import os
from typing import Optional

# Modelos por defecto (se pueden sobreescribir por entorno).
OPENAI_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
GROK_MODEL = os.getenv("GROK_TEXT_MODEL", "grok-4.20-beta")   # igual que image_engine
GROK_BASE_URL = "https://api.x.ai/v1"


def translate(text: str, system_prompt: str, provider: str = "openai",
              openai_key: Optional[str] = None, grok_key: Optional[str] = None,
              temperature: float = 0.4) -> str:
    text = text or ""
    provider = (provider or "openai").lower()
    try:
        from openai import OpenAI  # el SDK de OpenAI vale para xAI (API compatible)
        if provider == "grok":
            key = grok_key or os.getenv("GROK_API_KEY")
            if key:
                client = OpenAI(api_key=key, base_url=GROK_BASE_URL)
                model = GROK_MODEL
            else:
                # sin clave de Grok -> intenta OpenAI como fallback
                key = openai_key or os.getenv("OPENAI_API_KEY")
                if not key:
                    return text
                client = OpenAI(api_key=key, base_url=os.getenv("OPENAI_BASE_URL") or None)
                model = OPENAI_MODEL
        else:
            key = openai_key or os.getenv("OPENAI_API_KEY")
            if not key:
                return text
            client = OpenAI(api_key=key, base_url=os.getenv("OPENAI_BASE_URL") or None)
            model = OPENAI_MODEL
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": text}],
            temperature=temperature,
        )
        return (r.choices[0].message.content or "").strip() or text
    except Exception:
        return text
