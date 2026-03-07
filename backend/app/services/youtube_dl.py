import os
import subprocess
from pathlib import Path

DOWNLOAD_BASE = Path("/app/cache/youtube_downloads")

class YouTubeDLService:
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
    def list_downloads(channel_name: str):
        output_dir = DOWNLOAD_BASE / channel_name
        if not output_dir.exists():
            return []
        # Support both name and full path for debugging
        return [{"name": f.name, "path": str(f)} for f in output_dir.glob("*.mp3")]
