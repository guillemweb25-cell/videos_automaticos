# Videos Automáticos — Resumen del proyecto

Plataforma full-stack de creación automática de Shorts/TikToks para YouTube, multicanal, autohospedada en infraestructura propia. Pensada inicialmente para uso personal en 7 canales temáticos (espiritualidad, sueños, mensajes religiosos, salud senior, códigos Grabovoi, contenido adulto, etc.) y diseñada con arquitectura SaaS lista para abrir a más usuarios. ~173 commits, ~50 archivos de código backend/frontend, 17 workflows de ComfyUI distintos.

## Stack técnico

**Backend** — Python 3.12 · FastAPI · SQLAlchemy + Alembic · MariaDB · Pydantic · MoviePy · FFmpeg · Pillow · uvicorn.

**Frontend** — React 19 · TypeScript · Vite (modo *preview* en producción para sesiones largas estables) · CSS-in-JS sin framework UI.

**IA / generación** — OpenAI GPT-4o-mini · xAI Grok (LLM y `grok-imagine-video`) · Leonardo AI (modelos VEO3 / VEO3FAST) · ComfyUI con SDXL Juggernaut XL Ragnarok (autohospedado en GPU local) · ElevenLabs · TikTok TTS · XTTSv2 de Coqui (TTS local autohospedado para clonación de voz) · AssemblyAI para subtítulos.

**Integraciones** — YouTube Data API v3 (OAuth 2.0 por canal, upload, metadata, vistas) · Stripe (checkout + créditos prepago) · webhooks de pago.

**Infra / despliegue** — Docker Compose (api + frontend + db + servicio TTS local) · proxy inverso con HTTPS · reverse-proxy hacia GPU Windows en LAN (192.168.1.46) · acceso SSH desde Linux Debian a Windows 11 · volúmenes persistentes para caché de generación y credenciales OAuth.

## Arquitectura

Pipeline asíncrono dirigido por estados sobre cada vídeo:

```
draft → generating_audio → audio_ready
      → generating_images → images_ready
      → rendering → ready_to_upload
      → uploaded
```

Cada transición la dispara el usuario o un endpoint de "auto-advance". El estado se persiste en MariaDB y los artefactos (audios, imágenes, miniaturas, JSON de prompts, vídeo final) viven en una carpeta de caché por vídeo organizada como `cache/user_XXXX/CCCC-canal-handle/VVVV-titulo-slug/`.

**Servicios principales:**
- `image_engine` — generación de imágenes con tres backends intercambiables (Leonardo / Grok / ComfyUI), prompts contextualizados con LLM (con historial de los últimos 8 prompts para evitar repetición), upload de imagen de referencia entre imágenes consecutivas para coherencia visual.
- `audio_engine` — TTS con tres providers (ElevenLabs, TikTok TTS y un servicio Coqui XTTSv2 propio en otro contenedor para clonación de voz desde *seeds* de 10s).
- `rendering_engine` — Ken Burns (zoom + paneo) por imagen con MoviePy, post-proceso en FFmpeg con `filter_complex` para overlay de partículas con `colorkey` + loudnorm EBU R128.
- `seo_engine` — generación de título, descripción, tags y *hook* de miniatura por canal con LLM.
- `subtitle_engine` — transcripción con AssemblyAI + burn-in con FFmpeg.
- `style_service` — registro de estilos visuales por canal con prompts positivos/negativos heredables y reglas custom desde un `style-guide.md` por canal.
- `comfy_service` — cliente HTTP del ComfyUI remoto con cola y polling de jobs.
- `youtube_api` / `youtube_dl` — flujo OAuth 2.0 por canal, upload, métricas y descarga de audio para reseed de voz.

**Modelos** — `User`, `UserSettings` (claves API write-only por usuario), `Channel` (con `image_style_prompt`, `negative_prompt`, `default_style`, `default_workflow`), `Video`, `GlobalSettings`.

**Routers** — `auth`, `channels`, `videos` (refactorizado en submódulo + router principal de ~2.200 líneas), `youtube`, `payments`, `admin`, `settings`.

## Funcionalidades implementadas

