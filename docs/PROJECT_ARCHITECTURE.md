# Videos Automáticos - Arquitectura del Proyecto

Este documento es el **contexto técnico global** para que cualquier IA o persona comprenda la estructura, tecnologías y flujos del proyecto antes de tocar nada.

> Última actualización: 2026-08-05. Ver [CHANGELOG.md](CHANGELOG.md) para el detalle de lo añadido desde la primera versión de estos docs (2026-04-24).

## 1. Visión General
Plataforma full-stack autohospedada (Docker) que convierte un guion de texto en un vídeo "faceless" (Shorts/TikTok o largo) con voz IA, imágenes IA, subtítulos, miniatura, SEO y subida a YouTube. **Multi-canal**: cada canal tiene su propia identidad visual, voz, reglas de estilo, LoRAs y credenciales. Pipeline **resumible** (máquina de estados por vídeo).

## 2. Pila Tecnológica

### Backend
- **FastAPI** (Python 3.12), **100% async** (nunca bloquear el event loop: `await asyncio.to_thread` / `run_in_executor`).
- **MariaDB** (SQLAlchemy ORM + Alembic).
- **MoviePy + FFmpeg** (render, Ken Burns, overlays chroma, loudnorm EBU R128), **Pillow** (parche `LANCZOS`/`ANTIALIAS`).

### Backends de IA intercambiables por primitiva (elegibles por vídeo)
| Primitiva | Cloud | Cloud | Local (gratis) |
|---|---|---|---|
| **Imágenes** | Leonardo (VEO) | Grok / xAI | **ComfyUI + SDXL** |
| **Vídeo (img→mp4)** | Leonardo VEO3 | Grok grok-imagine-video | — |
| **LLM (prompts+SEO)** | OpenAI GPT-4o-mini | xAI Grok | — |
| **TTS** | ElevenLabs | TikTok TTS | **Coqui XTTSv2** (clonación) |
| **STT** | AssemblyAI (sync frase↔audio) | — | — |

- **ComfyUI** es el motor de imágenes principal (SDXL). Checkpoint SFW por defecto en la mayoría de canales: **RealVisXL V5.0** (sustituyó a Juggernaut Ragnarok, que era NSFW-prone). Ver [WORKFLOWS_AND_PIPELINES.md](WORKFLOWS_AND_PIPELINES.md).

### Frontend
- **React 19 + TypeScript + Vite**. En producción se sirve un **build estático** (`vite build && vite preview`), NO dev con HMR → cualquier cambio de código de frontend requiere **reconstruir el contenedor** `frontend`.
- Componentes clave: `App.tsx` (sidebar + navegación), `ChannelDashboard.tsx`, `VideoCreator.tsx`, `ImageReviewer.tsx` (revisión imagen a imagen, regenerar prompts/imágenes/audio, miniatura, render), `LoraManager.tsx` (catálogo de LoRAs + asignación por canal), `OrphansManager.tsx`, `Settings.tsx`, `Payments.tsx`, `AdminDashboard.tsx`, `api.ts` (cliente tipado).

### Infraestructura
- **Docker Compose**: `api` (FastAPI), `db` (MariaDB), `frontend` (Vite). El servicio **`local_tts_api`** (XTTSv2 + GPU) vive en un compose aparte, en la máquina con GPU (junto a ComfyUI).
- **Dos máquinas**: API/DB/frontend en un VPS Linux; ComfyUI + XTTSv2 en un Windows 11 con GPU en la LAN. Orquestación async por HTTP.
- Volúmenes: `./cache` (assets por `user/canal/vídeo`), `./overlay`, `./workflows`.

