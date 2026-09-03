import os
import subprocess
from pathlib import Path

from yt_dlp import YoutubeDL

DOWNLOAD_BASE = Path("/app/cache/youtube_downloads")

class YouTubeDLService:
    @staticmethod
    def scan_channel(
        url_or_handle: str,
        max_videos: int = 200,
        lang: str = "es",
        fetch_views_individually: bool = True,
    ) -> list:
        """
        Lists a public YouTube channel's videos (no OAuth needed). Uses
        yt-dlp's Python API in flat mode so we get title + view count +
        duration without fetching each video page.

        Accepts: full URL ("https://youtube.com/@handle"), bare handle
        ("@handle" or "handle"), or a /videos URL.

        Params:
          - lang: ISO language code for HTTP Accept-Language. YouTube
            auto-translates titles for viewers in other locales, so we have
            to ask for the original-language version explicitly. Defaults
            to Spanish since the app's primary audience is Hispanohablante.
          - fetch_views_individually: when True, do a per-video metadata
            fetch for any video whose view_count came back null from the
            flat listing (some channels / YouTube A/B tests don't include
            view_count inline). Adds ~50-200ms per missing video.

        Returns: list of {video_id, title, view_count, duration_seconds,
        upload_date (YYYYMMDD or None), url}.
        """
        u = (url_or_handle or "").strip()
        if not u:
            raise ValueError("URL o handle vacío")

        if u.startswith("@"):
            u = f"https://www.youtube.com/{u}/videos"
        elif "youtube.com" not in u and "youtu.be" not in u:
            # bare handle without @
            u = f"https://www.youtube.com/@{u}/videos"
        elif "/videos" not in u and "/shorts" not in u and "/streams" not in u:
            # channel root → point at /videos tab
            u = u.rstrip("/") + "/videos"

        # Headers: tell YouTube we want the channel's native language so we
        # don't get auto-translated titles back. Without this, YouTube
        # serves English by default to bots without Accept-Language.
        headers = {
            "Accept-Language": f"{lang}-ES,{lang};q=0.9,en;q=0.5",
        }

        opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "playlistend": int(max_videos),
            "skip_download": True,
            "http_headers": headers,
            "extractor_args": {
                # Pass language hint to YouTube's tab extractor too — some
                # versions of yt-dlp respect this for localized strings.
                "youtubetab": {"lang": [lang]},
                "youtube": {"lang": [lang]},
            },
        }

        print(f"[scan_channel] fetching listing: {u}", flush=True)
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(u, download=False)

        entries = (info or {}).get("entries") or []
        print(f"[scan_channel] listing returned {len(entries)} entries", flush=True)
        results = []
        for e in entries:
            if not e:
                continue
            vid = e.get("id")
            results.append({
                "video_id": vid,
                "title": e.get("title"),
                "view_count": e.get("view_count"),
                "duration_seconds": e.get("duration"),
                "upload_date": e.get("upload_date"),
                "url": f"https://www.youtube.com/watch?v={vid}" if vid else None,
            })

        # Fallback: if view_count is null for some/all entries, fetch each
        # missing video individually. Some channels don't expose view_count
        # in the flat listing — only on the video page itself. We cap the
        # extra fetches to keep response time bounded.
        if fetch_views_individually:
            missing = [r for r in results if r["view_count"] is None and r["video_id"]]
            if missing:
                detail_opts = {
                    "quiet": True,
                    "no_warnings": True,
                    "skip_download": True,
                    "http_headers": headers,
                    "extractor_args": opts["extractor_args"],
                }
                # Cap at 30 detail fetches: keeps the worst-case wait under
                # ~10s for a totally view-less listing while still covering
                # the most recent videos (which is what researchers want).
                MAX_DETAIL_FETCHES = 30
                print(f"[scan_channel] {len(missing)} videos missing view_count, "
                      f"fetching detail for first {min(len(missing), MAX_DETAIL_FETCHES)}",
                      flush=True)
                with YoutubeDL(detail_opts) as ydl:
                    for i, r in enumerate(missing[:MAX_DETAIL_FETCHES]):
                        try:
                            d = ydl.extract_info(r["url"], download=False)
                            r["view_count"] = d.get("view_count")
                            # Also pull upload_date if it was missing
                            if not r["upload_date"]:
                                r["upload_date"] = d.get("upload_date")
                            # And use the original (not auto-translated) title
                            # if we got a different / richer one back.
                            orig_title = d.get("title")
                            if orig_title and orig_title != r["title"]:
                                r["title"] = orig_title
                            if (i + 1) % 5 == 0:
                                print(f"[scan_channel] detail fetch progress: {i+1}/{min(len(missing), MAX_DETAIL_FETCHES)}", flush=True)
                        except Exception as ex:
                            print(f"[scan_channel] detail fetch failed for {r['video_id']}: {ex}", flush=True)

        return results


    @staticmethod
    def download_audio(url: str, channel_name: str) -> str:
        """
        Descarga el audio de un vídeo de YouTube en formato MP3.
        Retorna la ruta al archivo descargado.
        """
        output_dir = DOWNLOAD_BASE / channel_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Plantilla del nombre de archivo: %(title)s.%(ext)s
        output_template = str(output_dir / "%(title)s.%(ext)s")
        
        command = [
            "yt-dlp",
            "-x", # Extract audio
            "--audio-format", "mp3",
            "--audio-quality", "0", # Best quality
            "-o", output_template,
            url
        ]
        
        try:
            # Ejecutamos el comando
            subprocess.run(command, check=True, capture_output=True, text=True)
            
            # Buscamos el archivo generado (yt-dlp no nos da la ruta exacta fácilmente si hay caracteres raros)
            # Una forma simple es buscar el archivo más reciente en la carpeta
            files = list(output_dir.glob("*.mp3"))
            if not files:
                raise Exception("No se encontró el archivo MP3 después de la descarga.")
            
            latest_file = max(files, key=os.path.getctime)
            return str(latest_file)
            
        except subprocess.CalledProcessError as e:
            print(f"Error al descargar: {e.stderr}")
            raise Exception(f"Error de yt-dlp: {e.stderr}")

    @staticmethod
    def download_video(url: str, channel_name: str) -> dict:
        """Descarga el VÍDEO completo (mejor calidad, muxado a MP4) de un
        enlace de YouTube y devuelve la ruta + metadatos listos para reubir
        (título, descripción, etiquetas). Pensado para el flujo "mirror":
        bajar de YouTube y subir a mano a otra plataforma (Bilibili).

        Usa la API de Python de yt-dlp (no subprocess) para poder recuperar de
        forma fiable la ruta final del fichero muxado y los metadatos.
        """
        output_dir = DOWNLOAD_BASE / channel_name
        output_dir.mkdir(parents=True, exist_ok=True)

        opts = {
            # bv*+ba = mejor vídeo + mejor audio (se muxan); /b = fallback a un
            # único stream ya combinado si no hay separados.
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
            # %(title).150B recorta el título a 150 bytes para no petar rutas
            # largas en Windows; incluimos el id para evitar colisiones.
            "outtmpl": str(output_dir / "%(title).150B [%(id)s].%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "restrictfilenames": False,
            # YouTube devuelve 403 en el stream con el cliente web por defecto;
            # los clientes de móvil/apple entregan URLs de descarga válidas.
            # yt-dlp prueba estos en orden y usa el primero con formatos válidos.
            "extractor_args": {"youtube": {"player_client": ["android", "ios", "web_safari"]}},
        }

        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)

        # Resolver la ruta final del fichero (tras el mux a mp4).
        file_path = None
        reqs = info.get("requested_downloads") or []
        if reqs:
            file_path = reqs[0].get("filepath") or reqs[0].get("_filename")
        if not file_path:
            # Fallback: el .mp4 más reciente de la carpeta del canal.
            mp4s = list(output_dir.glob("*.mp4"))
            if mp4s:
                file_path = str(max(mp4s, key=os.path.getctime))
        if not file_path or not os.path.exists(file_path):
            raise Exception("No se encontró el vídeo descargado tras el mux.")

        return {
            "file_path": file_path,
            "id": info.get("id"),
            "title": info.get("title") or "",
            "description": info.get("description") or "",
            "tags": info.get("tags") or [],
            "categories": info.get("categories") or [],
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
            "original_url": info.get("webpage_url") or url,
        }

    @staticmethod
    def video_info(url: str) -> dict:
        """Extrae metadatos de un vídeo de YouTube SIN descargarlo (rápido):
        título, descripción, etiquetas, miniatura y duración. Para la ficha
        previa antes de decidir descargar el MP4."""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "skip_download": True,
            "extractor_args": {"youtube": {"player_client": ["android", "ios", "web_safari"]}},
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Elegir la mejor miniatura disponible (mayor resolución al final de la
        # lista); fallback al campo 'thumbnail' que ya elige yt-dlp.
        thumb = info.get("thumbnail")
        thumbs = info.get("thumbnails") or []
        if thumbs:
            best = thumbs[-1].get("url")
            if best:
                thumb = best

        return {
            "id": info.get("id"),
            "title": info.get("title") or "",
            "description": info.get("description") or "",
            "tags": info.get("tags") or [],
            "categories": info.get("categories") or [],
            "duration": info.get("duration"),
            "view_count": info.get("view_count"),
            "thumbnail": thumb,
            "original_url": info.get("webpage_url") or url,
        }

    @staticmethod
    def list_downloads(channel_name: str):
        output_dir = DOWNLOAD_BASE / channel_name
        if not output_dir.exists():
            return []
        # Support both name and full path for debugging
        return [{"name": f.name, "path": str(f)} for f in output_dir.glob("*.mp3")]
