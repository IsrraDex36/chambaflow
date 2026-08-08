# Changelog

## Cambios recientes

- **Reestructura a paquete `chambaflow/`**: los `cv_bot_*.py` sueltos en la raíz pasan a `chambaflow/bots/`; `utils.py`/`search_session.py` a `chambaflow/driver.py`/`chambaflow/state.py`; scripts a `scripts/`; docs a `docs/`; `config.example copy.yaml` renombrado a `config/config.example.yaml`. `main.py` queda como wrapper delgado.
  - Nuevo `chambaflow/filters.py` (`RelevanceFilter`): el filtro de relevancia por título (antes triplicado en cada `cv_bot_*.py`) ahora vive en un solo lugar. Efecto colateral: el fix de exclusión por palabra completa (evita que `java` excluya `javascript`, ya aplicado solo a OCC) ahora también cubre Computrabajo e Indeed.
  - Nuevo `chambaflow/bots/base.py` (`BotBase` + `WizardApplyMixin`): elimina ~17 métodos casi idénticos duplicados entre `BotComputrabajo` y `BotIndeed` (helpers de formulario, botones continuar/enviar, captura de debug en fallos).

- **Filtro de relevancia desde `config.yaml`**: El bloque `occ_filter` permite definir sin tocar código qué vacantes se aceptan o descartan.
  - `exclude_terms`: textos que excluyen el título (ej. Java, Spring Boot).
  - `exclude_regex`: patrones regex para exclusiones.
  - `include_tech_terms`: tecnologías que sí te interesan (React, TypeScript, etc.).
  - `keyword_ignore_tokens`: palabras que se ignoran al comparar con la keyword.
- **Paginación OCC**: El bot recorre todas las páginas de resultados por keyword (no solo la primera).
- **Modal de conocimientos**: Espera explícita a que el modal se cierre, re-llenado si el botón no se habilita, fallback para cerrar con X/overlay, y consideración de éxito si la vacante ya figura como postulada aunque el modal no desaparezca.
- **Documentación**: README y README_OCC actualizados con instrucciones y uso de `occ_filter`.
