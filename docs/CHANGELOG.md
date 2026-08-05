# Changelog — cambios desde la base de docs (2026-04-24)

Resumen de lo añadido desde la primera versión de esta documentación. Ordenado por temas; fechas aproximadas del historial de git.

## 🎨 Sistema de LoRAs (jul–ago 2026)
- **Registro de LoRAs** (tabla `loras`) con `label`, `filename`, `trigger_words`, fuerzas y notas. Pestaña **🎛️ LoRAs** en el frontend (catálogo + asignación por canal).
- **Inyección dinámica** en `comfy_service`: encadena `LoraLoader` tras el checkpoint y recablea MODEL/CLIP en cualquier workflow SDXL; antepone las trigger words al positivo. Endpoint `/loras` (CRUD + `available-files` desde ComfyUI).
- `channel.loras` (asignación por canal) + `lora_service.resolve_channel_loras`.
- LoRAs en uso: Tarot (DUSK), Dreamscape (canal sueños), Detail Tweaker / God Rays (opcionales).

## 🖼️ Imágenes: calidad, seguridad y variedad
- **Checkpoint SFW RealVisXL V5.0** adoptado en Grabovoi, Llama Violeta, Cábala, Sueños, Jesús, Salud y Tarot (sustituye a Juggernaut Ragnarok, propenso a desnudos) + sampler `dpmpp_2m/karras`.
- **Ropa forzada global** (`enforce_modest_clothing`): fuerza vestimenta en el positivo en todo estilo no adulto (`anime_hentai` exento). Es la defensa fiable contra el sesgo de desnudez de SDXL.
- **Anti-repetición / variedad de plano** en el prompt del LLM; scrub del falso amigo "llama" (animal vs fuego) en Llama Violeta.
- **Prompts anclados a la frase exacta** del audio (AssemblyAI) para sincronía imagen↔voz.
- Buckets SDXL óptimos (anti-deformidad), SAFETY_OVERRIDE anti-gore/menores, dress code bíblico, anti-niños (Korean/Grabovoi).
- **🔁 Regenerar TODOS los prompts** (nuevo): borra prompts+imágenes y los regenera desde el LLM aplicando reglas nuevas del canal. Regenerar por párrafo / auto-completar por duración.
- Miniaturas: workflow por canal (convención por slug), tipografía Anton, personaje a la derecha.

## 🔊 Audio (multi-backend)
- **TTS local XTTSv2 (Coqui)** en `local_tts_api` (clonación por seeds, `/voices`, `/trim-seeds`, stateless). + **TikTok TTS** y **ElevenLabs**.
- `video.tts_provider` guardado; **regenerar audio por párrafo** (fix de glitch sin rehacer el vídeo, con inferencia de proveedor segura).
- **XTTS estable**: params de generación (repetition_penalty/temperature) + fusión de chunks cortos (fin del "ultra tumba") + mejor split de texto.

## 🌐 Multi-proveedor y multi-canal
- **Grok (xAI)** para prompts/SEO + `grok-imagine-video` (img→mp4). Pipeline de fondo + mejoras UX.
- **Canal coreano** + autodetección de idioma (SEO+TTS) + slugify Unicode-aware.
- **Defaults por canal** que pre-rellenan el formulario; estilos por canal (`style-guide.md`).
- **Estilos/workflows** nuevos: Mystical-Cabala, Cinematic-Horror, Grabovoi-Mystic, Realismo Sucio (México), anime/hentai, crayón (zennESP→Tarot), Dreamy-Oniric, Tarot-RealVis.

## 🔔 Notificaciones y operaciones
- **Telegram**: avisos al terminar/fallar imágenes y render (`telegram_service`, fire-and-forget). Env `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`.
- **Backup de config de canales** (`scripts/manage_channels.py`): export/import de BD + `style-guide.md` + **LoRAs y asignaciones** (portable por filename).
- **Analizar Canal**: escaneo de canales públicos de YouTube vía yt-dlp.
- **Gestor de huérfanos**, recuperación de vídeos atascados al arranque, fixes de event-loop bloqueado, fix de overlay truncando el render.

## 🐛 Fixes de producción destacados
- Render truncado a 80s por `shortest=1` en el overlay → `-stream_loop -1`.
- Frontend colgado en "Loading" por llamadas síncronas bloqueando uvicorn → `asyncio.to_thread`.
- Tareas de fondo perdidas en cada reinicio → recovery en `@app.on_event("startup")`.
- Selección de voz pisada por `useEffect`; slugify/mojibake en migración (nombres con tildes).
- YouTube: scope `youtube.force-ssl`, gestión de vídeos ya subidos sin duplicar, fixes 422.

## ⚙️ Cambios operativos a recordar
- **Puertos**: API 8500, frontend 8501.
- **Frontend estático** (vite preview): reconstruir el contenedor tras cambios de código.
- **`.env` al arrancar**: recrear la api tras editarlo.
- **Config de canal fuera de git** (BD + `cache/`): respaldar con `manage_channels.py`.
- **XTTS `app.py`** montado como volumen: reiniciar `local_tts_api` tras cambios.
