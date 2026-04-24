# Referencia de API (Backend)

La API está construida con **FastAPI** y utiliza autenticación basada en usuario.

## 1. Endpoints de Generación de Vídeo (`/api/videos`)

### `GET /config`
Retorna la configuración disponible:
- Voces (TikTok, ElevenLabs).
- Estilos de imagen.
- Modelos de Leonardo.Ai.
- Modos de generación (FAST, QUALITY, COMFYUI).

### `GET /workflows`
Retorna la lista de archivos `.json` disponibles en la carpeta `/workflows`.

### `POST /`
Crea un nuevo proyecto de vídeo. Recibe el guion, canal, voz y configuración inicial.

### `POST /{video_id}/generate-images`
Inicia la generación de imágenes en segundo plano.
- **Asíncrono**: Devuelve `202 Accepted`.
- **Lógica**: Si el modo es `COMFYUI`, utiliza `ComfyService`.

### `POST /{video_id}/render`
Inicia el renderizado final del vídeo mediante MoviePy.

### `GET /{video_id}`
Retorna el estado completo de un vídeo (progreso, assets generados, metadatos).

## 2. Endpoints de Overlays (`/api/videos/overlays`)

### `GET /`
Lista los archivos de vídeo disponibles en la carpeta `/overlay` para ser usados como capas.

## 3. Endpoints de YouTube (`/api/youtube`)

### `POST /{video_id}/upload`
Sube el vídeo renderizado a YouTube utilizando las credenciales del canal.

### `GET /auth-url`
Genera la URL de OAuth2 para vincular un canal de YouTube.

## 4. Notas Técnicas
- **Autenticación**: La mayoría de los endpoints requieren un token de usuario (`get_current_user`).
- **CORS**: Configurado para permitir peticiones desde el frontend en desarrollo y producción.
