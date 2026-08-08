# ChambaFlow

![Tests](https://github.com/IsrraDex36/chambaflow/actions/workflows/tests.yml/badge.svg)
![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)
![Selenium](https://img.shields.io/badge/selenium-automation-green.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Bot de postulación automática para **OCC**, **Computrabajo** e **Indeed** (México). No es un scraper que finge ser humano: se conecta por CDP a un Chrome/Brave que **tú ya tienes abierto y con sesión iniciada**, y desde ahí hace el trabajo repetitivo — buscar, filtrar, abrir vacante, llenar formulario, postular.

```
╭─────────────────────────────────────────── Bienvenido ───────────────────────────────────────────╮
│                                                                                                    │
│              .  .                .           ·       .       .           * .    .                │
│      ██████╗██╗  ██╗ █████╗ ███╗  ·███╗██████╗  █████╗ ███████╗██╗      ██████╗ ██╗    ██╗       │
│      ██╔════╝██║ *██║██╔══██╗████╗ ████║██╔══██╗██╔══██╗██╔════╝██║     ██╔═══██╗██║    ██║      │
│      ██║    .███████║███████║██╔████╔██║██████╔╝███████║█████╗ ·██║     ██║   ██║██║ █╗ ██║      │
│      ██║     ██╔══██║██╔══██║██║╚██╔╝██║██╔══██╗██╔══██║██╔══╝ ·██║  .  ██║ . ██║██║███╗██║      │
│      ╚██████╗██║  ██║██║  ██║██║ ╚═╝ ██║██████╔╝██║  ██║██║     ███████╗╚██████╔╝╚███╔███╔╝      │
│       ╚═════╝╚═╝  ╚═╝╚═╝* ╚═╝╚═╝     ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝       │
│           ..     .                 .            .         .   .     ·                            │
│                                                                                                    │
│      Bot de Postulación Automática                                                                │
│      OCC · Computrabajo · Indeed                                                                  │
│                                                                                                    │
╰────────────────────────────────────────────── v2.0 ──────────────────────────────────────────────╯
```

## Por qué se conecta a tu navegador en vez de abrir uno propio

Login, 2FA y captchas los resuelves **tú**, a mano, una sola vez por sesión de navegador. El bot arranca con `--remote-debugging-port=9222`, tú entras a occ.com.mx / mx.computrabajo.com / mx.indeed.com e inicias sesión, y Selenium se adjunta a esa ventana ya autenticada (`debugger_address` en `config.yaml`). Cero credenciales guardadas, cero intento de automatizar el login. Es más frágil que un headless clásico si cierras la ventana, pero es la única forma honesta de no pelear contra la protección anti-bot de estos sitios.

Antes de tocar nada, además, el bot **verifica que sigas logueado**: navega a la home del sitio, lee el texto de la página y busca señales tipo "cerrar sesión" / "mi cuenta" vs "iniciar sesión" / "regístrate". Si detecta que la sesión se cayó, salta ese sitio por completo en vez de scrapear una página de login en bucle.

## Requisitos

- Python 3.9+
- Brave o Chrome instalado
- Cuenta con sesión iniciada en OCC, Computrabajo y/o Indeed

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

## Primera vez que lo usas

Checklist completo, en orden, antes de tu primera corrida real:

1. **Instala** (sección de arriba).
2. **Genera `config.yaml`**: corre `python -u main.py` una vez — si no existe, el bot lo crea solo copiando `config/config.example.yaml` y te avisa en consola. También puedes copiarlo a mano: `cp config/config.example.yaml config.yaml` (Windows: `copy config\config.example.yaml config.yaml`).
3. **Edítalo antes de postular de verdad** — como mínimo:
   - `cv_path`: ruta a tu CV real en PDF. **Ya no hay CV de mentira de respaldo**: si el archivo no existe, el bot avisa en consola y ese paso falla en cada postulación real.
   - `debugger_address: "127.0.0.1:9222"` — recomendado, para adjuntarse al navegador que abres tú mismo (ver "Por qué se conecta a tu navegador" arriba). Déjalo en `""` solo si quieres que el bot abra su propio navegador (menos confiable, sin tu sesión).
   - `sitios` y `keywords` a tu gusto.
4. **Abre el navegador en modo depuración** (paso 1 de abajo).
5. **Inicia sesión manual** (paso 2 de abajo).
6. **Corre el bot** — la primera vez, mejor con `--dry-run` para ver qué encuentra y filtra sin postular de verdad: `python -u main.py --dry-run`.

Una vez configurado, el día a día es solo repetir los pasos 4-6.

### 1. Abrir el navegador en modo depuración

**macOS** — script listo (abre Brave y corre OCC):

```bash
./scripts/run_occ.sh
```

O manual:

```bash
"/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
  --remote-debugging-port=9222 \
  --user-data-dir="$(pwd)/session_data_brave" &
```

**Windows (PowerShell)** — scripts listos:

```powershell
.\scripts\run_occ.ps1            # solo OCC
.\scripts\run_computrabajo.ps1   # solo Computrabajo
```

O manual:

```powershell
Start-Process -FilePath "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" -ArgumentList '--remote-debugging-port=9222','--user-data-dir=C:\Users\TU_USUARIO\chambaflow-profile\brave'
```

**Linux:**

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir="$(pwd)/session_data_chrome" &
```

Usando Chrome en vez de Brave: cambia la ruta del binario y pon `browser: "chrome"` en `config.yaml`. No adivines si tienes Brave o Chrome instalado — el bot escanea las rutas típicas de tu sistema operativo al arrancar y lo imprime en la pantalla de bienvenida (`Sistema: macOS | Navegadores detectados: Brave ✓, Chrome ✗`), avisando si el `browser` de tu config no coincide con lo que encontró.

### 2. Iniciar sesión manual

En la ventana que se abrió: entra a occ.com.mx, mx.computrabajo.com y/o mx.indeed.com, inicia sesión, deja la ventana abierta.

### 3. Ejecutar el bot

```bash
python -u main.py
```

Menú con **Espacio** (marcar/desmarcar sitio) y **Enter** (confirmar). Sin marcar nada o cancelando con Ctrl+C, corre con la lista `sitios` de `config.yaml`.

Sin menú:

```bash
python -u main.py --sitios occ,computrabajo
python -u main.py --dry-run          # navega y filtra real, pero no envía ninguna postulación
```

## Bajo el capó

**Filtro de relevancia** (`chambaflow/filters.py::RelevanceFilter`, un solo módulo para los 3 sitios): por cada vacante evalúa el título en este orden — `include_title_must_contain_any` (si lo pones, filtro obligatorio) → `exclude_terms`/`exclude_regex` (match por palabra completa vía regex con lookaround, para que `"java"` no descarte `"javascript"`) → `include_tech_terms` (si matchea, aceptar) → fallback comparando tokens de tu keyword de búsqueda contra el título.

**Rotación de keywords y cuota diaria** (`chambaflow/state.py`): cada corrida no empieza por la primera keyword de tu lista — guarda un offset en `chambaflow_state.yaml` y rota. La cuota diaria (`max_postulaciones_dia`) se calcula contando las filas de hoy en `postulaciones.csv`, así que sobrevive a que cierres y vuelvas a abrir el bot varias veces en el mismo día.

**Anti-doble-postulación en OCC**: normaliza título+empresa (sin acentos, sin espacios extra) y recuerda esa firma en `chambaflow_state.yaml` por `dedupe_days`. Evita repetir la misma vacante cuando una agencia la re-publica con un `job_id` distinto cada pocos días. Computrabajo e Indeed en cambio leen directamente el badge "ya aplicaste" del panel.

**`screenshots/` es solo evidencia de fallos**, no un feature de uso normal: se llena únicamente cuando algo se rompe (modal que no cierra, postulación sin confirmación clara, error de scraping), cada captura con su línea en `screenshots/{sitio}_apply_failures.log` (`job_id`/título/URL). Una corrida sin errores no toca esa carpeta.

**Scheduler** (`config.yaml: scheduler`): en vez de una corrida y listo, deja el bot en loop entre `start_hour` y `end_hour`, con `pause_between_runs_min` entre cada ejecución — pensado para dejarlo picoteando vacantes nuevas durante el día sin supervisión.

## Configuración (`config.yaml`)

| Clave | Qué hace |
|---|---|
| `sitios` | Default si no eliges en el menú: `["occ"]`, `["computrabajo"]`, `["indeed"]` o combinación |
| `browser` / `debugger_address` | `"brave"`/`"chrome"` + `"127.0.0.1:9222"` para adjuntarse al navegador ya abierto. `debugger_address: ""` → el bot lanza su propio navegador con perfil en `session_dir` |
| `keywords` | Strings o `{ query: "...", extra_queries: [...] }` — ver rotación arriba |
| `cv_path` | PDF a subir cuando el formulario lo pida |
| `max_postulaciones_dia` / `daily_quota.count_from_csv` | Tope diario real, contado desde `postulaciones.csv` |
| `search.rotate_keywords` / `search.state_file` | Rotación de keywords entre corridas |
| `occ_filter` / `computrabajo_filter` / `indeed_filter` | Reglas de `RelevanceFilter`. Si no defines `computrabajo_filter`/`indeed_filter`, caen a `occ_filter` — un solo bloque puede gobernar los 3 sitios |
| `indeed_filter.contact` | Solo Indeed: `{ nombre, apellido, telefono }` para el paso de datos de contacto del wizard IndeedApply |
| `occ_modal.max_attempts` / `preferred_skill_ratings` | Solo OCC: reintentos y orden de preferencia del modal de "nivel de conocimientos" |
| `scheduler` | `enabled`, `start_hour`, `end_hour`, `pause_between_runs_min` |

Plantilla comentada completa en `config/config.example.yaml`; detalle extra de OCC en `docs/README_OCC.md`.

## Sitios soportados

| Sitio | Clave | Mecánica de postulación |
|---|---|---|
| OCC | `occ` | Panel lateral vía Handlebars, resuelve el modal de "nivel de conocimientos" (radios de skill), paginación completa por keyword |
| Computrabajo MX | `computrabajo` | Click en "Postularme", wizard in-page (CV → preguntas de selección → "Enviar mi CV") |
| Indeed MX | `indeed` | Solo vacantes con badge **IndeedApply** (descarta las que redirigen a sitio externo del empleador); wizard en ventana/iframe aparte con datos de contacto, CV y preguntas |

## Detener el bot

`Ctrl+C` en la terminal, y cierra la ventana del navegador.

```bash
pkill -f "main.py"                                    # macOS / Linux
```

```powershell
tasklist /FI "IMAGENAME eq python.exe" /FO TABLE       # Windows
taskkill /PID <PID> /F
```

## Estructura del proyecto

| Ruta | Rol |
|---|---|
| `main.py` | Wrapper de 2 líneas → `chambaflow.cli.main` |
| `chambaflow/cli.py` | Menú, banner, argparse, `run_once()`, scheduler |
| `chambaflow/driver.py` | `setup_driver()` (adjunta al navegador vía CDP), screenshots, log CSV |
| `chambaflow/browser_detect.py` | SO + rutas de Brave/Chrome instaladas (mac/Windows/Linux) |
| `chambaflow/filters.py` | `RelevanceFilter` — filtro de relevancia único para los 3 bots |
| `chambaflow/state.py` | Rotación de keywords y cuota diaria persistidas |
| `chambaflow/bots/base.py` | `BotBase` (init común + `is_logged_in()`) y `WizardApplyMixin` (formulario multi-paso compartido por Computrabajo/Indeed) |
| `chambaflow/bots/{occ,computrabajo,indeed}.py` | Un bot por sitio |
| `config/config.example.yaml` | Plantilla comentada |
| `scripts/` | `.sh`/`.ps1` que abren el navegador en debug y lanzan el bot |
| `docs/` | `README_OCC.md`, `CONTRIBUTING.md`, `CHANGELOG.md` |

## ⚠️ Uso responsable

Fines educativos y de ahorro de tiempo personal. Postular en automático puede ir contra los Términos de Servicio de estos portales — úsalo bajo tu propio riesgo, con cuotas razonables (`max_postulaciones_dia`) y sin intentar saturar los servidores.
