# Videos Automáticos - Arquitectura del Proyecto

Este documento está diseñado como **contexto técnico global** para que cualquier Inteligencia Artificial Generativa (LLMs) pueda comprender la estructura, las tecnologías y los flujos de datos de este proyecto antes de realizar cambios o añadir nuevas funcionalidades.

## 1. Visión General
**Videos Automáticos** es una plataforma Full-Stack autohospedada mediante Docker que automatiza la creación de vídeos cortos y largos (estilo "Faceless" o YouTube Shorts / TikToks) a partir de un texto o guion.
Combina múltiples APIs de IA generativa para imágenes y voces, y unifica los recursos multimedia usando un motor de edición de vídeo en Python, ofreciendo una interfaz web moderna para revisar y ajustar los resultados antes del renderizado final.

## 2. Pila Tecnológica (Tech Stack)

### Backend
- **Framework:** FastAPI (Python 3.10+)
- **Base de Datos:** MariaDB (vía SQLAlchemy ORM y Alembic para migraciones)
- **Motor de Vídeo:** MoviePy (Renderizado, Efecto Ken Burns, Overlays con Chroma Key, Concatenación, Subtítulos).
- **Procesamiento de Imágenes:** Pillow (Pillow >= 10.0.0 con parche de compatibilidad `LANCZOS` para MoviePy).
- **APIs Externas:**
  - **Leonardo.Ai:** (Generación de imágenes, incluyendo modelos V1 y V2 como *Nano Banana Pro* - alias `gemini-image-2`).
  - **ElevenLabs:** (Síntesis de voz / TTS).
  - **YouTube Data API v3:** (Subida automatizada de los vídeos finales).

### Frontend
- **Framework:** React con TypeScript.
- **Build Tool:** Vite (sirviendo típicamente en el puerto 8501).
- **Componentes clave:**
  - `VideoCreator.tsx`: Formulario principal para configurar el canal, resolución (vertical 9:16 vs horizontal 16:9), guion y subtítulos.
  - `ImageReviewer.tsx`: Modal avanzado para revisar imagen a imagen, regenerar prompts con IA, sustituir imágenes, seleccionar Overlays y renderizar.
  - `api.ts`: Cliente HTTP fuertemente tipado que se comunica con el Backend.

### Infraestructura & Despliegue
- **Docker Compose:** Define 3 servicios principales:
  1. `api`: Contenedor Python con el backend FastAPI (expuesto en puertos internos/externos).
  2. `db`: Contenedor MariaDB con volúmenes persistentes.
  3. `frontend`: Contenedor Node/Vite.
- **Volúmenes compartidos:**
  - `./overlay`: Carpeta montada en caliente para añadir archivos de vídeo que sirvan como capas de superposición (`overlay_retro_01.mp4`).
  - Carpeta de Caché (`/cache` o `./downloads/`): Donde se guardan temporalmente los fragmentos de audio (`chunk_001.mp3`), imágenes y vídeos renderizados.

## 3. Arquitectura del Backend (`backend/app/`)

El backend sigue un patrón modular claro MVC + Servicios:

- **`routers/`**: Controladores de FastAPI (`video_gen.py`, `youtube.py`). Orquestan las peticiones del frontend.
- **`models/`**: Modelos de SQLAlchemy (`Video`, `Channel`).
- **`schemas/`**: Validadores Pydantic.
- **`services/`**: Donde reside la lógica de negocio pesada.
  - `image_engine.py`: Encargado de hablar con Leonardo.Ai. Ajusta de forma dinámica las dimensiones (ej. obligando a `848x1264` para Nano Banana Pro en vertical).
  - `audio_engine.py`: Encargado de consumir ElevenLabs y gestionar la línea de tiempo (segundos de duración por párrafo).
  - `rendering_engine.py`: El corazón de MoviePy. Recibe las rutas estáticas de audio e imágenes, aplica transiciones o Ken Burns, inserta archivos del directorio `overlay/` con `vfx.mask_color` transparente, y "plancha" los subtítulos si se requieren.
  - `seo_engine.py`: Para metadatos de YouTube.

## 4. Flujo de Datos Principal (Generación de Vídeo)

1. **Configuración y Guion (Frontend)**
   - El usuario elige Canal, Guion, Orientación (Vertical/Horizontal), Estilo visual y Modelo de IA.
2. **Generación de Assets Multiservicio (`POST /{video_id}/render` o pasos previos)**
   - El guion se separa por párrafos.
   - El backend solicita los audios a ElevenLabs. La duración de esos audios marca exactamente cuánto durará la imagen estática generada por Leonardo.Ai en la pantalla.
3. **Revisión Humana (ImageReviewer)**
   - El usuario entra al modal de revisión. Mira los fotogramas, escucha el audio de cada párrafo, elimina, añade o repite prompts para pulir detalles.
4. **Renderizado Final y Ensamblaje (`RenderingEngine`)**
   - Cuando el usuario hace click en "Finalizar y Renderizar":
     - MoviePy construye `ImageClip` a partir de las fotos.
     - Ajusta sus duraciones a los fragmentos `.mp3` de ElevenLabs.
     - (Opcional) Crea un `VideoFileClip` de un overlay (ej. polvo retro de película) y hace un loop encima de todas las capas ignorando el fondo negro (`[0,0,0]`).
     - (Opcional) Usa un creador de generador de texto (ej. ImageMagick o TextClip) para imprimir subtítulos dinámicos de Karaoke.
     - Ejecuta `write_videofile` exportando el MP4 final.

## 5. Notas Importantes para IA

- **MoviePy & Pillow:** Dado que MoviePy 1.0.3 tiene dependencias legacy de Pillow, el backend incluye un parche dinámico (`Image.ANTIALIAS = Image.Resampling.LANCZOS`) en tiempo de ejecución.
- **Soporte Leonardo v2:** Usa soporte V2 para permitir ControlNet o *Image Guidance*.
- **Subtítulos:** Generan variables en las query strings, al igual que los overlays (ej. `?subtitles=true&overlay=overlay_retro.mp4`).
- **Montaje Local:** Usa rutas absolutas y relativas dentro de la red Docker. Cualquier archivo subido al backend o almacenado en la caché es referenciado a través de un ID estructurado por el Canal y Título del vídeo en la base de datos MariaDB.
