# 1. Abrir Brave en modo depuración (puerto 9222)
# 2. Esperar a que esté listo
# 3. Ejecutar el bot de Computrabajo (conectado a ese navegador)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Abriendo Brave con depuración remota (puerto 9222)..."
Start-Process -FilePath "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" -ArgumentList '--remote-debugging-port=9222','--user-data-dir=C:\Users\imorales\Videos\PRUEBAS-PY\bot\brave_manual_profile'

Write-Host "Esperando 6 segundos a que Brave inicie..."
Start-Sleep -Seconds 6

Write-Host "Ejecutando bot de Computrabajo..."
python main.py --config config.yaml
