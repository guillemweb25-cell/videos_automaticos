' Lanza el agente de entrenamiento de LoRAs SIN ventana (pythonw), al iniciar sesion.
' Se coloca una copia en la carpeta de Inicio de Windows (shell:startup).
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "D:\videos_automaticos"
sh.Run """D:\AI\sd-scripts\venv\Scripts\pythonw.exe"" host_agent\train_agent.py", 0, False