## 3. Modelos de datos (`backend/app/models/`)
- **User** (créditos, admin), **UserSettings** (API keys por usuario: openai/grok/leonardo/elevenlabs/assemblyai).
- **Channel**: `name`, `youtube_handle`, `creds_dir`, `image_style_prompt`, `negative_prompt`, `default_style`, `default_workflow`, **`loras`** (lista JSON de ids de LoRA), `user_id`.
- **Video**: estado (máquina de estados resumible), `base_dir`, `width/height`, `voice`, **`tts_provider`**, `style`, `max_images_per_paragraph`, `llm_provider`, campos SEO/YouTube, `last_error`.
- **Lora** (registro): `label`, `filename` (nombre exacto ComfyUI), `trigger_words`, `model_strength`, `clip_strength`, `notes`, `user_id`.
- **GlobalSettings** (registro abierto, etc.).

## 4. Servicios (`backend/app/services/`)
- `comfy_service.py`: cliente async ComfyUI + **inyección dinámica de LoRAs** (encadena `LoraLoader` tras el checkpoint, recablea MODEL/CLIP) + antepone trigger words al positivo + snap a buckets SDXL.
- `image_engine.py`: orquestador de imágenes (ComfyUI/Leonardo/Grok). Genera prompts con el LLM. **SAFETY_OVERRIDE** (anti-gore/NSFW/menores) + `enforce_modest_clothing` (ropa forzada en el positivo para todo estilo no adulto) + scrubs específicos por canal.
- `audio_engine.py`: TTS multi-backend (ElevenLabs/TikTok/XTTS). Trocea texto y fusiona chunks cortos (fix "ultra tumba" de XTTS).
- `lora_service.py`: resuelve `channel.loras` → payload + trigger words.
- `telegram_service.py`: notificador fire-and-forget (avisos fin/fallo de imágenes y render).
- `style_service.py`: catálogo de estilos + carga por capas (global→canal→workflow) + lectura de `style-guide.md` por canal.
- `rendering_engine.py`, `seo_engine.py`, `subtitle_engine.py`, `youtube_api.py`, `youtube_dl.py` (scan de canales públicos), `maintenance_service.py`.

## 5. Flujo de datos (generación de vídeo)
1. **Config (frontend)**: canal, guion, voz, estilo, workflow, modo (ComfyUI/cloud). Los **defaults del canal** pre-rellenan el formulario.
2. **Audio**: TTS por párrafo → `cache/.../audio/chunks/NNN.mp3` + `paragraphs_durations.json`. Guarda `video.tts_provider`.
3. **Imágenes (async)**: por párrafo → transcripción word-level (AssemblyAI) para sincronizar la frase → LLM genera prompt → ComfyUI (con LoRAs+ropa inyectados) → `images/pNNN_MM.png`. Prompts cacheados en `image_prompts_all.json`.
4. **Revisión**: `ImageReviewer` permite regenerar prompt/imagen/párrafo, **🔁 regenerar TODOS los prompts** (aplica reglas nuevas del canal), **🎧 regenerar audio** de un párrafo, y elegir overlay/subtítulos.
5. **Render**: MoviePy sincroniza imágenes a la duración del audio + Ken Burns + overlay + loudnorm → `output/final_video.mp4`. Aviso Telegram al terminar.
6. **SEO + YouTube**: título/descr/tags/miniatura por reglas del canal → subida OAuth por canal.

## 6. Notas importantes para IA
- **Async everywhere**. Nunca bloquear el event loop.
- **Config por canal fuera de git**: `default_style/workflow`, `image_style_prompt`, `negative_prompt`, asignación de LoRAs viven en **BD**; los `style-guide.md` en **`cache/`** (ignorado). Respaldar con `backend/scripts/manage_channels.py export` (genera `backend/config/channels_config.json`, commiteable). Los **checkpoints y LoRAs** (ficheros) viven en la máquina GPU, no en git.
- **Workflows = plantillas**: el backend parchea el nodo `_meta.title == "positive"/"negative"`, el seed y la resolución. Los LoRAs se inyectan en runtime (no van baked salvo excepciones).
- **Estilo adulto**: solo `anime_hentai` permite desnudez; el resto fuerza ropa.
- **Frontend estático**: cambios de código de frontend → reconstruir el contenedor `frontend`.
- **XTTS local**: `app.py` montado como volumen; el contenedor NO recarga solo → reiniciar `local_tts_api-tts_api-1` tras cambios.
