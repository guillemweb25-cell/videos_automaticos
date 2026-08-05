# Referencia de API (Backend)

FastAPI con autenticación JWT (`get_current_user`). Casi todos los endpoints requieren token. Rutas agrupadas por router (`backend/app/routers/`).

## Auth (`/auth`)
- `POST /auth/register`, `POST /auth/login` (→ access_token), `GET /auth/me`.

## Canales (`/channels`)
- `GET /` · `POST /` · `PATCH /{id}` · `DELETE /{id}` — CRUD. El PATCH acepta `image_style_prompt`, `negative_prompt`, `default_style`, `default_workflow`, **`loras`** (lista de ids), etc.
- `GET|POST|DELETE /{id}/music` — música de fondo del canal (MP3).
- `GET|POST|DELETE /{id}/style-guide` — `style-guide.md` del canal (reglas de nicho, títulos, thumbnails, descripciones que se inyectan al LLM).
- `GET /{id}/youtube/auth-url` · `POST /youtube/callback` · `POST /{id}/youtube/client-secret` · `GET /{id}/youtube/info` — OAuth y credenciales por canal.

## LoRAs (`/loras`)
- `GET /` · `POST /` · `PATCH /{id}` · `DELETE /{id}` — registro de LoRAs (`label`, `filename`, `trigger_words`, `model_strength`, `clip_strength`, `notes`).
- `GET /loras/available-files` — lista los `.safetensors` que ComfyUI puede cargar (para el desplegable; se consultan a ComfyUI en vivo).
- La **asignación** LoRA↔canal se hace vía `PATCH /channels/{id}` con `loras: [ids]`.

## Generación de vídeo (`/videos`)
- `GET /videos/config` — voces (TikTok/ElevenLabs/XTTS local), estilos, modelos Leonardo, modos (FAST/QUALITY/COMFYUI).
- `GET /videos/workflows` — `.json` en `/workflows`. `GET /videos/overlays`.
- `POST /videos/` — crea vídeo (guion, canal, voz, resolución, estilo, `llm_provider`).
- `POST /videos/{id}/script` · `GET .../script`.
- `POST /videos/{id}/audio?voice=&provider=` — genera audio por párrafo (guarda `tts_provider`). `GET .../audio-progress`.
- **`POST /videos/{id}/paragraphs/{pid}/regenerate-audio`** — re-sintetiza SOLO ese párrafo (fix glitch), sin rehacer el vídeo. Usa el proveedor real guardado.
- `POST /videos/{id}/images` — genera imágenes (async). `GET .../images-progress`. `GET .../images_data`.
- `POST /videos/{id}/paragraphs/{pid}/regenerate` — regenera prompts+imágenes de un párrafo.
- **`POST /videos/{id}/regenerate-all-prompts`** — borra prompts+imágenes y regenera TODOS los prompts desde el LLM (para aplicar reglas nuevas del canal). No toca el audio.
- `POST /videos/{id}/regenerate-image` · `POST .../regenerate-prompt` · `POST .../add-image` · `DELETE .../remove-image` · `POST .../auto-fill-images/{pid}`.
- `POST /videos/{id}/image-to-video` — img→mp4 (Grok/Leonardo VEO). `POST .../link-clip` · `POST .../upload-clip`.
- `POST /videos/{id}/render?subtitles=&overlay=` — render MoviePy (async). `GET .../render-progress`. Aviso Telegram al terminar/fallar.
- `POST /videos/{id}/seo` · `POST .../generate-thumbnail` · `POST .../regenerate-thumbnail-hook` · `POST .../update-thumbnail-text` · `POST .../upload-thumbnail`.
- Huérfanos: `GET /videos/orphans` · `DELETE /videos/{id}/purge` · `POST /videos/bulk-purge` · `POST /videos/{id}/mark-uploaded`.
- `POST /videos/{id}/auto-advance` — reanuda desde `audio_ready` con defaults del canal.

## YouTube (`/youtube`)
- `GET /youtube/{id}/metadata` · `POST /{id}/upload` · `POST /{id}/update-metadata` · `POST /{id}/regenerate/{title|description|tags}` · `POST /{id}/reset-upload`.
- `GET /youtube/videos/{ch}` · `GET /shorts/{ch}` · `POST /scan-public-channel` (yt-dlp) · `POST /download/{ch}`.

## Ajustes / Pagos / Admin
- `GET|PUT /settings/` — API keys por usuario. `GET /settings/public` · `POST /settings/global` · `POST /settings/cleanup`.
- `GET /payments/balance` · `POST /payments/create-checkout-session` (Stripe).
- `/admin/users`, `/admin/users/{id}/add-credits`, `/admin/stats`.

## Health
- `GET /health` · `GET /` (200) · `GET /favicon.ico` (204).

## Notas
- Muchos POST de generación son **async** (lanzan tarea de fondo y devuelven de inmediato); el frontend hace polling de `*-progress`.
- Al reiniciar la api, un hook de startup **rescata** vídeos atascados en estados en-progreso (los degrada al estado seguro previo con `last_error`).
