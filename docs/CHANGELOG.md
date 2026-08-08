# Changelog

## Cambios recientes

- **CI con GitHub Actions** (`.github/workflows/tests.yml`): corre `pyflakes` y la suite de `pytest` en cada push/PR a `main`, en Python 3.9 y 3.12. Badge de estado en el README.

- **`config.yaml` se autogenera desde la plantilla si falta.** `chambaflow/config.py::ensure_config_exists()` copia `config/config.example.yaml` a `config.yaml` (o a `--config` que se haya pasado) la primera vez que no existe, y avisa en consola. No pisa nunca un `config.yaml` ya existente.

- **Fix: ya no se genera un `tu_cv.pdf` falso.** `run_once()` creaba en silencio un archivo de texto plano ("Fake CV content") si `cv_path` no existía, y en una corrida real ese texto se hubiera subido como CV a vacantes reales. Ahora solo advierte en consola que falta el CV y que ese paso va a fallar; no crea nada.

- **Suite de tests (`tests/`, pytest)**: 38 tests sobre la lógica pura del proyecto — `RelevanceFilter`, rotación de keywords y cuota diaria (`state.py`), detección de SO/navegador (`browser_detect.py`), migración de `postulaciones.csv` y `BotBase.is_logged_in()` (con un `FakeDriver`, sin navegador real). Los bots por sitio quedan sin test: dependen de DOM real logueado. `pytest` agregado a `requirements.txt`; sección de tests en `docs/CONTRIBUTING.md`.

- **Rediseño de `postulaciones.csv`**: header nuevo `Fecha, Hora, Sitio, Keyword, Vacante, Empresa, Status` (antes `Fecha` mezclaba fecha+hora y no existía `Keyword`). El keyword de búsqueda que produjo cada postulación ahora queda registrado. `log_postulacion()` migra automáticamente cualquier CSV con el header viejo (deja un `.bak` antes de tocarlo); `count_postulaciones_hoy()` sigue funcionando igual.

- **README reescrito**: mecanismo interno explicado con detalle real (por qué se conecta al navegador en vez de headless, algoritmo exacto del filtro de relevancia, dedupe, cuota, para qué sirve `screenshots/`, scheduler). Incluye Indeed (antes ausente del título y de la tabla de sitios soportados). Badge de Python corregido a 3.9+ (antes decía 3.10+, incorrecto tras el fix de `Optional[]`).

- **Reestructura a paquete `chambaflow/`**: los `cv_bot_*.py` sueltos en la raíz pasan a `chambaflow/bots/`; `utils.py`/`search_session.py` a `chambaflow/driver.py`/`chambaflow/state.py`; scripts a `scripts/`; docs a `docs/`; `config.example copy.yaml` renombrado a `config/config.example.yaml`. `main.py` queda como wrapper delgado.
  - Nuevo `chambaflow/filters.py` (`RelevanceFilter`): el filtro de relevancia por título (antes triplicado en cada `cv_bot_*.py`) ahora vive en un solo lugar. Efecto colateral: el fix de exclusión por palabra completa (evita que `java` excluya `javascript`, ya aplicado solo a OCC) ahora también cubre Computrabajo e Indeed.
  - Nuevo `chambaflow/bots/base.py` (`BotBase` + `WizardApplyMixin`): elimina ~17 métodos casi idénticos duplicados entre `BotComputrabajo` y `BotIndeed` (helpers de formulario, botones continuar/enviar, captura de debug en fallos).
  - Nuevo `chambaflow/browser_detect.py`: detecta SO (mac/Windows/Linux) y rutas de Brave/Chrome instaladas, agregando soporte real para Chrome en mac y para Linux (antes ausente en ambos). La pantalla de bienvenida muestra "Sistema: X | Navegadores detectados: ..." sin tocar `config.yaml`.
  - `BotBase.is_logged_in()`: heurística de texto de página por sitio (`LOGGED_IN_SIGNALS`/`LOGGED_OUT_SIGNALS`). `run_once()` salta un sitio completo si detecta que no hay sesión iniciada, en vez de scrapear una pantalla de login en bucle.
  - Banner de bienvenida rediseñado: wordmark con fondo de estrellas blancas (`_render_on_starfield()`), con fallback a título compacto en terminales angostas (~80 cols) donde antes se rompía carácter por carácter. Versión a v2.0, tagline con los 3 sitios soportados.
  - Menú de sitios: se quitó el listado numerado manual que duplicaba lo que ya renderiza `questionary.checkbox`; instrucciones más claras sobre el fallback a `config.yaml`.

- **Filtro de relevancia desde `config.yaml`**: El bloque `occ_filter` permite definir sin tocar código qué vacantes se aceptan o descartan.
  - `exclude_terms`: textos que excluyen el título (ej. Java, Spring Boot).
  - `exclude_regex`: patrones regex para exclusiones.
  - `include_tech_terms`: tecnologías que sí te interesan (React, TypeScript, etc.).
  - `keyword_ignore_tokens`: palabras que se ignoran al comparar con la keyword.
- **Paginación OCC**: El bot recorre todas las páginas de resultados por keyword (no solo la primera).
- **Modal de conocimientos**: Espera explícita a que el modal se cierre, re-llenado si el botón no se habilita, fallback para cerrar con X/overlay, y consideración de éxito si la vacante ya figura como postulada aunque el modal no desaparezca.
- **Documentación**: README y README_OCC actualizados con instrucciones y uso de `occ_filter`.
