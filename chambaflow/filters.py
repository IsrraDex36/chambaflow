"""
Filtro de relevancia por título de vacante, compartido por los tres bots
(OCC, Computrabajo, Indeed). Antes vivía triplicado como `_is_relevant` +
parsing de `filter_config` en cada `cv_bot_*.py`; ver CHANGELOG para el
historial de fixes que solo habían llegado a OCC (regex .net/c#).
"""
from __future__ import annotations

import re
from typing import Any, Optional

DEFAULT_EXCLUDE_TERMS = [
    "java ",
    " spring boot",
    "springboot",
    "spring framework",
    "hibernate",
    "jakarta ee",
    "j2ee",
    "jee",
]

DEFAULT_TECH_TERMS = [
    "react", "frontend", "front-end", "full stack", "fullstack",
    "developer", "desarrollador", "programador", "software",
    "backend", "typescript", "javascript", "next", "next.js",
    "angular", "vue", ".net", "web", "python", "node",
]

DEFAULT_KEYWORD_IGNORE = [
    "remoto", "mexico", "méxico", "puebla", "cdmx",
    "junior", "sr", "senior", "jr", "de", "en", "y", "-", "/",
]


class RelevanceFilter:
    """Decide si el título de una vacante es relevante para una keyword dada."""

    def __init__(self, filter_config: Optional[dict[str, Any]] = None):
        fc = filter_config or {}
        self.exclude_terms = [t.lower() for t in fc.get("exclude_terms", DEFAULT_EXCLUDE_TERMS)]
        self.exclude_regex = fc.get("exclude_regex", [])
        self.tech_terms = [t.lower() for t in fc.get("include_tech_terms", DEFAULT_TECH_TERMS)]
        self.keyword_ignore = set(
            t.lower() for t in fc.get("keyword_ignore_tokens", DEFAULT_KEYWORD_IGNORE)
        )
        self.include_title_must_contain_any = [
            str(t).lower().strip() for t in fc.get("include_title_must_contain_any", []) if str(t).strip()
        ]

    def is_relevant(self, title: str, keyword_low: str) -> bool:
        title_low = (title or "").lower().strip()
        if not title_low:
            return False

        if self.include_title_must_contain_any:
            if not any(term in title_low for term in self.include_title_must_contain_any):
                return False

        # Exclusión por palabra completa: evita que "java" excluya "javascript".
        # Lookaround sobre la clase alfanumérica (en vez de \b) porque términos
        # como ".net" o "c#" no tienen transición word/non-word junto a \b.
        for term in self.exclude_terms:
            t = (term or "").strip().lower()
            if not t:
                continue
            try:
                if re.search(r"(?<![a-z0-9])" + re.escape(t) + r"(?![a-z0-9])", title_low):
                    return False
            except re.error:
                if t in title_low:
                    return False

        for pattern in self.exclude_regex:
            try:
                if re.search(pattern, title_low):
                    return False
            except re.error:
                continue

        if any(t in title_low for t in self.tech_terms):
            return True

        tokens = [
            t.strip()
            for t in keyword_low.replace("/", " ").replace("-", " ").split()
            if t.strip() and t.strip().lower() not in self.keyword_ignore
        ]
        return any(tok in title_low for tok in tokens)
