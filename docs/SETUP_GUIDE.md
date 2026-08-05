# Guía de Instalación y Configuración

## 1. Requisitos
- Docker + Docker Compose.
- **ComfyUI** accesible por red (con checkpoints SDXL y LoRAs instalados en la máquina GPU).
- Opcional: servicio **`local_tts_api`** (XTTSv2 + GPU) para voces clonadas.
- Cuentas API según lo que uses: OpenAI y/o Grok (LLM+SEO), ElevenLabs y/o TikTok/XTTS (voz), AssemblyAI (sync subtítulos), Leonardo (opcional), Stripe (créditos).

## 2. `.env`
```bash
cp .env.example .env   # editar
```
Críticas: `COMFY_URL`, `LOCAL_TTS_URL`, `MYSQL_PASSWORD`, keys de IA. Ver [ENVIRONMENT.md](ENVIRONMENT.md).
> Tras editar `.env`, **recrea** el contenedor: `docker compose up -d --force-recreate api` (las env vars se cargan al arrancar).

## 3. Despliegue
```bash
docker compose up -d --build
```
- API: `http://localhost:8500` · Frontend: `http://localhost:8501` · DB: 3307→3306.
- Migraciones Alembic corren al arrancar la api (`alembic upgrade head` en `backend/start.sh`).
- El servicio TTS local se levanta por separado desde `local_tts_api/` (su propio compose, en la máquina GPU).

## 4. ComfyUI: workflows, checkpoints y LoRAs
- **Workflows**: en ComfyUI, Dev mode → "Save (API Format)" → guardar el JSON en `/workflows`. El nodo positivo/negativo debe tener `_meta.title` = `positive`/`negative` para que el backend lo parchee. Aparecen solos en el desplegable del frontend.
- **Checkpoints**: en `ComfyUI/models/checkpoints/SDXL/`. Por defecto se usa **RealVisXL V5.0** (SFW). Los workflows referencian p. ej. `SDXL/RealVisXL_V5.0_fp16.safetensors`.
- **LoRAs**: en `ComfyUI/models/loras/` (subcarpetas permitidas; ComfyUI las lista con `\` en Windows). Se **registran** en la pestaña 🎛️ LoRAs (con sus trigger words) y se **asignan** a un canal. El backend los inyecta en runtime sobre cualquier workflow SDXL (no hay que editar el JSON).

## 5. Frontend (build estático)
El contenedor `frontend` hace `vite build && vite preview` (no dev/HMR). Tras cambiar código de frontend, **reconstruye**: `docker restart videos_automaticos-frontend-1` (o `docker compose up -d --build frontend`). Los cambios de **datos** (nuevo workflow/LoRA en BD) solo requieren recargar el navegador.

## 6. Backup de configuración de canales
La config que hace que cada canal genere bien vive en BD (estilos, negativos, asignación de LoRAs) y en `cache/` (style-guides) — **no en git**. Respáldala:
```bash
# snapshot -> backend/config/channels_config.json (commiteable)
docker exec videos_automaticos-api-1 python scripts/manage_channels.py export
# previsualizar restore
docker exec videos_automaticos-api-1 python scripts/manage_channels.py import --dry-run
# restaurar (BD + style-guides)
docker exec videos_automaticos-api-1 python scripts/manage_channels.py import
```
Incluye canales + registro de LoRAs + asignaciones (portable por filename). No toca secretos (OAuth). Recomendado: exportar y commitear tras cada cambio de config de canal.

## 7. Notificaciones Telegram (opcional)
Añade `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` al `.env`, recrea la api, y recibirás aviso al terminar/fallar imágenes y render. El `chat_id` se obtiene escribiendo al bot y consultando `getUpdates`.

## 8. Sincronización portátil↔servidor
`scripts/sync_push.sh` / `sync_pull.sh` mueven caché/BD/credenciales (NO el código — eso por Git). ⚠️ Transferir preservando UTF-8 (nombres de carpeta con tildes); una transferencia que reinterprete a CP437/Latin-1 corrompe los nombres.
