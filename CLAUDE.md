# ChambaFlow — contexto para IA

Bot de postulación automática a empleos en portales mexicanos (OCC, Computrabajo, Indeed) usando Selenium conectado a un navegador Brave/Chrome ya abierto (modo `--remote-debugging-port`). Uso personal/educativo, no headless por diseño (requiere sesión ya logueada manualmente).

## Idea central

El bot NO abre sesión ni resuelve captchas: el usuario abre Brave/Chrome con `--remote-debugging-port=9222`, inicia sesión a mano en el sitio, y el bot se conecta a esa misma ventana vía `debuggerAddress` de Selenium. A partir de ahí: busca por keyword, filtra vacantes relevantes por reglas de texto/regex en `config.yaml`, abre cada vacante y postula, resolviendo formularios/modales de preguntas cuando aparecen.

## Arquitectura (paquete `chambaflow/`)

El código vivía como scripts sueltos en la raíz (`cv_bot_occ.py`, `cv_bot_computrabajo.py`, `cv_bot_indeed.py`, `utils.py`, `search_session.py`, `main.py`) con ~3600 líneas y enorme duplicación entre los tres bots (17 métodos casi idénticos entre Computrabajo/Indeed, copy-paste). Se reestructuró a paquete:

```
main.py                  # wrapper delgado: from chambaflow.cli import main
chambaflow/
  cli.py                 # antes main.py: menú, argparse, run_once(), scheduler
  config.py              # load_config()
  driver.py              # antes utils.py: setup_driver, get_random_delay, log_postulacion, take_screenshot
  state.py               # antes search_session.py: rotación keywords, cuota diaria (sin cambios de lógica)
  filters.py             # RelevanceFilter — filtro de relevancia por título, ÚNICO (antes triplicado)
  browser_detect.py      # detect_os(), find_browser_path(), detect_available_browsers() (mac/Windows/Linux)
  bots/
    base.py              # BotBase (init común + self.relevance) y WizardApplyMixin (helpers de formulario)
    occ.py               # BotOCC(BotBase)
    computrabajo.py       # BotComputrabajo(BotBase, WizardApplyMixin)
    indeed.py            # BotIndeed(BotBase, WizardApplyMixin)
config/
  config.example.yaml    # antes "config.example copy.yaml" (nombre roto, corregido)
scripts/
  run_occ.sh / run_occ.ps1 / run_computrabajo.ps1
docs/
  README_OCC.md / CONTRIBUTING.md / CHANGELOG.md
```

`config.yaml`, `postulaciones.csv`, `chambaflow_state.yaml`, `tu_cv.pdf`, `screenshots/` siguen en la raíz (datos runtime del usuario, gitignored, rutas relativas asumidas desde el cwd del proyecto).

### Por qué `BotBase` / `WizardApplyMixin` y qué NO se unificó

- `BotBase`: constructor común (`driver`, `dry_run`, `controlled_mode`, `max_scan_per_keyword`, `search_url`, `postulaciones_csv`) + `self.relevance = RelevanceFilter(filter_config)` + `_is_relevant()` delegando ahí. Lo heredan los tres bots.
- `WizardApplyMixin` (solo `BotComputrabajo`/`BotIndeed`, **no** OCC): helpers del flujo multi-paso tipo wizard — `_get_input_label_or_aria`, `_get_radio_label`, `_has_visible_form_fields`, `_click_continue_button`/`_find_submit_button`/`_click_submit_button` (genéricos, reciben `CONTINUE_XPATHS`/`SUBMIT_XPATHS` como class attrs por subclase), `_capture_apply_failure_debug` (genérico vía `self.sitio.lower()` para nombrar logs/screenshots). OCC no lo usa porque su flujo es un modal de un solo paso con DOM propio (`_handle_knowledge_modal`), no un wizard multi-página.
- **Deliberadamente NO unificado** (queda por bot, con contenido/selectores propios): `_infer_input_value` (textos de respuesta genérica difieren por sitio), `_handle_questions_step` (orden/detalle de manejo de selects/radios difiere sutilmente), `_click_card`/`_panel_has_content`/paginación (selectores CSS específicos de cada sitio), `_detect_apply_page_type` (señales de texto por sitio). Fusionar esto tenía riesgo de alterar comportamiento de un flujo Selenium ya funcional sin forma de probarlo sin sesión real logueada — se dejó fuera a propósito.

### Efecto colateral relevante del refactor

