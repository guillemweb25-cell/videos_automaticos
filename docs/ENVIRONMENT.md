# Variables de Entorno y Configuración

El archivo `.env` en la raíz del proyecto es fundamental para el funcionamiento de todas las APIs y la persistencia de datos.

## 1. Configuración de Base de Datos
- `MYSQL_USER`: Usuario de la base de datos (ej. `guillem`).
- `MYSQL_PASSWORD`: Contraseña del usuario.
- `MYSQL_DATABASE`: Nombre de la base de datos (ej. `videos_automaticos`).
- `MYSQL_ROOT_PASSWORD`: Contraseña de root (solo para inicialización).

## 2. APIs de Inteligencia Artificial
- `OPENAI_API_KEY`: Utilizada para la generación de metadatos SEO (Títulos y Descripciones).
- `ELEVENLABS_API_KEY`: Necesaria para la síntesis de voz (TTS).
- `LEONARDO_API_KEY`: Opcional, para usar los modelos de Leonardo.Ai.

## 3. Integración con ComfyUI
- `COMFY_URL`: Dirección IP y puerto de la instancia de ComfyUI (ej. `http://192.168.1.32:8188`). **Importante**: Debe ser accesible desde el contenedor de Docker de la API.

## 4. Sincronización y Despliegue (Scripts)
- `REMOTE_SSH_USER`: Usuario SSH del servidor remoto.
- `REMOTE_SSH_HOST`: Dirección IP o dominio del servidor.
- `REMOTE_SSH_PORT`: Puerto SSH (ej. `5622`).
- `REMOTE_BASE_PATH`: Ruta base en el servidor donde reside el proyecto (ej. `/home/guillem/code/videos_automaticos`).

## 5. Otras Configuraciones
- `SECRET_KEY`: Clave para la generación de tokens JWT de sesión.
- `ALGORITHM`: Algoritmo de encriptación (ej. `HS256`).
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Tiempo de expiración de la sesión.
- `FRONTEND_URL`: URL del frontend para configurar CORS (ej. `http://localhost:8501`).
