# ChambaFlow OCC - Instrucciones de Uso

Guía dedicada para ejecutar el bot en `occ.com.mx`.
Por defecto está configurado para Brave en modo depuración, pero también funciona con otros navegadores Chromium (por ejemplo Chrome o Edge).

## 1) Requisitos

- Python 3.10+ instalado
- Dependencias del proyecto instaladas:

```powershell
pip install -r requirements.txt
```

## 1.1) Instalación rápida

```powershell
git clone https://github.com/IsrraDex36/chambaflow.git
cd chambaflow
pip install -r requirements.txt
```

## 1.2) Primer arranque en 60 segundos

Checklist express:

1. Instala dependencias: `pip install -r requirements.txt`
2. Verifica `config.yaml`:
   - `sitios: ["occ"]`
   - `browser: "brave"` (o `chrome`)
   - `debugger_address: "127.0.0.1:9222"`
3. Abre navegador en debug (`--remote-debugging-port=9222`)
4. Inicia sesión manual en `https://www.occ.com.mx/`
5. Ejecuta: `python -u main.py`
6. Si necesitas detener: usa el comando de la sección **9**

- Tener `config.yaml` configurado para OCC:
  - `sitios: ["occ"]`
  - `browser: "brave"`
  - `debugger_address: "127.0.0.1:9222"`

## 2) Regla clave del flujo

Siempre en este orden:

1. Abrir navegador (Brave) en modo depuración
2. Iniciar sesión manual en OCC
3. Ejecutar el bot

Si no hay navegador en `9222`, el bot no podrá conectarse.

## 3) Abrir Brave en modo depuración

En PowerShell:

```powershell
Start-Process -FilePath "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" -ArgumentList '--remote-debugging-port=9222','--user-data-dir=C:\Users\imorales\Videos\PRUEBAS-PY\bot\brave_manual_profile'
```

Validación opcional:

```powershell
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:9222/json/version', timeout=3).status)"
```

Si imprime `200`, está correcto.

## 3.1) Otros navegadores compatibles (Chromium)

Tambien puedes usar Chrome o Edge.

1. Cambia en `config.yaml`:

```yaml
browser: "chrome"
debugger_address: "127.0.0.1:9222"
```

2. Abre ese navegador con `--remote-debugging-port=9222` y un perfil dedicado.

Ejemplo Chrome en PowerShell:

```powershell
Start-Process -FilePath "C:\Program Files\Google\Chrome\Application\chrome.exe" -ArgumentList '--remote-debugging-port=9222','--user-data-dir=C:\Users\imorales\Videos\PRUEBAS-PY\bot\chrome_manual_profile'
```

## 4) Iniciar sesión en OCC

En la ventana de Brave abierta:

1. Entrar a `https://www.occ.com.mx/`
2. Iniciar sesión manualmente
3. Dejar esa ventana abierta

## 5) Ejecutar el bot

Desde la carpeta del proyecto:

```powershell
python -u main.py
```

`-u` ayuda a ver logs en tiempo real.

## 6) Configuración recomendada (`config.yaml`)

Ejemplo:

```yaml
keywords:
  - "Desarrollador web remoto"
  - "Frontend remoto"
  - "Full stack remoto"
  - "Ingeniero de software remoto"
  - "Programador remoto"
sitios:
  - "occ"
browser: "brave"
debugger_address: "127.0.0.1:9222"
controlled_mode: true
max_postulaciones_dia: 10
occ_max_scan_per_keyword: 12
```

## 7) Qué hace el bot en OCC

- Busca por cada keyword
- Recorre cards de vacantes
- Filtra vacantes no relevantes
- Intenta postular y resolver modal de conocimientos
- Respeta límites (`max_postulaciones_dia` y `occ_max_scan_per_keyword`)

## 8) Evidencia y depuración

Se guardan capturas en `screenshots/` cuando hay errores.

Si falla el modal de conocimientos tras los reintentos:

- screenshot de modal (si disponible)
- screenshot de página
- log en `screenshots/occ_modal_failures.log` con `job_id` y contexto

## 9) Detener bot/procesos

```powershell
Get-CimInstance Win32_Process | Where-Object { ($_.Name -match '^python(\.exe)?$' -and $_.CommandLine -like '*PRUEBAS-PY\\bot*main.py*') -or ($_.Name -match '^chromedriver(\.exe)?$' -and $_.CommandLine -like '*PRUEBAS-PY\\bot*') -or ($_.Name -match '^brave(\.exe)?$' -and $_.CommandLine -like '*--remote-debugging-port=9222*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
```

## 10) Problemas comunes

- **No conecta al navegador**: Brave no está abierto con `--remote-debugging-port=9222`.
- **Se abre pero no postula**: revisa sesión iniciada en OCC y vacantes ya postuladas.
- **Mucho ruido en resultados**: ajusta `keywords` y baja/ajusta `occ_max_scan_per_keyword`.
- **Modal se atora**: revisar `screenshots/occ_modal_failures.log` y capturas.
