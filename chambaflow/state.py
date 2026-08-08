"""
Estado de búsqueda y cuota diaria: rotación de keywords entre ejecuciones y conteo desde CSV.
"""
from __future__ import annotations

import csv
import os
from datetime import datetime
from typing import Any

import yaml


def normalize_keywords(raw: Any) -> list[str]:
    """
    Normaliza `keywords` del YAML:
    - Lista de strings: ["react", "python remoto"]
    - Lista mixta con dicts: { query: "react", extra_queries: ["desarrollador react"] }
    """
    if not raw:
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str):
            s = item.strip()
            if s:
                out.append(s)
        elif isinstance(item, dict):
            q = (item.get("query") or item.get("primary") or item.get("keyword") or "").strip()
            if q:
                out.append(q)
            for extra in item.get("extra_queries") or item.get("also_search") or []:
                es = str(extra).strip()
                if es:
                    out.append(es)
    # Sin duplicados conservando orden
    seen: set[str] = set()
    unique: list[str] = []
    for k in out:
        kl = k.lower()
        if kl not in seen:
            seen.add(kl)
            unique.append(k)
    return unique


def rotate_keyword_list(keywords: list[str], offset: int) -> list[str]:
    if not keywords:
        return []
    n = len(keywords)
    o = offset % n
    return keywords[o:] + keywords[:o]


def load_run_state(path: str) -> dict:
    if not path or not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_run_state(path: str, state: dict) -> None:
    if not path:
        return
    abs_path = os.path.abspath(path)
    d = os.path.dirname(abs_path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(state, f, allow_unicode=True, default_flow_style=False)


def count_postulaciones_hoy(
    csv_path: str,
    *,
    count_simulated: bool = False,
    today_prefix: str | None = None,
) -> int:
    """
    Cuenta filas del CSV cuya fecha (columna Fecha) es hoy.
    Por defecto no cuenta filas de dry-run (Status con 'simulado' o 'dry').
    """
    if not csv_path or not os.path.isfile(csv_path):
        return 0
    today = today_prefix or datetime.now().strftime("%Y-%m-%d")
    n = 0
    try:
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return 0
            for row in reader:
                fecha = (row.get("Fecha") or row.get("fecha") or "").strip()
                if not fecha.startswith(today):
                    continue
                status = (row.get("Status") or row.get("status") or "").lower()
                if not count_simulated and (
                    "simulado" in status or "dry" in status or "simulated" in status
                ):
                    continue
                n += 1
    except Exception:
        return 0
    return n
