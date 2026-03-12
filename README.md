# ChambaFlow - Bot de Postulación (OCC) - Guía Rápida

## 1) SIEMPRE: primero navegador, después bot

Primero abre el navegador en modo depuración. El bot está configurado para conectarse a esa sesión; si no existe, no arranca.

## 2) Abrir Brave en modo depuración

Ejecuta este comando en PowerShell:

```powershell
Start-Process -FilePath "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" -ArgumentList '--remote-debugging-port=9222','--user-data-dir=C:\Users\imorales\Videos\PRUEBAS-PY\bot\brave_manual_profile'
```

Opcional para validar que está activo:

```powershell
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:9222/json/version', timeout=3).status)"
```

Si imprime `200`, todo bien.

## 3) Iniciar sesión manual en OCC

1. En la ventana de Brave que se abrió, entra a `https://www.occ.com.mx/`.
2. Inicia sesión manualmente.
3. Deja esa ventana abierta.

## 4) Ejecutar el bot

Desde la carpeta del proyecto:

```powershell
python -u main.py
```

## 5) Detener el bot

Para detener procesos del bot:

```powershell
Get-CimInstance Win32_Process | Where-Object { ($_.Name -match '^python(\.exe)?$' -and $_.CommandLine -like '*PRUEBAS-PY\\bot*main.py*') -or ($_.Name -match '^chromedriver(\.exe)?$' -and $_.CommandLine -like '*PRUEBAS-PY\\bot*') -or ($_.Name -match '^brave(\.exe)?$' -and $_.CommandLine -like '*--remote-debugging-port=9222*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
```

## 6) Configuración clave (`config.yaml`)

Verifica que tengas:

```yaml
keywords:
  - "React remoto"
  - "Frontend remoto"
  - "Full stack remoto"
  - "React Puebla"
sitios:
  - "occ"
browser: "brave"
debugger_address: "127.0.0.1:9222"
controlled_mode: true
max_postulaciones_dia: 10
occ_max_scan_per_keyword: 12
```
