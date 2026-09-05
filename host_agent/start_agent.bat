@echo off
REM Lanza el agente de entrenamiento de LoRAs en el host (fuera de Docker).
REM Debe correr en la maquina con GPU. Escucha en 0.0.0.0:8600.
REM Para que este disponible siempre: anade un acceso directo a este .bat en
REM   shell:startup  (Win+R -> shell:startup), o crea una tarea en el Programador de tareas.
cd /d "%~dp0.."
"D:\AI\sd-scripts\venv\Scripts\python.exe" host_agent\train_agent.py
pause
