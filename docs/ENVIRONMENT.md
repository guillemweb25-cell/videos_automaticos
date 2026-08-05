# Variables de Entorno y Configuración

El `.env` en la raíz configura BD, APIs, integraciones y despliegue. El backend lo carga vía Pydantic (`app/config.py`) y docker-compose lo inyecta (`env_file: .env`).

> ⚠️ Las variables se cargan al **arrancar** el contenedor. Tras editar `.env` hay que **recrear** el contenedor api (`docker compose up -d --force-recreate api`), no basta el hot-reload.

## 1. Base de datos (docker-compose)
- `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`, `MYSQL_ROOT_PASSWORD`.
- `DATABASE_URL` (backend): p. ej. `mysql+pymysql://user:pass@db:3306/videos_automaticos`.

## 2. Puertos (docker-compose, opcionales)
- `BACKEND_PORT` (default **8500** → 8000 interno), `FRONTEND_PORT` (default **8501** → 5173 interno).

## 3. APIs de IA
Pueden ir en `.env` (global) y/o por usuario en la pestaña **Ajustes** (guardadas en `user_settings`). Las keys por-usuario tienen prioridad al generar.
- `OPENAI_API_KEY` — LLM (prompts de imagen + SEO).
- `GROK_API_KEY` — xAI Grok (LLM/SEO + grok-imagine-video). *(gestionada por usuario en Ajustes)*
- `LEONARDO_API_KEY` — imágenes/vídeo Leonardo (VEO).
- `ELEVEN_API_KEY` — TTS ElevenLabs.
- `ASSEMBLYAI_API_KEY` — STT (sincronizar la frase exacta del audio con cada imagen).

## 4. ComfyUI (imágenes locales)
- `COMFY_URL` — IP:puerto de ComfyUI (p. ej. `http://192.168.1.46:8188`). Debe ser accesible desde el contenedor api.
- `COMFY_IS_WINDOWS` — bool (rutas de ComfyUI en Windows).
- `COMFY_SEED` — seed fijo opcional (si no, aleatorio).

## 5. TTS local (XTTSv2)
- `LOCAL_TTS_URL` — URL del servicio `local_tts_api` (p. ej. `http://192.168.1.46:8022`). Sirve `/generate`, `/voices`, `/trim-seeds`.

## 6. Notificaciones Telegram (opcional)
- `TELEGRAM_BOT_TOKEN` — token del bot (de @BotFather).
- `TELEGRAM_CHAT_ID` — chat destino (obtenible con `getUpdates` tras escribir al bot).
- Si faltan, el notificador se salta silenciosamente (nunca rompe el pipeline).

## 7. Stripe / créditos
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`.
- `VIDEO_COST_CREDITS` — coste en créditos por vídeo (default 50).
- `FRONTEND_URL` — usado en checkout y CORS.

## 8. Sesión (JWT) y CORS
- `JWT_SECRET_KEY`, `JWT_ALGORITHM` (HS256), `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 7 días).
- `CORS_ORIGINS` — lista o CSV de orígenes permitidos.

## 9. Scripts de sincronización (opcional, `scripts/sync_*.sh`)
- `REMOTE_SSH_USER`, `REMOTE_SSH_HOST`, `REMOTE_SSH_PORT`, `REMOTE_BASE_PATH`.

> `.env` está en `.gitignore`: los secretos NO viajan a git. Ver `.env.example` para la plantilla.
