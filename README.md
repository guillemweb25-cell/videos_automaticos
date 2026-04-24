# Videos Automáticos - AI Video Platform

Plataforma autohospedada para la generación automatizada de vídeos (YouTube Shorts, TikToks, etc.) utilizando IA para guiones, locuciones e imágenes.

## 📚 Documentación Técnica

Para comprender el funcionamiento interno del proyecto, consulta los siguientes documentos:

- **[Arquitectura del Proyecto](docs/PROJECT_ARCHITECTURE.md)**: Visión general, stack tecnológico y estructura de carpetas.
- **[Guía de Instalación y Setup](docs/SETUP_GUIDE.md)**: Cómo levantar el proyecto con Docker y conectar ComfyUI.
- **[Flujos y Workflows](docs/WORKFLOWS_AND_PIPELINES.md)**: Detalle del pipeline asíncrono y la integración con ComfyUI.
- **[Referencia de API](docs/API_REFERENCE.md)**: Endpoints principales del backend.
- **[Variables de Entorno](docs/ENVIRONMENT.md)**: Configuración necesaria en el archivo `.env`.

## 🚀 Inicio Rápido

1. Copia el archivo `.env.example` a `.env` y rellena las API keys.
2. Asegúrate de tener ComfyUI corriendo en el puerto 8188 (o el configurado).
3. Levanta los contenedores:
   ```bash
   docker-compose up -d
   ```
4. Accede al frontend en `http://localhost:8501`.

## 🛠️ Herramientas de Desarrollo
Este proyecto está optimizado para ser gestionado por herramientas de IA como Antigravity, Claude Code o Cursor. Consulta la carpeta `/docs` para obtener el contexto completo.
