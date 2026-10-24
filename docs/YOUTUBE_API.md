# Integración con YouTube

Cómo conecta la app con YouTube: conexión de cada canal (OAuth), subida de vídeos, gestión de
vídeos ya subidos y lectura de la información de los canales.

Hay **dos vías** distintas para hablar con YouTube:

| Vía | Para qué | Necesita login de Google |
|---|---|---|
| **YouTube Data API v3** (`google-api-python-client`) | Subir, editar, poner miniaturas, leer *tu* canal | Sí, OAuth por canal |
| **yt-dlp** (scraping) | Escanear canales públicos ajenos, descargar vídeos/audio para repost | No |

Archivos principales:

| Archivo | Qué contiene |
|---|---|
| `backend/app/services/youtube_api.py` | `YouTubeService`: credenciales, OAuth, llamadas a la Data API |
| `backend/app/routers/youtube.py` | Endpoints `/youtube/...`: info del canal, listados, subida, edición |
| `backend/app/routers/channels.py` | Endpoints `/channels/{id}/youtube/...`: subir `client_secret.json`, OAuth |
| `backend/app/services/youtube_dl.py` | yt-dlp: escaneo de canales públicos y descargas |
| `frontend/src/components/ChannelDashboard.tsx` | Botones de vincular cuenta y callback de OAuth |
| `frontend/src/components/VideoUploadModal.tsx` | Modal «Publicar en YouTube» (subir / sincronizar / miniatura) |

---

## 1. Conexión de un canal (OAuth 2.0)

Cada canal de la app tiene **su propia cuenta de YouTube** y sus propias credenciales. No hay
un login global: un canal = un proyecto OAuth (o el mismo proyecto reutilizado) + un token.

### 1.1 Dónde se guardan las credenciales

```
cache/user_<id>/<NNNN>-<slug-canal>/youtube_credentials/
├── client_secret.json   ← credenciales de la app OAuth (las descargas de Google Cloud)
└── token.json           ← token del usuario (access + refresh), lo escribe la app
```

`YouTubeService.get_creds_dir(channel_id, user_id, channel_name)` busca la carpeta del canal
por su prefijo numérico (`0002-*`) y crea `youtube_credentials/` si no existe. Ninguno de los
dos ficheros va a git (`cache/` está ignorado).

### 1.2 Preparación en Google Cloud (una vez por proyecto)

