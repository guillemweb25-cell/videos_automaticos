# Flujos y Pipelines - Detalle Técnico

## 1. Pipeline de imágenes (ComfyUI)
1. **Prompt del LLM**: `image_engine.generate_prompts` toma el párrafo/frase (sincronizada con AssemblyAI) + estilo del canal + `style-guide.md` (custom_rules) y produce un prompt en inglés. Aplica **SAFETY_OVERRIDE** (anti-gore/NSFW/menores), **variedad de plano** (no repetir composiciones), y **`enforce_modest_clothing`** (fuerza ropa en el positivo en todo estilo NO adulto — es la única defensa fiable contra el sesgo de desnudez de SDXL; el negativo solo no basta).
2. **Carga de plantilla**: `ComfyService` lee `/workflows/<wf>.json`.
3. **Inyección de LoRAs** (`comfy_service._inject_loras`): resuelve `channel.loras` (`lora_service.resolve_channel_loras`) → inserta una cadena de `LoraLoader` tras el `CheckpointLoaderSimple`, recablea MODEL/CLIP de todos los consumidores, y **antepone las trigger words** al nodo positivo. Genérico para cualquier workflow SDXL.
4. **Parcheo**: nodo `_meta.title=="positive"/"negative"` (o primer `CLIPTextEncode`), seed, y **resolución** (snap a buckets SDXL óptimos para evitar deformidades). El prompt del LLM va delante del texto de estilo del nodo.
5. **Envío**: POST async a `/prompt` de ComfyUI; polling hasta descargar la imagen a `cache/.../images/`.

### Checkpoints
- **RealVisXL V5.0** es el checkpoint SFW por defecto en la mayoría de canales fotorrealistas (Grabovoi, Llama Violeta, Cábala, Sueños, Jesús, Salud, Tarot). Sustituyó a **Juggernaut Ragnarok** (merge sin censura, muy propenso a desnudos). Sampler recomendado: `dpmpp_2m/karras`, ~30 pasos base + 12 de refinement, cfg ~5.
- **Sombras** (horror) mantiene un checkpoint más gritty a propósito. El **canal adulto** (`anime_hentai`) NO fuerza ropa.
- Convención de miniatura por canal: `workflows/<slug(canal)>-thumbnail.json` (si existe, gana sobre el workflow del cuerpo).

## 2. Pipeline de audio (multi-backend)
- Proveedores: **ElevenLabs**, **TikTok TTS**, **XTTSv2 local** (Coqui, clonación de voz por seeds en `local_tts_api/audio_seeds/`). El proveedor usado se guarda en `video.tts_provider`.
- `audio_engine._split_text` trocea por frases y **fusiona chunks < 60 chars** con el vecino (evita el artefacto "voz de ultra tumba" de XTTS en fragmentos minúsculos).
- **XTTS estable** (`local_tts_api/app.py`): `tts_to_file` con `repetition_penalty` alto + `temperature` baja + `enable_text_splitting` (reduce el artefacto "audio al revés" en las juntas). Defensivo (fallback si el build no acepta kwargs).
- **Regenerar audio por párrafo**: re-sintetiza solo un `NNN.mp3` (a temporal y swap atómico; un fallo no deja el párrafo mudo), actualiza `paragraphs_durations.json` + duración total, e invalida el transcript. XTTS es estocástico → re-tirar suele arreglar un glitch residual.

## 3. Arquitectura async (FastAPI + asyncio)
- Generaciones (imágenes/audio/render/SEO) corren en **tareas de fondo** (`asyncio.create_task` / `run_in_executor`); el router devuelve de inmediato y el frontend hace polling de `*-progress`.
- **Nunca bloquear el event loop**: las llamadas síncronas (requests a OpenAI/Grok, MoviePy, TTS) van envueltas en `await asyncio.to_thread(...)`.
- **Recuperación al arranque**: un hook `@app.on_event("startup")` detecta vídeos atascados en estados en-progreso (tras un reinicio) y los degrada al estado seguro previo con un `last_error` accionable.

## 4. Render (MoviePy + FFmpeg)
1. **Sync audio↔imagen**: cada párrafo dura lo que su audio; sus imágenes se reparten sobre esa duración (Ken Burns).
2. **Overlay**: vídeo de partículas con `vfx.mask_color`; se usa `-stream_loop -1` para que `shortest=1` no trunque el render al overlay.
3. **Loudnorm** EBU R128 + música de fondo con ducking.
4. **Subtítulos** (AssemblyAI) quemados opcionalmente.
5. Estado → `ready`, `output/final_video.mp4`. Aviso Telegram.

## 5. Config por canal (¡fuera de git!)
- BD: `default_style/workflow`, `image_style_prompt`, `negative_prompt`, asignación de `loras`.
- `cache/<...>/style-guide.md`: reglas de nicho/visuales que se inyectan al LLM (el bloque **antes del primer `##`** se usa como reglas de imágenes → poner ahí las reglas visuales/anti-desnudez).
- Respaldo: `backend/scripts/manage_channels.py export|import` → `backend/config/channels_config.json` (incluye canales + LoRAs + style-guides; portable por filename). Ver [SETUP_GUIDE.md](SETUP_GUIDE.md).
