"""Traducción/mejora de prompts vía LLM, con elección de proveedor OpenAI o Grok
(xAI). Best-effort: si falta clave o falla, devuelve el texto original.

Reutilizable por el estudio de personajes (characters.py) y el vídeo LTX
(video_ltx.py). Las claves vienen de UserSettings (por usuario) o del entorno.
"""
import os
import base64
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


_DESCRIBE_SYSTEM = (
    "Describe this reference photo as a concise English prompt for an image generator. "
    "START with the main garment and its COLOR, emphasized in parentheses with weight, e.g. "
    "'(pink wrap dress:1.3)'. Then add the SETTING/background and the LIGHTING and framing "
    "(e.g. mirror selfie, full body). Do NOT mention identity, face, names or explicit content. "
    "Output ONE line, comma-separated keywords/phrases, no explanation."
)


def _vision_call(client, model, data_url):
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": _DESCRIBE_SYSTEM},
                  {"role": "user", "content": [
                      {"type": "text", "text": "Describe this photo as a prompt:"},
                      {"type": "image_url", "image_url": {"url": data_url}}]}],
        temperature=0.3,
    )
    return (r.choices[0].message.content or "").strip()


def describe_image(image_bytes: bytes, mime: str = "image/jpeg", provider: str = "openai",
                   openai_key: Optional[str] = None, grok_key: Optional[str] = None) -> str:
    """Genera un prompt (inglés) que describe la foto de referencia (ropa/escena/luz)
    con un modelo de visión. Best-effort: "" si falla. Con Grok, cae a OpenAI si peta."""
    provider = (provider or "openai").lower()
    try:
        from openai import OpenAI
        data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"
        ok = openai_key or os.getenv("OPENAI_API_KEY")
        gk = grok_key or os.getenv("GROK_API_KEY")
        if provider == "grok" and gk:
            try:
                return _vision_call(OpenAI(api_key=gk, base_url=GROK_BASE_URL), GROK_MODEL, data_url)
            except Exception:
                pass  # fallback a OpenAI
        if ok:
            return _vision_call(OpenAI(api_key=ok, base_url=os.getenv("OPENAI_BASE_URL") or None), "gpt-4o-mini", data_url)
        return ""
    except Exception:
        return ""
