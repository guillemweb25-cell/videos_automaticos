# Guía de Instalación y Configuración

Sigue estos pasos para levantar el entorno de desarrollo o producción.

## 1. Requisitos Previos
- Docker y Docker Compose instalados.
- Instancia de ComfyUI (Local o Remota) accesible por red.
- Cuentas en: OpenAI (opcional para SEO), ElevenLabs, Leonardo.Ai (opcional).

## 2. Configuración del Entorno (`.env`)
Copia el archivo de ejemplo:
```bash
cp .env.example .env
```
Variables críticas:
- `COMFY_URL`: URL de tu instancia de ComfyUI (ej. `http://192.168.1.32:8188`).
- `ELEVENLABS_API_KEY`: Para las voces.
- `MYSQL_PASSWORD`: Contraseña para MariaDB.
- `REMOTE_SSH_USER`, `REMOTE_SSH_HOST`, `REMOTE_SSH_PORT`: Para los scripts de sincronización.

## 3. Despliegue con Docker
El proyecto está totalmente contenedorizado. Para iniciar:
```bash
docker-compose up -d --build
```
Servicios disponibles:
- **API (Backend)**: `http://localhost:8000`
- **Frontend**: `http://localhost:8501`
- **Base de Datos**: Puerto `3306` interno.

## 4. Configuración de ComfyUI
Para que la integración funcione, ComfyUI debe estar en modo API.
1. Abre tu workflow en la interfaz de ComfyUI.
2. Habilita "Dev mode" en los ajustes.
3. Haz click en "Save (API Format)" para obtener el JSON.
4. Guarda ese JSON en la carpeta `/workflows` del proyecto.
5. El sistema detectará automáticamente el nuevo workflow en el desplegable del frontend.

## 5. Sincronización entre Laptop y Servidor
Utiliza los scripts en `/scripts`:
- `./scripts/sync_push.sh`: Sube caché, base de datos y credenciales al servidor.
- `./scripts/sync_pull.sh`: Baja la base de datos y caché del servidor al portátil.
*Nota: Estos scripts NO sincronizan el código (usar Git para eso).*
