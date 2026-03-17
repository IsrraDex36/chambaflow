# ChambaFlow - Bot de Postulación (OCC y Computrabajo)

![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![Selenium](https://img.shields.io/badge/selenium-automation-green.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Bot para postular automáticamente en OCC y Computrabajo (México). Usa Selenium con Brave o Chrome en modo depuración.

## Requisitos

- Python 3.10+
- Brave o Chrome
- Cuenta iniciada sesión en OCC y/o Computrabajo

## Instalación

```bash
pip install -r requirements.txt
```

Dependencias principales: `selenium`, `webdriver-manager`, `pyyaml`, `questionary` (menú en consola).

## Arranque rápido

### 1. Abrir el navegador en modo depuración

Siempre hay que abrir primero el navegador; el bot se conecta a esa sesión.

Ejemplo con Brave (perfil en la carpeta del proyecto):

```powershell
Start-Process -FilePath "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" -ArgumentList '--remote-debugging-port=9222','--user-data-dir=C:\Users\TU_USUARIO\Videos\PRUEBAS-PY\bot\brave_manual_profile'
```

O usa el script que abre Brave y luego el bot (solo Computrabajo):

```powershell
.\run_computrabajo.ps1
```

### 2. Iniciar sesión manual

En la ventana de Brave que se abrió, entra a occ.com.mx y/o mx.computrabajo.com e inicia sesión. Deja la ventana abierta.

### 3. Ejecutar el bot

```bash
python -u main.py
```

Al ejecutar se muestra un menú en consola:

- **Espacio**: marcar o desmarcar cada sitio (OCC, Computrabajo).
- **Enter**: confirmar y ejecutar con los sitios elegidos.

Si no marcas ninguno o cancelas, se usa la lista `sitios` de `config.yaml`.

## Ejecutar sin menú (por línea de comandos)

```bash
python -u main.py --sitios computrabajo
python -u main.py --sitios occ,computrabajo
```

## Configuración (`config.yaml`)

| Clave | Descripción |
|---|---|
| `sitios` | Lista por defecto si no eliges en el menú, ej. `["occ"]`, `["computrabajo"]` o ambos |
| `browser` | `"brave"` o `"chrome"` |
| `debugger_address` | `"127.0.0.1:9222"` para conectarse al navegador abierto con `--remote-debugging-port=9222`. Déjalo vacío `""` si quieres que el bot abra el navegador él solo |
| `keywords` | Términos de búsqueda (ej. `"Desarrollador React remoto"`) |
| `cv_path` | Ruta a tu CV en PDF |
| `max_postulaciones_dia` | Límite de postulaciones por ejecución |
| `occ_filter` / `computrabajo_filter` | Términos a excluir o incluir en el título de la vacante (`exclude_terms`, `include_tech_terms`, etc.) |

Ver `config.example.yaml` o `README_OCC.md` para más detalle sobre OCC.

## Sitios soportados

| Sitio | Clave en config / menú | Notas |
|---|---|---|
| OCC | `occ` | Scroll infinito, filtros por términos |
| Computrabajo MX | `computrabajo` | Click en "Postularme", formulario in-page |

## Detener el bot

En PowerShell, para terminar procesos Python del bot:

```powershell
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE
taskkill /PID <PID> /F
```

O cierra la ventana de Brave y el proceso Python.

## Estructura del proyecto

| Archivo | Descripción |
|---|---|
| `main.py` | Entrada: menú de sitios, carga config, lanza los bots |
| `cv_bot_occ.py` | Bot para OCC |
| `cv_bot_computrabajo.py` | Bot para Computrabajo (listado, panel, preguntas de selección, "Enviar mi CV") |
| `utils.py` | Driver Selenium, delays, screenshots |
| `config.yaml` | Configuración (no subir credenciales) |
| `run_computrabajo.ps1` | Abre Brave con depuración y ejecuta el bot (Computrabajo) |

Más detalle de OCC en `README_OCC.md`.

## ⚠️ Advertencia de Uso Responsable

> **Nota Legal / Disclaimer:** Este proyecto tiene fines educativos y de optimización de tiempo personal. El uso continuo de bots puede ir en contra de los Términos de Servicio de algunas plataformas. Usa esta herramienta bajo tu propio riesgo. Se recomienda usar pausas razonables y no saturar los servidores.
