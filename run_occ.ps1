# 1. Abrir Brave en modo depuracion (puerto 9222)
# 2. Esperar a que este listo
# 3. Ejecutar el bot de OCC (conectado a ese navegador)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Abriendo Brave con depuracion remota (puerto 9222) - perfil OCC..."
$braveProfileOcc = Join-Path $env:USERPROFILE "Videos\PRUEBAS-PY\bot\brave_occ_profile"
Start-Process -FilePath "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" -ArgumentList '--remote-debugging-port=9222',"--user-data-dir=$braveProfileOcc"

Write-Host "Esperando 6 segundos a que Brave inicie..."
Start-Sleep -Seconds 6

Write-Host "Ejecutando bot de OCC..."
python -u main.py --config config.yaml --sitios occ