### Pipeline de generación
- Subida de guion en texto plano, segmentación automática en párrafos.
- Generación de audio por párrafo con concatenación inteligente y *fade* entre tramos.
- Cálculo de duración real por párrafo a partir del audio generado, no del texto.
- Generación dinámica del nº de imágenes por párrafo (1 cada 10s aprox., con cap de 10).
- Caché de prompts e imágenes por hash del párrafo + estilo + workflow → reanudaciones gratis.
- Reanudación granular del pipeline desde cualquier estado intermedio (vídeos atascados → recuperación automática al reiniciar).

### Imágenes
- Tres backends (Leonardo / Grok / ComfyUI local) seleccionables en runtime con coste estimado por modo.
- 17 workflows de ComfyUI temáticos (Cinematic-Horror, Mystical-Cabala, Stock-Senior, Biblical-Epic, Anime-Illustration, Grabovoi-Mystic, Comic-Horror, Dreamy-Oniric, Fast-Standard, Juggernaut-HQ, Upscale-con-HiresFix...) cada uno con sus pesos, *samplers*, embeddings y *negatives* específicos.
- *ImageReviewer* en frontend: regenerar imagen individual, regenerar prompt, eliminar, añadir, convertir imagen a vídeo (Grok grok-imagine-video o Leonardo VEO3).
- Reglas de NSFW por canal con *style-guide.md* (clausulas de "fully clothed", anti-NSFW con prioridad sobre menores, etc.).
- *Init image* entre imágenes del mismo párrafo para mantener consistencia de personaje.

### TTS local con XTTSv2
- Servicio Docker independiente con XTTSv2 (Coqui) corriendo en GPU del Windows.
- Stateless: el backend manda el archivo *seed* en cada petición → no hay estado por servicio.
- Endpoint `/trim-seeds` que recorta automáticamente seeds a 10s.
- Algoritmo propio de *split* de texto largo para evitar tartamudeos en XTTS.
- Detección automática de voces locales (mediante `/voices`) y exposición en frontend junto a las de ElevenLabs y TikTok.

### Render
- Ken Burns con MoviePy (zoom + recorte centrado, modo *pingpong*).
- Soporte mixto: imágenes estáticas y clips de vídeo cortos en el mismo render.
- Música de fondo con *ducking* automático y *fadeout* (boost +60% voz, -94% música).
- Overlay de partículas con `colorkey=black` + loop infinito (`-stream_loop -1`).
- Loudnorm EBU R128 (I=-14 LUFS) en post-proceso.
- Burn-in de subtítulos opcional generados desde el audio con AssemblyAI.
- Progreso en tiempo real escrito a fichero (`render_progress.txt` con fases 0-90 MoviePy → 92 post → 96 subtítulos → 100 fin).
- Tema corporativo por canal (logo de cierre, miniatura, fuentes adaptables a vertical/horizontal).

### YouTube
- OAuth 2.0 por canal con refresh tokens persistidos.
- Upload con metadata generada por LLM (título, descripción, tags) y miniatura propia.
- Listado de vídeos del canal ordenados por vistas (vista en grid / lista / texto plano).
- *Reset* del estado de subida para resubir si la primera vez falló.

### Pagos y multiusuario
- Stripe Checkout para añadir saldo en euros → créditos.
- Tarifa por operación: cada generación de imagen / vídeo / TTS deduce créditos antes de ejecutar.
- Modo bring-your-own-key: el usuario puede meter sus claves de OpenAI/Grok/Leonardo y no consumir créditos.
- Panel de administración con listado de usuarios, alta de créditos manual y métricas globales.

### Operaciones
- Hook de *startup* que recupera vídeos atascados tras reinicio del backend (cualquier vídeo en estado intermedio se mueve al estado seguro previo con un mensaje accionable para el usuario).
- Limpieza global cross-canal de "vídeos huérfanos" (no subidos a YouTube) con filtros por canal/estado/antigüedad, selección múltiple, purga de DB + caché de disco, y acciones rápidas por fila (lanzar render, continuar imágenes, marcar como subido manualmente).
- Endpoint de *cleanup* automático de imágenes optimizables (deduplicación, compresión).

## Episodios técnicos relevantes

### Bug del render truncado a 80 segundos
Síntoma: 8 vídeos subidos a YouTube de varios canales se cortaban al minuto y pico aunque el audio seguía sonando. Ningún error en logs.

Diagnóstico: `ffprobe` reveló que el stream de vídeo duraba 80s (la duración exacta del overlay de partículas) mientras que el audio mantenía los ~9 minutos correctos. El `filter_complex` de FFmpeg incluía `[0:v][ovl]overlay=shortest=1[v_out]`. Como el overlay era más corto que el render principal, `shortest=1` truncaba el output al overlay en lugar de al input principal.

