from chambaflow.state import (
    normalize_keywords,
    rotate_keyword_list,
    load_run_state,
    save_run_state,
    count_postulaciones_hoy,
)


def test_normalize_keywords_plain_strings():
    assert normalize_keywords(["react", " python remoto "]) == ["react", "python remoto"]


def test_normalize_keywords_dict_with_extra_queries():
    raw = [{"query": "react", "extra_queries": ["desarrollador react", "react developer"]}]
    assert normalize_keywords(raw) == ["react", "desarrollador react", "react developer"]


def test_normalize_keywords_dedupes_case_insensitive_keeping_order():
    raw = ["React", "react", "Python", "PYTHON"]
    assert normalize_keywords(raw) == ["React", "Python"]


def test_normalize_keywords_empty_input():
    assert normalize_keywords([]) == []
    assert normalize_keywords(None) == []


def test_rotate_keyword_list_wraps_around():
    kw = ["a", "b", "c", "d"]
    assert rotate_keyword_list(kw, 0) == ["a", "b", "c", "d"]
    assert rotate_keyword_list(kw, 2) == ["c", "d", "a", "b"]
    assert rotate_keyword_list(kw, 4) == ["a", "b", "c", "d"]  # offset == len -> vuelve al inicio


def test_rotate_keyword_list_empty():
    assert rotate_keyword_list([], 3) == []


def test_run_state_roundtrip(tmp_path):
    state_file = str(tmp_path / "state.yaml")
    assert load_run_state(state_file) == {}

    save_run_state(state_file, {"keyword_offset": 5, "rotation_date": "2026-08-08"})
    loaded = load_run_state(state_file)
    assert loaded == {"keyword_offset": 5, "rotation_date": "2026-08-08"}


def test_load_run_state_corrupt_file_returns_empty(tmp_path):
    state_file = tmp_path / "state.yaml"
    state_file.write_text("::: esto no es yaml valido :::: [", encoding="utf-8")
    assert load_run_state(str(state_file)) == {}


def _write_csv(path, rows):
    header = "Fecha,Hora,Sitio,Keyword,Vacante,Empresa,Status\n"
    body = "\n".join(",".join(r) for r in rows)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + body + ("\n" if rows else ""))


def test_count_postulaciones_hoy_counts_only_today_and_excludes_simulado(tmp_path):
    csv_path = str(tmp_path / "postulaciones.csv")
    _write_csv(csv_path, [
        ["2026-08-08", "10:00:00", "OCC", "react", "Vacante A", "Empresa A", "Postulado"],
        ["2026-08-08", "11:00:00", "OCC", "react", "Vacante B", "Empresa B", "Simulado"],
        ["2026-08-07", "09:00:00", "OCC", "react", "Vacante C", "Empresa C", "Postulado"],
    ])
    assert count_postulaciones_hoy(csv_path, today_prefix="2026-08-08") == 1


def test_count_postulaciones_hoy_can_include_simulado(tmp_path):
    csv_path = str(tmp_path / "postulaciones.csv")
    _write_csv(csv_path, [
        ["2026-08-08", "10:00:00", "OCC", "react", "Vacante A", "Empresa A", "Postulado"],
        ["2026-08-08", "11:00:00", "OCC", "react", "Vacante B", "Empresa B", "Simulado"],
    ])
    assert count_postulaciones_hoy(csv_path, today_prefix="2026-08-08", count_simulated=True) == 2


def test_count_postulaciones_hoy_missing_file_returns_zero(tmp_path):
    assert count_postulaciones_hoy(str(tmp_path / "no_existe.csv")) == 0


def test_count_postulaciones_hoy_empty_file_returns_zero(tmp_path):
    csv_path = tmp_path / "vacio.csv"
    csv_path.write_text("", encoding="utf-8")
    assert count_postulaciones_hoy(str(csv_path)) == 0