`RelevanceFilter` usa matching por palabra completa vía regex con lookaround (`(?<![a-z0-9])termino(?![a-z0-9])`) para `exclude_terms`, evitando que `"java"` excluya `"javascript"`. Ese fix (commit `c47fe01`) antes solo estaba en OCC; ahora al ser un módulo único aplica también a Computrabajo e Indeed.

## Flujo de ejecución

```
main.py → chambaflow.cli.main()
  → choose_sitios_interactive() (menú questionary: Espacio/Enter) o --sitios en CLI
  → run_once(args, config_path, sitios_override)
      → load_config(config.yaml)                         # chambaflow/config.py
      → normalize_keywords()                              # chambaflow/state.py
      → calcula cuota restante del día (lee postulaciones.csv si daily_quota.count_from_csv)
      → carga/rota offset de keywords (chambaflow_state.yaml)
      → setup_driver()                                    # chambaflow/driver.py — conecta a debugger_address o lanza navegador propio
      → instancia BotOCC / BotComputrabajo / BotIndeed según `sitios`
      → por cada bot, por cada keyword (en orden rotado): bot.search_and_apply(keyword, cv_path, cupo_restante)
      → guarda nuevo offset de rotación en chambaflow_state.yaml
      → driver.quit()
  → si config.scheduler.enabled: bucle infinito que reintenta run_once() dentro de una ventana horaria, con pausa entre corridas (Ctrl+C para salir)
```

Cada bot comparte la misma interfaz pública: `search_and_apply(keyword, cv_path, max_apps) -> int` (aplicaciones realizadas).

## Esquema de `config.yaml` (claves relevantes)

- `sitios`: lista default si no se elige por menú/CLI (`occ`, `computrabajo`, `indeed`).
- `browser`: `"brave"` o `"chrome"`.
- `debugger_address`: `"127.0.0.1:9222"` para adjuntarse a navegador ya abierto. Vacío `""` → el bot lanza su propio navegador con perfil en `session_dir`.
- `session_dir`: carpeta de perfil persistente si no hay `debugger_address` (default `session_data_chrome`/`session_data_brave` según `browser`).
- `keywords`: lista de strings, o dicts `{query, extra_queries}` (ver `chambaflow.state.normalize_keywords`).
- `cv_path`: ruta al PDF del CV; si no existe, `run_once()` crea un placeholder de texto plano (para dry-run).
- `max_postulaciones_dia`: tope diario absoluto.
- `daily_quota.count_from_csv`: si `true`, resta del tope lo ya postulado hoy según `postulaciones.csv` (o `daily_quota.csv_path` / `postulaciones_csv`).
- `daily_quota.unlimited`: bypassa el tope por completo.
- `search.rotate_keywords` + `search.state_file`: entre corridas no siempre arranca en la primera keyword; guarda offset. `search.reset_keyword_rotation_daily` resetea el offset una vez por día.
- `occ_max_scan_per_keyword`: tope de vacantes escaneadas por keyword (compartido como parámetro para los tres bots).
- `occ_filter`: reglas de relevancia por título — `exclude_terms`, `exclude_regex`, `include_tech_terms`, `keyword_ignore_tokens`, `include_title_must_contain_any` (consumidas por `RelevanceFilter`), más filtros de antigüedad solo-OCC (`min_days_old`, `max_days_old`, `sort_by_date`, `reject_unknown_posting_age`, `max_pages_when_sorted_by_date`, `dedupe_days`).
  - **Importante**: `computrabajo_filter` e `indeed_filter` caen a `occ_filter` si no están definidos explícitamente (ver `chambaflow/cli.py::run_once`). Un solo bloque de filtro puede gobernar los tres sitios.
- `occ_modal.max_attempts` / `occ_modal.preferred_skill_ratings`: solo aplica al modal de conocimientos de OCC.
- `controlled_mode`: flag pasado a los bots (comportamiento más conservador/manual en pasos sensibles).
- `rotate_user_agent` / `stealth_mode`: opcionales en `setup_driver()`; `stealth_mode` inyecta CDP para ocultar `navigator.webdriver` (usarlo puede subir tasa de captchas, por eso off por default).
- `scheduler`: `enabled`, `start_hour`, `end_hour`, `pause_between_runs_min` — corre `run_once()` en loop dentro de ventana horaria.

## Lógica de relevancia de vacantes (`chambaflow/filters.py::RelevanceFilter`)

1. Si `include_title_must_contain_any` no está vacío y el título no contiene ninguno → descartar.
2. Si el título matchea `exclude_terms` (palabra completa) o `exclude_regex` → descartar.
3. Si el título contiene algún `include_tech_terms` → aceptar.
4. Fallback: comparar tokens de la keyword de búsqueda (ignorando `keyword_ignore_tokens`) contra el título.

