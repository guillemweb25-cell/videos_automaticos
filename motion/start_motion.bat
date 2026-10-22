@echo off
REM Lanza el servicio de render "motion" (HyperFrames) en el host (fuera de Docker).
REM Escucha en 127.0.0.1:8610 (el contenedor api entra por host.docker.internal). La primera vez: "npm install" en esta carpeta.
REM Para que arranque siempre: copia start_motion_hidden.vbs en shell:startup.
cd /d "%~dp0"
if not exist node_modules call npm install
node server.mjs
pause
