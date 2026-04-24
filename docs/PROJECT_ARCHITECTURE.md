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
- **APIs Externas y Motores:**
  - **ComfyUI (Local/Remoto):** Motor principal de generación de imágenes mediante workflows dinámicos JSON. Permite alta calidad (SDXL/Juggernaut) y control total sin censura.
  - **Leonardo.Ai:** (Motor secundario/legacy para generación de imágenes).
  - **ElevenLabs:** (Síntesis de voz / TTS).
  - **YouTube Data API v3:** (Subida automatizada de los vídeos finales).

### Frontend
- **Framework:** React con TypeScript.
- **Build Tool:** Vite.
- **Componentes clave:**
  - `VideoCreator.tsx`: Formulario principal para configurar el canal, resolución, guion y **selección de Workflow de ComfyUI**.
  - `ImageReviewer.tsx`: Modal avanzado para revisar imagen a imagen, regenerar prompts con IA, sustituir imágenes, seleccionar Overlays y renderizar.
  - `api.ts`: Cliente HTTP fuertemente tipado que se comunica con el Backend.

### Infraestructura & Despliegue
- **Docker Compose:** Define 3 servicios principales:
  1. `api`: Contenedor Python con el backend FastAPI.
  2. `db`: Contenedor MariaDB con volúmenes persistentes.
  3. `frontend`: Contenedor Node/Vite.
- **Volúmenes compartidos:**
  - `./overlay`: Carpeta montada en caliente para vídeos de superposición.
  - `./cache`: Carpeta de caché persistente para audios, imágenes y renders.

## 3. Arquitectura del Backend (`backend/app/`)

El backend utiliza una arquitectura **100% asíncrona** para evitar bloqueos del event loop:

- **`routers/`**: Controladores de FastAPI. `video_gen.py` orquesta la generación lanzando tareas en segundo plano (`asyncio.create_task`).
- **`services/`**:
  - `comfy_service.py`: Cliente asíncrono para interactuar con ComfyUI.
  - `image_engine.py`: Orquestador de generación de imágenes (ComfyUI / Leonardo).
  - `audio_engine.py`: Gestión de TTS con ElevenLabs.
  - `rendering_engine.py`: Ensamblaje de vídeo con MoviePy.
  - `seo_engine.py`: Generación asíncrona de metadatos (Títulos, Descripciones) mediante IA.

## 4. Flujo de Datos Principal (Generación de Vídeo)

1. **Configuración (Frontend)**: El usuario elige estilo, guion y el **Workflow de ComfyUI** deseado.
2. **Generación Asíncrona**: 
   - El backend genera el audio y calcula los tiempos por párrafo.
   - Se lanza una tarea en segundo plano que consume la API de ComfyUI enviando el prompt positivo/negativo inyectado en el JSON del workflow.
3. **Caché Persistente**: Los resultados se guardan en `/cache` organizados por `user_id/channel_id/video_id`.
4. **Revisión y Render**: El usuario valida los assets y MoviePy genera el MP4 final.

## 5. Notas Importantes para IA

- **Async Everywhere**: No utilizar funciones bloqueantes en los routers. Siempre usar `async/await` o `run_in_executor`.
- **Workflow Templates**: Los archivos `.json` en `/workflows` son plantillas. El backend reemplaza tokens específicos (como el prompt) antes de enviarlos a ComfyUI.
- **Pillow Patch**: Se mantiene el parche `Image.ANTIALIAS` para compatibilidad con MoviePy en `image_engine.py` y `rendering_engine.py`.
- **ComfyUI URL**: Se configura vía `.env` (puerto default 8188).