1. En [Google Cloud Console](https://console.cloud.google.com/) crea un proyecto y activa
   **YouTube Data API v3**.
2. Pantalla de consentimiento OAuth: tipo *Externo*; añade la cuenta de Google del canal como
   usuario de prueba mientras la app esté en modo *Testing*.
3. Credenciales → **ID de cliente OAuth** de tipo **Aplicación web**.
4. **URI de redirección autorizada**: el *origen* del frontend **con barra final**, que es lo
   que manda la app:
   - `https://ytauto.enguillem.es/`
   - (y si se usa en LAN) `http://192.168.1.46:8501/`
5. Descarga el JSON → es el `client_secret.json`.

> Si la URI no coincide exactamente (http/https, puerto, barra final) Google devuelve
> `redirect_uri_mismatch`.

### 1.3 Scopes que pide la app

Definidos en `SCOPES` (`youtube_api.py`):

| Scope | Para qué |
|---|---|
| `youtube.upload` | `videos.insert` (subir) |
| `youtube.readonly` | leer canal, listas y vídeos |
| `youtube.force-ssl` | `videos.update` y `thumbnails.set` en vídeos **ya subidos** (sin él: 403 *Insufficient Permission*) |
| `userinfo.email`, `userinfo.profile`, `openid` | identificar la cuenta |

`OAUTHLIB_RELAX_TOKEN_SCOPE=1` evita errores cuando Google devuelve los scopes en otro formato.
Si se añade un scope nuevo, los canales ya vinculados tienen que **volver a autorizar**.

### 1.4 Flujo de vinculación (paso a paso)

```
Usuario (dashboard del canal)            Backend                         Google
──────────────────────────────           ───────                         ──────
1. "Seleccionar archivo" client_secret ─▶ POST /channels/{id}/youtube/client-secret
                                          guarda client_secret.json
2. "Vincular con Google" ───────────────▶ GET /channels/{id}/youtube/auth-url?redirect_uri=<origen>/
                                          construye la URL (access_type=offline,
                                          prompt=consent, include_granted_scopes,
                                          state=channel:<id>)
   ◀──────────── { auth_url } ───────────
3. window.location = auth_url ───────────────────────────────────────────▶ login + permisos
4. ◀──────────── redirige a <origen>/?code=XXXX&state=channel:<id> ──────────
5. ChannelDashboard lee ?code y ?state, limpia la URL y llama (con el id del state):
   ─────────────────────────────────────▶ POST /channels/youtube/callback?code&channel_id&redirect_uri
                                          Flow.fetch_token(code) → escribe token.json
6. "¡Cuenta vinculada correctamente!" y recarga los datos de YouTube del canal
```

Detalles:

- La URL de autorización se monta a mano (no con `Flow.authorization_url`) para evitar el PKCE
  automático de `google-auth-oauthlib`; el intercambio del código sí usa `Flow`.
- `access_type=offline` + `prompt=consent` garantizan que Google entregue **refresh token**.
- El canal que inicia la vinculación viaja en el **`state`** de OAuth (`channel:<id>`): al volver
  de Google el token se guarda en ese canal aunque el dashboard abierto sea otro.
- El callback exige usuario logueado y que el canal sea suyo.
- Si un canal no tiene `client_secret.json`, se copia el global `backend/youtube_creds/client_secret.json`
  (si existe); si tampoco existe, la app responde «Falta el archivo client_secret.json».

### 1.5 Uso y renovación del token

`YouTubeService.get_credentials()` se llama antes de cada operación:

1. Carga `token.json`.
2. Si está caducado y hay refresh token → `creds.refresh()` y reescribe `token.json`.
3. Si el refresh falla (`RefreshError`: token revocado, contraseña cambiada, app en *Testing*
   más de 7 días…) **borra `token.json`** y devuelve `None` → la app pide volver a vincular
   («Not authenticated with YouTube» / «No se pudo autenticar con YouTube»).

> En modo *Testing* de la pantalla de consentimiento, Google caduca los refresh tokens a los
> 7 días. Para que no caduquen, publica la app OAuth (modo *In production*).

---

## 2. Subir un vídeo

Desde **Mis Generaciones → Subir a YouTube** se abre `VideoUploadModal`. Al pulsar subir:

```
POST /youtube/{video_id}/upload
body: { title, description, tags, privacy_status, publish_at? }
```

`upload_video_to_youtube` (router) → `YouTubeService.upload_video()`:

1. Comprueba que existe `<base_dir>/output/final_video.mp4`.
2. **Limpia las etiquetas**: separa por comas, quita `?` y `¿`, corta cada etiqueta a 100
   caracteres y el total a < 500 (límites de YouTube).
3. Cuerpo de `videos.insert` (`part=snippet,status`):
   ```json
   {
     "snippet": { "title": "...", "description": "...", "tags": [...], "categoryId": "22" },
     "status":  { "privacyStatus": "private|unlisted|public", "selfDeclaredMadeForKids": false,
                  "publishAt": "2026-11-01T08:00:00Z" }
   }
   ```
   - `categoryId` 22 = *People & Blogs* (fijo).
   - **Programado**: si llega `publish_at`, YouTube exige `private`; si se pidió `public` se
     cambia a `private` y YouTube lo publica a esa hora.
4. **Subida reanudable** (`MediaFileUpload(resumable=True)` + `next_chunk()`), con progreso en
   los logs del contenedor.
5. Guarda en la BD `youtube_video_id` e `is_uploaded = True`.
6. Si existe `<base_dir>/output/thumbnail.png` → `thumbnails.set` (ver §4).
7. **Shorts promocionales** (vídeos con `promo_plan.json`): manda un Telegram y devuelve
   `related_video` con el vídeo largo para enlazarlo a mano (ver §5).

La descripción de los vídeos nuevos lleva delante el bloque fijo del canal
(`channels.description_header`, p. ej. el enlace del libro de afiliado).

---

## 3. Gestionar vídeos ya subidos

Si el vídeo ya tiene `is_uploaded`, el mismo modal pasa a **«Sincronizar Cambios»**:

```
POST /youtube/{video_id}/update-metadata
body: { title, description, tags }
```

`update_video_metadata()` hace `videos.update(part="snippet")` con título, descripción,
etiquetas (mismas reglas de limpieza) y `categoryId`. Después:

- guarda título/descripción/etiquetas en la BD;
- vuelve a subir `thumbnail.png` con `thumbnails.set`.

Qué **no** se puede cambiar desde aquí: privacidad y programación (solo al subir).

Otros endpoints relacionados:

| Endpoint | Qué hace |
|---|---|
| `GET /youtube/{id}/metadata` | Datos para el modal: título, descripción, etiquetas, miniatura, `is_uploaded`, `youtube_video_id`, cabecera del canal, `thumbnail_hook`, `is_short`, `related_video` |
| `POST /youtube/{id}/reset-upload` | **Solo local**: marca el vídeo como no subido (para volver a subirlo). **No borra nada en YouTube.** |
| `POST /youtube/{id}/regenerate/title` · `/description` · `/tags` | SEO con LLM (no toca YouTube hasta sincronizar) |

> **Error 403 al sincronizar**: el canal se vinculó sin `youtube.force-ssl`. Solución:
> volver a vincular la cuenta desde la configuración del canal.

---

## 4. Miniaturas

`YouTubeService.set_thumbnail(video_id, path)` → `thumbnails.set`:

- Límite de YouTube: **2 MB**. Si el PNG pesa más, se convierte a JPEG bajando la calidad de 5
  en 5 hasta que quepa (fichero temporal `__tmp_thumb_<id>.jpg`, se borra después).
- La cuenta tiene que estar **verificada** en YouTube para poder poner miniaturas
  personalizadas.
- Se llama al subir y al sincronizar. Las miniaturas se generan en la app (IA + texto, o
  plantillas HyperFrames: `POST /videos/{id}/thumbnail-motion`).

---

## 5. Shorts: lo que la API NO permite

YouTube decide que un vídeo es Short por su formato (vertical y corto); se sube igual que uno
normal. Pero la Data API **no expone**:

- **Vídeo relacionado** (el enlace del Short al vídeo largo).
- **Miniatura del Short**: en la práctica `thumbnails.set` no se refleja en el reproductor de
  Shorts; la portada se elige como fotograma desde la app de YouTube.

Cómo lo resuelve la app:

1. Los shorts promocionales terminan con **2 s de portada fija** (diseñable en vertical desde el
   modal con HyperFrames → «Meter portada en el vídeo»).
2. Al subir un short, la app avisa en pantalla y por **Telegram** del vídeo largo a enlazar.
3. Se termina a mano en la **app de YouTube del móvil** → editar el short:
   miniatura = un fotograma de la portada; vídeo relacionado = el largo.
4. Si el largo ya está subido al crear el short, su enlace va también al final de la
   descripción (`▶ Vídeo completo: https://youtu.be/…`).

---

## 6. Leer la información de los canales

### 6.1 Tu canal (Data API, con OAuth)

| Endpoint | Llamadas a la API | Devuelve |
|---|---|---|
| `GET /youtube/channel/{channel_id}` | `channels.list(part=snippet,statistics, mine=true)` | El recurso del canal (título, suscriptores, vistas, nº vídeos…). 401 si no hay token válido |
| `GET /youtube/videos/{channel_id}?max_results=50&min_seconds=120&exclude_title_tags=#short,#shorts` | ver abajo | Vídeos largos (> `min_seconds`, sin `#short` en el título) |
| `GET /youtube/shorts/{channel_id}?max_results=50` | ver abajo | Vídeos de ≤ 120 s |

`get_videos()`:

1. `channels.list(part=contentDetails, mine=true)` → ID de la lista **uploads** del canal.
2. `playlistItems.list` paginado (50 por página) hasta `max_results` → IDs de vídeo.
3. `videos.list(part=snippet,contentDetails,statistics)` en bloques de 50 → título, miniatura
   `medium`, fecha, **duración** (ISO 8601 `PT#H#M#S` → segundos) y visualizaciones.

Esto alimenta las pestañas **General / Vídeos / Shorts** del dashboard del canal.

### 6.2 Canales públicos ajenos (yt-dlp, sin OAuth)

| Endpoint | Qué hace |
|---|---|
| `POST /youtube/scan-public-channel` `{url, max_videos}` | Lista los vídeos de cualquier canal público (`@handle` o `/channel/UC…`): título, vistas, duración, fecha, URL. Para análisis de competencia («Analizar Canal») |
| `POST /youtube/download/{channel_id}?url=` · `GET /youtube/downloads/{channel_id}` | Descarga de audio (YouTube a MP3) |
| `/repost/{channel_id}/info` · `/thumbnail` · `/download` · `/downloads` · `/file` | Repost: metadatos, miniatura (PNG), descarga del MP4 con `player_client=android` para evitar 403 |

No consumen cuota de la API, pero dependen de que yt-dlp siga funcionando con YouTube
(actualizar `yt-dlp` si empiezan a fallar).

---

## 7. Cuota de la API

Cuota por defecto: **10.000 unidades/día por proyecto de Google Cloud** (se comparte entre
todos los canales que usen el mismo `client_secret.json`). Coste aproximado de lo que usa la
app (consulta la tabla oficial de cuotas: Google la cambia de vez en cuando):

| Operación | Coste aprox. |
|---|---|
| `videos.insert` (subir) | ~1.600 |
| `thumbnails.set` | 50 |
| `videos.update` (sincronizar) | 50 |
| `channels.list`, `playlistItems.list`, `videos.list` | 1 cada una |

Es decir, unas **6 subidas al día por proyecto**. Con más canales conviene repartirlos en
varios proyectos de Google Cloud (un `client_secret.json` distinto por grupo de canales) o
pedir ampliación de cuota.

---

## 8. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| «No has conectado este canal con YouTube (o el token caducó)» | No hay `token.json` o el refresh falló y se borró | Vincular de nuevo desde el dashboard del canal |
| `redirect_uri_mismatch` | La URI de Google Cloud no es exactamente `https://<dominio>/` | Añadir la URI exacta con barra final |
| 403 *Insufficient Permission* al sincronizar o poner miniatura | Token sin `youtube.force-ssl` | Volver a vincular |
| `quotaExceeded` | Cuota diaria agotada | Esperar al reinicio (medianoche hora del Pacífico) o usar otro proyecto |
| La miniatura no cambia | Cuenta no verificada, o es un Short | Verificar la cuenta / en Shorts, desde la app móvil |
| «Falta el archivo client_secret.json» | No se subió el JSON para ese canal | Subirlo en «Vincular cuenta de YouTube» |

---

## 9. Cambios hechos al documentar (2026-10-24)

Se corrigieron cuatro fallos encontrados al escribir este documento:

- `GET /channels/{id}/youtube/info` creaba `YouTubeService` con un solo argumento (habría
  fallado); ahora usa `(channel_id, user_id, channel_name)` como el resto.
- `get_auth_url()` usaba `YOUTUBE_CREDS_BASE` sin definir (500 en vez del aviso de
  «Falta el archivo client_secret.json»); ahora está definida (`/app/youtube_creds`).
- El canal del callback OAuth sale del `state` (`channel:<id>`), no del dashboard abierto.
- `POST /channels/youtube/callback` exige usuario autenticado y dueño del canal.