## Dedupe / anti-doble-postulación

`BotOCC` normaliza título+empresa (`_normalize_signature`, quita acentos/espacios) y guarda firmas ya aplicadas en `state` (compartido vía `chambaflow_state.yaml`) para no repetir vacantes entre corridas (`_is_duplicate_recent`). Solo OCC lo hace. Computrabajo/Indeed detectan "ya aplicado" leyendo el panel (`_already_applied_panel` / equivalente) en vez de firma persistida.

## Gotchas no obvios

- Si `debugger_address` está seteado pero no hay navegador escuchando ahí, `run_once()` aborta antes de crear el driver (`debugger_is_available`) — no lanza navegador nuevo como fallback.
- `session_dir` solo se usa cuando NO hay `debugger_address` (perfiles persistentes y modo "adjuntarse a navegador abierto" son mutuamente excluyentes).
- `max_postulaciones_dia: 999` + `occ_max_scan_per_keyword: 999` en `config.yaml` actual = límites prácticamente desactivados; cuidado si se reactivan pruebas con esta config tal cual.
- `controlled_mode: false` en `config.yaml` actual difiere del ejemplo (`true`) — modo menos conservador.
- El CSV de postulaciones (`postulaciones.csv`) es la fuente de verdad para la cuota diaria entre corridas del scheduler; si se borra o cambia de ruta, la cuota se resetea de facto.
- `chambaflow/driver.py::log_postulacion()` escribe con header `Fecha, Hora, Sitio, Keyword, Vacante, Empresa, Status` (`Fecha`/`Hora` separados; antes era una sola columna `Fecha` con fecha+hora). Si detecta el header viejo (`Fecha, Sitio, Vacante, Empresa, Status`) migra el archivo in-place (deja `.bak` antes de tocarlo) — `_migrate_legacy_csv()`, se dispara en cada llamada a `log_postulacion()` pero es no-op una vez migrado. `count_postulaciones_hoy()` sigue funcionando igual porque `Fecha` ahora es exactamente `%Y-%m-%d` (antes bastaba con el prefijo).
- `tu_cv.pdf` puede ser un archivo placeholder de texto plano generado automáticamente si no existe — no asumir que siempre es un PDF real al depurar el flujo de subida de CV.
- Mensajes de consola y nombres de variables están en español; identificadores de clase/función en inglés — mantener ese mix (así lo pide `docs/CONTRIBUTING.md`).
- `chambaflow/bots/base.py::WizardApplyMixin._capture_apply_failure_debug` nombra logs/screenshots vía `self.sitio.lower()` (`"computrabajo_apply_failures.log"`, `"indeed_apply_failures.log"`) — si se cambia `sitio` en una subclase, cambian esos nombres de archivo.
- `chambaflow/browser_detect.py` solo detecta binarios instalados (para informar en pantalla vía `print_browser_status()`); NO cambia `config.yaml` ni fuerza el `browser` a usar — es meramente informativo por decisión explícita.
- `chambaflow/cli.py::print_welcome_banner()` elige entre wordmark ASCII completo (86 cols, con fondo de estrellas blancas vía `_render_on_starfield()`) o título compacto "ChambaFlow" según `console.size.width`, porque en terminales angostas (~80 cols, default en muchas consolas Windows) rich envolvía el wordmark carácter por carácter y salía ilegible. Si se edita el ASCII art, revalidar ambos anchos.
- `tests/` (pytest) cubre solo lógica pura sin Selenium/red: `RelevanceFilter`, `chambaflow/state.py`, `chambaflow/browser_detect.py`, migración de CSV en `chambaflow/driver.py`, y `BotBase.is_logged_in()` (con un `FakeDriver` de prueba, sin navegador real). Los bots en sí (`bots/occ.py`, `computrabajo.py`, `indeed.py`) no tienen tests — dependen de DOM real y sesión logueada, no son mockeables sin falsificar demasiado.

## Comandos útiles

```bash
python -u main.py                          # menú interactivo
python -u main.py --sitios occ,computrabajo # sin menú
python -u main.py --dry-run                 # simula sin postular real (loguea "Simulado" en CSV)
./scripts/run_occ.sh                        # mac: abre Brave debug + corre OCC
```

## Advertencia

Automatizar postulaciones puede violar Términos de Servicio de estos portales. Proyecto de uso personal/educativo — no diseñado para operación a escala ni evasión activa de detección.
