' Lanza el servicio de render "motion" SIN ventana, al iniciar sesion.
' Se coloca una copia en la carpeta de Inicio de Windows (shell:startup).
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "D:\videos_automaticos\motion"
sh.Run "node server.mjs", 0, False
