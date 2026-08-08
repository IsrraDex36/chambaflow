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

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell):**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Dependencias principales: `selenium`, `webdriver-manager`, `pyyaml`, `questionary` (menú en consola). El venv es opcional pero recomendado; actívalo cada vez que abras una terminal nueva antes de correr el bot.

## Arranque rápido

El flujo es siempre el mismo en cualquier sistema operativo: **1)** abrir el navegador en modo depuración, **2)** iniciar sesión manual en el sitio, **3)** ejecutar el bot. Solo cambia cómo se hace el paso 1.

### 1. Abrir el navegador en modo depuración

El bot nunca abre el navegador por ti para iniciar sesión — se conecta a una ventana que tú ya abriste con `--remote-debugging-port=9222`.

**macOS**

Script listo para OCC (abre Brave, espera y ejecuta el bot):

```bash
./scripts/run_occ.sh
```

O manualmente:

```bash
"/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
  --remote-debugging-port=9222 \
  --user-data-dir="$(pwd)/session_data_brave" &
```

Con Chrome en vez de Brave, cambia la ruta a `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"` y ajusta `browser: "chrome"` en `config.yaml`.

**Windows (PowerShell)**

Scripts listos (abren Brave y ejecutan el bot):

```powershell
.\scripts\run_occ.ps1            # solo OCC
.\scripts\run_computrabajo.ps1   # solo Computrabajo
```

O manualmente:

```powershell
Start-Process -FilePath "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" -ArgumentList '--remote-debugging-port=9222','--user-data-dir=C:\Users\TU_USUARIO\chambaflow-profile\brave'
```

Con Chrome, cambia la ruta a `"C:\Program Files\Google\Chrome\Application\chrome.exe"` y ajusta `browser: "chrome"` en `config.yaml`.

**Linux**

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir="$(pwd)/session_data_chrome" &
# o: brave-browser --remote-debugging-port=9222 --user-data-dir="$(pwd)/session_data_brave" &
```

> No sabes qué navegador tienes instalado o en qué SO estás corriendo esto — el bot lo detecta solo y lo muestra al arrancar (pantalla de bienvenida: "Sistema: ... | Navegadores detectados: ..."). Si el `browser` de `config.yaml` no coincide con lo instalado, te avisa ahí mismo.

### 2. Iniciar sesión manual

En la ventana que se abrió, entra a occ.com.mx y/o mx.computrabajo.com e inicia sesión. Deja la ventana abierta.

### 3. Ejecutar el bot

**macOS / Linux:**

```bash
python -u main.py
```

**Windows (PowerShell):**

```powershell
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
| `keywords` | Términos de búsqueda: strings o `{ query: "...", extra_queries: [...] }` |
| `cv_path` | Ruta a tu CV en PDF |
| `max_postulaciones_dia` | Tope diario de postulaciones (ver `daily_quota` para repartir entre varias ejecuciones) |
| `daily_quota` | `count_from_csv: true` resta las postulaciones ya registradas hoy en `postulaciones.csv` |
| `search` | `rotate_keywords`, `state_file`: entre ejecuciones no siempre empiezas por la misma keyword |
| `occ_modal` | (OCC) `max_attempts`, `preferred_skill_ratings` para el modal de conocimientos |
| `occ_filter` / `computrabajo_filter` | `exclude_terms`, `include_tech_terms`, `include_title_must_contain_any`, etc. |

Ver `config/config.example.yaml` o `docs/README_OCC.md` para más detalle sobre OCC.

## Sitios soportados

| Sitio | Clave en config / menú | Notas |
|---|---|---|
| OCC | `occ` | Scroll infinito, filtros por términos |
| Computrabajo MX | `computrabajo` | Click en "Postularme", formulario in-page |

## Detener el bot

Lo más simple en cualquier SO: `Ctrl+C` en la terminal donde corre `python -u main.py`, y cerrar la ventana del navegador.

**macOS / Linux:**

```bash
pkill -f "main.py"
```

**Windows (PowerShell):**

```powershell
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE
taskkill /PID <PID> /F
```

## Estructura del proyecto

| Ruta | Descripción |
|---|---|
| `main.py` | Wrapper delgado: `from chambaflow.cli import main` |
| `chambaflow/cli.py` | Menú de sitios, parseo de args, `run_once()`, scheduler |
| `chambaflow/config.py` | Carga de `config.yaml` |
| `chambaflow/driver.py` | Driver Selenium, delays, screenshots, log de postulaciones |
| `chambaflow/state.py` | Rotación de keywords, estado en disco, cuota diaria desde CSV |
| `chambaflow/filters.py` | `RelevanceFilter`: filtro de relevancia por título, compartido por los tres bots |
| `chambaflow/bots/base.py` | `BotBase` (init común + filtro) y `WizardApplyMixin` (helpers de formularios multi-paso compartidos por Computrabajo/Indeed) |
| `chambaflow/bots/occ.py` | Bot para OCC |
| `chambaflow/bots/computrabajo.py` | Bot para Computrabajo (listado, panel, preguntas de selección, "Enviar mi CV") |
| `chambaflow/bots/indeed.py` | Bot para Indeed (IndeedApply) |
| `config.yaml` | Configuración real del usuario (no subir credenciales) |
| `config/config.example.yaml` | Plantilla comentada de config |
| `scripts/` | `run_occ.sh`, `run_occ.ps1`, `run_computrabajo.ps1` — abren Brave con depuración y ejecutan el bot |
| `docs/` | `README_OCC.md`, `CONTRIBUTING.md`, `CHANGELOG.md` |

Más detalle de OCC en `docs/README_OCC.md`.

## ⚠️ Advertencia de Uso Responsable

> **Nota Legal / Disclaimer:** Este proyecto tiene fines educativos y de optimización de tiempo personal. El uso continuo de bots puede ir en contra de los Términos de Servicio de algunas plataformas. Usa esta herramienta bajo tu propio riesgo. Se recomienda usar pausas razonables y no saturar los servidores.