Fix: añadir `-stream_loop -1` antes del input del overlay para hacerlo infinito. El `shortest=1` se mantiene porque también marca el final correcto cuando el render principal acaba primero.

### Bug del event loop bloqueado
Síntoma: la web se quedaba en "Cargando..." al recargarla mientras se estaba generando un vídeo en segundo plano.

Diagnóstico: el bg task de generación de imágenes era `async` pero llamaba síncronamente a `engine.generate_prompts`, `seo.generate_thumbnail_hook` y similares, que internamente hacen `requests.post` a OpenAI/Grok. Cada llamada bloqueaba el único event loop de uvicorn 5-10s por párrafo. Mientras tanto, cualquier `GET /auth/me` quedaba encolado, y el frontend se quedaba congelado en el estado inicial de carga.

Fix: envolver las llamadas síncronas con `await asyncio.to_thread(...)` para que corran en el thread pool por defecto, dejando el event loop libre. Mismo patrón aplicado al pipeline de audio (`run_in_executor`).

### Pérdida de bg tasks tras reinicio
Síntoma: cualquier `docker compose restart` mataba las tareas en curso y los vídeos se quedaban atascados en `generating_audio` / `generating_images` / `rendering` en la base de datos para siempre.

Fix: hook `@app.on_event("startup")` que detecta vídeos en estado intermedio al arrancar y los mueve al estado seguro inmediatamente anterior con un `last_error` accionable explicando al usuario qué botón pulsar para reanudar. Combinado con caché por hash del párrafo, las reanudaciones son casi gratis.

### Voice override sobreescrito por useEffect
Síntoma: la voz seleccionada en el formulario se reseteaba a la primera disponible cada vez que `availableVoices` se actualizaba.

Fix: hacer que el `useEffect` solo establezca el valor por defecto cuando la voz actual no es válida para el provider seleccionado, en lugar de en cada render.

### NSFW slip en canal religioso
Síntoma: una imagen de "San José carpintero" salió con un menor desnudo en el taller.

Fix: pipeline de reglas custom por canal cargadas desde `style-guide.md`, con prioridad para clausulas de protección (NSFW + menores) y refuerzo de "fully clothed" en canales sensibles.

## Decisiones de producto interesantes

- **Vite preview en producción** en lugar de `vite dev`. El usuario deja pestañas abiertas durante horas en el reviewer de imágenes; con HMR la página se reseteaba y perdía el estado al cabo de un tiempo. Build estático servido por preview = pestañas estables.
- **Caché agresiva por hash de párrafo + estilo + workflow.** Las regeneraciones puntuales no rehacen lo que no cambió.
- **Auto-advance** que reanuda desde `audio_ready` aplicando los defaults del canal automáticamente, sin volver a pasar por el formulario.
- **Cada canal puede tener su propio `default_workflow` y `default_style`** y precarga los selectores en el formulario de creación.
- **Toasts inline en vez de `alert()`** en el frontend (regla aprendida la primera vez que apareció uno: "no me metas alerts, los odio"). `confirm()` se mantiene solo para acciones irreversibles (purgar de DB + disco).

## Lo que demuestra

- Diseño y desarrollo full-stack end-to-end de un sistema en producción real (no demo): pipeline con dependencias temporales, estados persistidos, múltiples integraciones de pago.
- Integración de IA generativa multimodal en arquitectura compleja: 3 backends de imagen, 3 de TTS, 2 de LLM, 1 de subtítulos — todos intercambiables.
- Autohospedaje sobre GPU propia (ComfyUI + XTTSv2) con conexión segura desde un VPS Linux a un host Windows por LAN.
- Diagnóstico y fix de bugs sutiles: bloqueo de event loop, ffmpeg filter_complex truncando outputs, bg tasks que no sobreviven reinicios.
- Sensibilidad a UX: progreso en tiempo real, recuperación de fallos sin perder trabajo, regla "no alerts", pre-fill de defaults sensatos por canal, vista cross-channel para limpieza.
- Capacidad de operar y mantener producción en solitario: ya hay vídeos publicados, el sistema funciona y se ha probado con casos reales (incluido descubrir bugs *en producción* y fixearlos sin perder vídeos previamente subidos).
