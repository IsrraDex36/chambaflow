# ChambaFlow

![Tests](https://github.com/IsrraDex36/chambaflow/actions/workflows/tests.yml/badge.svg)
![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)
![Selenium](https://img.shields.io/badge/selenium-automation-green.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Bot de postulación automática para **OCC**, **Computrabajo** e **Indeed** (México). Se conecta por CDP a un Chrome/Brave que **tú ya abriste y en el que ya iniciaste sesión**, y desde ahí busca, filtra, llena formularios y postula.

```
╭─────────────────────────────────────────── Bienvenido ───────────────────────────────────────────╮
│      ██████╗██╗  ██╗ █████╗ ███╗   ███╗██████╗  █████╗ ███████╗██╗      ██████╗ ██╗    ██╗       │
│      ██╔════╝██║  ██║██╔══██╗████╗ ████║██╔══██╗██╔══██╗██╔════╝██║     ██╔═══██╗██║    ██║      │
│      ██║     ███████║███████║██╔████╔██║██████╔╝███████║█████╗  ██║     ██║   ██║██║ █╗ ██║      │
│      ██║     ██╔══██║██╔══██║██║╚██╔╝██║██╔══██╗██╔══██║██╔══╝  ██║     ██║   ██║██║███╗██║      │
│      ╚██████╗██║  ██║██║  ██║██║ ╚═╝ ██║██████╔╝██║  ██║██║     ███████╗╚██████╔╝╚███╔███╔╝      │
│       ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝        │
│                          Bot de Postulación Automática · OCC · Computrabajo · Indeed              │
╰────────────────────────────────────────────── v2.0 ──────────────────────────────────────────────╯
```

## Cómo funciona

- **No automatiza el login.** Tú abres el navegador con `--remote-debugging-port=9222`, entras a mano a OCC/Computrabajo/Indeed, y Selenium se adjunta a esa ventana ya autenticada. Cero credenciales guardadas, cero pelea contra captchas.
- **Verifica sesión antes de tocar nada.** Si detecta que te desconectaste, salta ese sitio en vez de insistir sobre una pantalla de login.
- **El CV normalmente ya está en tu perfil.** El bot reutiliza el CV que ya subiste a cada plataforma; solo sube un archivo local (`cv_path`, ver tabla de Configuración) si el sitio fuerza un CV nuevo y no ofrece usar el existente.

## Requisitos

- Python 3.9+
- Brave o Chrome instalado
- Sesión iniciada en OCC, Computrabajo y/o Indeed

## Instalación

Dos vías — usa la que te acomode.

**Opción A — CLI vía pip (recomendada, multiplataforma):**

```bash
python3 -m venv venv && source venv/bin/activate   # Windows: python -m venv venv && .\venv\Scripts\Activate.ps1
pip install -e .
```

Deja el comando `chambaflow` disponible en el venv (`chambaflow --help`).

**Opción B — ejecutable standalone (sin instalar Python):**

Un solo binario. **Por ahora solo hay build probado en macOS arm64** — Windows y Linux no están generados todavía, pero puedes compilarlos tú mismo con `pyinstaller` (instrucciones y gotchas completos en [`docs/BUILD.md`](docs/BUILD.md)):

```bash
pip install -e ".[build]"
pyinstaller chambaflow.spec
./dist/chambaflow --help
```

## Uso rápido

```bash
chambaflow status                 # 1. genera config.yaml si no existe
# edita config.yaml: debugger_address, sitios, keywords
./scripts/run_occ.sh              # 2. abre Brave en modo debug (o hazlo a mano, ver abajo)
#    ... inicia sesión a mano en la ventana que se abrió ...
chambaflow run --dry-run          # 3. corrida de prueba: navega y filtra, no postula de verdad
chambaflow run                    # 4. corrida real
```

> **`--dry-run` no aísla el navegador.** Nunca envía postulaciones reales ni escribe en tu `postulaciones.csv` real (usa `postulaciones_dryrun.csv` aparte por default), pero si ya tienes un navegador real abierto en `debugger_address`, sí navega ahí de verdad — te avisa en consola cuando pasa. Para probar sin tocar tu sesión real: cierra ese navegador antes, o usa `debugger_address: ""` (el bot abre uno propio y desechable).

### Comandos

**`chambaflow run`** — busca y postula. Menú interactivo si no le das `--sitio`.

```bash
chambaflow run --sitio occ --dry-run
```

**`chambaflow status`** — cuota de hoy vs. máxima y última postulación (`postulaciones.csv`).

```bash
chambaflow status
```

**`chambaflow config show`** — imprime `config.yaml` con resaltado de sintaxis.

```bash
chambaflow config show
```

**`chambaflow config edit`** — abre `config.yaml` en `$EDITOR` (o `$VISUAL`).

```bash
chambaflow config edit
```

Más flags de `run`:

```bash
chambaflow run --sitio occ --sitio indeed          # sitios puntuales (repetible; sin esto, menú o config.yaml)
chambaflow run --keyword "desarrollador python"    # fuerza una keyword, ignora rotación
chambaflow run --config otra_config.yaml           # otro archivo de config
```

## Abrir el navegador en modo depuración

El bot no abre sesión por ti. Pasos, en orden:

1. Abre tu Chrome/Brave con `--remote-debugging-port=9222` (ejemplos abajo).
2. Entra a OCC/Computrabajo/Indeed e inicia sesión a mano en esa ventana.
3. Deja esa ventana abierta y corre el bot — se conecta ahí directo.

El puerto que uses (`9222` en los ejemplos) debe coincidir exactamente con `debugger_address` en tu `config.yaml` (ej. `"127.0.0.1:9222"`). Si no coinciden, o si cierras la ventana, el bot no se conecta.

**macOS** — `./scripts/run_occ.sh` (abre Brave + corre OCC), o a mano:

```bash
"/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
  --remote-debugging-port=9222 --user-data-dir="$(pwd)/session_data_brave" &
```

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
.\scripts\run_occ.ps1            # solo OCC
.\scripts\run_computrabajo.ps1   # solo Computrabajo
```

O a mano:

```powershell
Start-Process -FilePath "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" -ArgumentList '--remote-debugging-port=9222','--user-data-dir=C:\Users\TU_USUARIO\chambaflow-profile\brave'
```
</details>

<details>
<summary><b>Linux</b></summary>

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir="$(pwd)/session_data_chrome" &
```
</details>

Para usar Chrome en vez de Brave: cambia el binario y pon `browser: "chrome"` en `config.yaml`. El bot detecta qué navegadores tienes instalados y lo muestra al arrancar, avisando si no coincide con tu config.

## Configuración (`config.yaml`)

| Clave | Qué hace |
|---|---|
| `sitios` | Default si no eliges en el menú: `["occ"]`, `["computrabajo"]`, `["indeed"]` o combinación |
| `browser` / `debugger_address` | `"brave"`/`"chrome"` + `"127.0.0.1:9222"` para adjuntarse al navegador abierto. `""` → el bot lanza uno propio |
| `keywords` | Strings o `{ query, extra_queries }`, con rotación de orden entre corridas |
| `cv_path` | Respaldo, solo si el sitio exige subir CV y no hay uno ya en tu perfil |
| `max_postulaciones_dia` / `daily_quota.count_from_csv` | Tope diario, contado desde `postulaciones.csv` |
| `search.rotate_keywords` / `search.state_file` | Rotación de keywords entre corridas |
| `occ_filter` / `computrabajo_filter` / `indeed_filter` | Reglas de relevancia; si no defines los de Computrabajo/Indeed, caen a `occ_filter` |
| `indeed_filter.contact` | Solo Indeed: `{ nombre, apellido, telefono }` para el wizard |
| `occ_modal.max_attempts` / `preferred_skill_ratings` | Solo OCC: modal de "nivel de conocimientos" |
| `scheduler` | `enabled`, `start_hour`, `end_hour`, `pause_between_runs_min` — corre en loop dentro de una ventana horaria |
| `screenshots_retention_days` | Borra capturas de más de N días al arrancar (default 30) |

Plantilla comentada en `config/config.example.yaml`; detalle de OCC en `docs/README_OCC.md`.

## Bajo el capó

- **Filtro de relevancia** (`RelevanceFilter`, un solo módulo para los 3 sitios): `include_title_must_contain_any` → `exclude_terms`/`exclude_regex` (palabra completa, `"java"` no descarta `"javascript"`) → `include_tech_terms` → fallback por tokens de la keyword.
- **Cuota diaria** contada desde `postulaciones.csv`, sobrevive a cerrar y reabrir el bot el mismo día.
- **Anti-doble-postulación en OCC**: firma título+empresa guardada en `chambaflow_state.yaml`, evita repetir vacantes republicadas con `job_id` distinto. Computrabajo/Indeed leen el badge "ya aplicaste" del panel.
- **`screenshots/`** solo guarda evidencia de fallos (no de corridas normales); se limpia sola pasados `screenshots_retention_days`.

## Sitios soportados

| Sitio | Clave | Mecánica |
|---|---|---|
| OCC | `occ` | Panel lateral, modal de "nivel de conocimientos", paginación por keyword |
| Computrabajo MX | `computrabajo` | Wizard in-page (CV → preguntas de selección → enviar) |
| Indeed MX | `indeed` | Solo vacantes con badge **IndeedApply**; wizard en ventana/iframe aparte |

## Detener el bot

`Ctrl+C` en la terminal, y cierra la ventana del navegador.

```bash
pkill -f "chambaflow"                                   # macOS / Linux
```

```powershell
taskkill /IM python.exe /F                              # Windows
```

## Estructura del proyecto

| Ruta | Rol |
|---|---|
| `pyproject.toml` | Entry point `chambaflow = "chambaflow.cli:app"` |
| `chambaflow/cli.py` | CLI Typer (`run`/`status`/`config`), menú, banner, `run_once()`, scheduler |
| `chambaflow/driver.py` | `setup_driver()` (CDP), screenshots, log CSV |
| `chambaflow/filters.py` | `RelevanceFilter`, único para los 3 bots |
| `chambaflow/state.py` | Rotación de keywords y cuota diaria |
| `chambaflow/bots/base.py` | `BotBase` + `WizardApplyMixin` (compartido por Computrabajo/Indeed) |
| `chambaflow/bots/{occ,computrabajo,indeed}.py` | Un bot por sitio |
| `config/config.example.yaml` | Plantilla comentada |
| `scripts/` | Abren el navegador en debug y lanzan el bot |
| `docs/` | `README_OCC.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `BUILD.md` (ejecutable standalone) |

## ⚠️ Uso responsable

Postular de forma automatizada puede ir contra los Términos de Servicio de OCC, Computrabajo e Indeed, aunque sea uso personal y una postulación a la vez. Úsalo bajo tu propio criterio, con tu propia cuenta, y con cuotas razonables (`max_postulaciones_dia`).
