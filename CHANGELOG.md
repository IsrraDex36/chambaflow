# Changelog

## Cambios recientes

- **Filtro de relevancia desde `config.yaml`**: El bloque `occ_filter` permite definir sin tocar código qué vacantes se aceptan o descartan.
  - `exclude_terms`: textos que excluyen el título (ej. Java, Spring Boot).
  - `exclude_regex`: patrones regex para exclusiones.
  - `include_tech_terms`: tecnologías que sí te interesan (React, TypeScript, etc.).
  - `keyword_ignore_tokens`: palabras que se ignoran al comparar con la keyword.
- **Paginación OCC**: El bot recorre todas las páginas de resultados por keyword (no solo la primera).
- **Modal de conocimientos**: Espera explícita a que el modal se cierre, re-llenado si el botón no se habilita, fallback para cerrar con X/overlay, y consideración de éxito si la vacante ya figura como postulada aunque el modal no desaparezca.
- **Documentación**: README y README_OCC actualizados con instrucciones y uso de `occ_filter`.
