# ChambaFlow

![Tests](https://github.com/IsrraDex36/chambaflow/actions/workflows/tests.yml/badge.svg)
![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)
![Selenium](https://img.shields.io/badge/selenium-automation-green.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Bot de postulación automática para **OCC**, **Computrabajo** e **Indeed** (México). Se conecta por CDP a un Chrome/Brave que **tú ya abriste y en el que ya iniciaste sesión**, y desde ahí busca, filtra, llena formularios y postula.

## Cómo funciona

- **No automatiza el login.** Tú abres el navegador en modo debug, entras a mano, y Selenium se adjunta a esa ventana. Cero credenciales guardadas.
- Si detecta que te desconectaste, salta ese sitio en vez de insistir en el login.
- Reutiliza el CV ya subido a tu perfil; solo usa `cv_path` si el sitio fuerza uno nuevo.

## Requisitos

- Python 3.9+
- Brave o Chrome instalado
- Sesión iniciada en OCC, Computrabajo y/o Indeed

## Instalación

```bash
python3 -m venv venv && source venv/bin/activate   # Windows: .\venv\Scripts\Activate.ps1
pip install -e .
```

Deja el comando `chambaflow` disponible (`chambaflow --help`).

**Alternativa sin Python:** ejecutable standalone vía PyInstaller — solo build probado en macOS arm64, instrucciones en [`docs/BUILD.md`](docs/BUILD.md).

## Uso rápido

```bash
chambaflow status                 # 1. genera config.yaml si no existe
# edita config.yaml: debugger_address, sitios, keywords
./scripts/run_occ.sh              # 2. abre Brave en modo debug
#    ... inicia sesión a mano ...
chambaflow run --dry-run          # 3. corrida de prueba, no postula real
chambaflow run                    # 4. corrida real
```

> `--dry-run` no aísla el navegador: si `debugger_address` apunta a uno real, navega ahí (avisa en consola). Para probar sin riesgo, cierra ese navegador o usa `debugger_address: ""`.

### Comandos

```bash
chambaflow run --sitio occ --dry-run               # busca y postula
chambaflow status                                   # cuota de hoy vs máxima
chambaflow config show                              # imprime config.yaml
chambaflow config edit                              # abre config.yaml en $EDITOR
chambaflow run --sitio occ --sitio indeed           # sitios puntuales (repetible)
chambaflow run --keyword "desarrollador python"     # fuerza keyword, ignora rotación
chambaflow run --config otra_config.yaml            # otro archivo de config
```

## Abrir el navegador en modo depuración

1. Abre Chrome/Brave con `--remote-debugging-port=9222`.
2. Inicia sesión a mano en OCC/Computrabajo/Indeed en esa ventana.
3. Deja la ventana abierta y corre el bot.

El puerto debe coincidir con `debugger_address` en `config.yaml` (ej. `"127.0.0.1:9222"`).

**macOS** — `./scripts/run_occ.sh`, o a mano:

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
</details>

<details>
<summary><b>Linux</b></summary>

```bash
google-chrome --remote-debugging-port=9222 --user-data-dir="$(pwd)/session_data_chrome" &
```
</details>

Para Chrome en vez de Brave: cambia el binario y pon `browser: "chrome"` en `config.yaml`.

## Configuración (`config.yaml`)

| Clave | Qué hace |
|---|---|
| `sitios` | Default si no eliges en el menú: `["occ"]`, `["computrabajo"]`, `["indeed"]` o combinación |
| `browser` / `debugger_address` | `"brave"`/`"chrome"` + `"127.0.0.1:9222"` para adjuntarse. `""` → el bot abre uno propio |
| `keywords` | Strings o `{ query, extra_queries }`, con rotación entre corridas |
| `cv_path` | Respaldo, solo si el sitio exige CV nuevo |
| `max_postulaciones_dia` / `daily_quota.count_from_csv` | Tope diario, contado desde `postulaciones.csv` |
| `occ_filter` / `computrabajo_filter` / `indeed_filter` | Reglas de relevancia; si no defines Computrabajo/Indeed, caen a `occ_filter` |
| `scheduler` | `enabled`, `start_hour`, `end_hour`, `pause_between_runs_min` |
| `screenshots_retention_days` | Borra capturas viejas al arrancar (default 30) |

Plantilla comentada en `config/config.example.yaml`; detalle de OCC en `docs/README_OCC.md`.

## Sitios soportados

| Sitio | Clave | Mecánica |
|---|---|---|
| OCC | `occ` | Panel lateral, modal de "nivel de conocimientos" |
| Computrabajo MX | `computrabajo` | Wizard in-page (CV → preguntas → enviar) |
| Indeed MX | `indeed` | Solo vacantes con badge **IndeedApply** |

## Detener el bot

`Ctrl+C` en la terminal, y cierra la ventana del navegador.

```bash
pkill -f "chambaflow"       # macOS / Linux
taskkill /IM python.exe /F  # Windows (PowerShell)
```

## ⚠️ Uso responsable

Postular de forma automatizada puede ir contra los Términos de Servicio de OCC, Computrabajo e Indeed. Úsalo bajo tu propio criterio, con tu propia cuenta, y con cuotas razonables (`max_postulaciones_dia`).
