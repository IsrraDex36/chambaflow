import csv

from chambaflow.driver import log_postulacion, _migrate_legacy_csv, CSV_HEADER


def _read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def test_log_postulacion_creates_file_with_new_header(tmp_path):
    csv_path = str(tmp_path / "postulaciones.csv")
    log_postulacion(csv_path, "OCC", "Frontend Dev", "Empresa X", "Postulado", keyword="react")

    rows = _read_rows(csv_path)
    assert rows[0] == CSV_HEADER
    assert len(rows) == 2
    fecha, hora, sitio, keyword, vacante, empresa, status = rows[1]
    assert sitio == "OCC"
    assert keyword == "react"
    assert vacante == "Frontend Dev"
    assert empresa == "Empresa X"
    assert status == "Postulado"
    assert len(fecha) == 10 and fecha.count("-") == 2  # YYYY-MM-DD
    assert len(hora) == 8 and hora.count(":") == 2  # HH:MM:SS


def test_log_postulacion_appends_without_rewriting_header(tmp_path):
    csv_path = str(tmp_path / "postulaciones.csv")
    log_postulacion(csv_path, "OCC", "Vacante 1", "Empresa 1", "Postulado", keyword="react")
    log_postulacion(csv_path, "Indeed", "Vacante 2", "Empresa 2", "Postulado", keyword="python")

    rows = _read_rows(csv_path)
    assert len(rows) == 3
    assert rows[0] == CSV_HEADER


def test_migrate_legacy_csv_splits_fecha_and_adds_empty_keyword(tmp_path):
    csv_path = tmp_path / "postulaciones.csv"
    csv_path.write_text(
        "Fecha,Sitio,Vacante,Empresa,Status\n"
        "2026-06-27 14:18:29,OCC,Vacante Vieja,Empresa Vieja,Postulado\n",
        encoding="utf-8",
    )

    _migrate_legacy_csv(str(csv_path))

    rows = _read_rows(str(csv_path))
    assert rows[0] == CSV_HEADER
    assert rows[1] == ["2026-06-27", "14:18:29", "OCC", "", "Vacante Vieja", "Empresa Vieja", "Postulado"]

    backup = tmp_path / "postulaciones.csv.bak"
    assert backup.is_file()
    assert "Fecha,Sitio,Vacante,Empresa,Status" in backup.read_text(encoding="utf-8")


def test_migrate_legacy_csv_is_noop_on_new_format(tmp_path):
    csv_path = tmp_path / "postulaciones.csv"
    content = ",".join(CSV_HEADER) + "\n2026-08-08,10:00:00,OCC,react,V,E,Postulado\n"
    csv_path.write_text(content, encoding="utf-8")

    _migrate_legacy_csv(str(csv_path))

    assert csv_path.read_text(encoding="utf-8") == content
    assert not (tmp_path / "postulaciones.csv.bak").exists()


def test_migrate_legacy_csv_is_noop_when_file_missing(tmp_path):
    csv_path = tmp_path / "no_existe.csv"
    _migrate_legacy_csv(str(csv_path))  # no debe lanzar excepcion
    assert not csv_path.exists()


def test_migrate_legacy_csv_does_not_overwrite_existing_backup(tmp_path):
    csv_path = tmp_path / "postulaciones.csv"
    csv_path.write_text(
        "Fecha,Sitio,Vacante,Empresa,Status\n2026-06-27 14:18:29,OCC,V,E,Postulado\n",
        encoding="utf-8",
    )
    backup = tmp_path / "postulaciones.csv.bak"
    backup.write_text("backup original, no se debe perder", encoding="utf-8")

    _migrate_legacy_csv(str(csv_path))

    assert backup.read_text(encoding="utf-8") == "backup original, no se debe perder"
