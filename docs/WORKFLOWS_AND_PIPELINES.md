# Flujos y Pipelines - Detalle Técnico

Este documento detalla el pipeline de generación de vídeo, enfocado en el procesamiento asíncrono y la integración con ComfyUI.

## 1. Pipeline de Generación de Imágenes (ComfyUI)

El sistema utiliza ComfyUI como motor principal de generación debido a su flexibilidad y capacidad de usar modelos locales (NSFW allowed, SDXL, LoRAs).

### Flujo de Ejecución:
1. **Petición del Usuario**: El frontend envía el `workflow_name` (ej. `Biblical-Epic.json`) y el prompt base.
2. **Carga de Plantilla**: `ComfyService` carga el archivo `.json` desde `/workflows`.
3. **Inyección de Prompts**: Se buscan los nodos de texto (usualmente CLIP Text Encode) y se reemplaza el contenido por el prompt generado por la IA (combinado con el estilo seleccionado).
4. **Envío a la API**: Se realiza una petición POST asíncrona al endpoint `/prompt` de ComfyUI.
5. **Monitorización (Polling/WebSocket)**: El servicio espera a que la imagen se genere y la descarga a la caché local.

## 2. Arquitectura Asíncrona (FastAPI + Asyncio)

Para evitar que el backend se bloquee mientras espera a ComfyUI o ElevenLabs, se ha implementado un sistema de tareas en segundo plano.

### Tareas en Segundo Plano (`asyncio.create_task`):
Cuando el usuario inicia una generación de imágenes o SEO, el router no espera a que termine. En su lugar:
1. Crea una tarea asíncrona.
2. Devuelve un `202 Accepted` al frontend.
3. El frontend monitoriza el estado consultando periódicamente el endpoint del vídeo.

### Ventajas:
- **Escalabilidad**: Se pueden lanzar múltiples generaciones simultáneamente.
- **Resiliencia**: Si una generación falla, el servidor sigue respondiendo a otras peticiones.
- **UX**: La interfaz no se congela y puede mostrar barras de progreso reales.

## 3. Renderizado de Vídeo (MoviePy)

El renderizado final ocurre en `RenderingEngine`:
1. **Sincronización Audio-Imagen**: Cada párrafo tiene una duración exacta dictada por el audio de ElevenLabs.
2. **Efectos Visuales**: Se aplica el efecto Ken Burns (zoom suave) a las imágenes estáticas.
3. **Overlays**: Se superponen vídeos con fondo negro utilizando `vfx.mask_color` para lograr efectos de partículas o texturas.
4. **Subtítulos**: Se generan archivos `.ass` o se "queman" directamente en el vídeo usando ImageMagick.
