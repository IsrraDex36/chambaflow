"""
Piezas compartidas entre bots de sitios de empleo.

- BotBase: atributos de __init__ y filtro de relevancia comunes a los tres
  bots (OCC, Computrabajo, Indeed).
- WizardApplyMixin: helpers del flujo de postulación multi-paso ("wizard")
  que Computrabajo e Indeed comparten casi línea por línea (formulario
  in-page tras "Postularme" / "Apply"). OCC no lo usa: su flujo es un modal
  de un solo paso con DOM propio (ver cv_bot_occ.py / bots/occ.py).
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Optional

from selenium.webdriver.common.by import By

from chambaflow.driver import get_random_delay, take_screenshot
from chambaflow.filters import RelevanceFilter


class BotBase:
    sitio = "Sitio"

    # Detección de sesión iniciada: heurística por texto de página (mismo
    # estilo que _detect_apply_page_type/_application_confirmed en los bots).
    # Cada subclase define su URL y sus señales; ver bots/occ.py, computrabajo.py,
    # indeed.py. Si no hay LOGIN_CHECK_URL, is_logged_in() no verifica nada (None).
    LOGIN_CHECK_URL: str = ""
    LOGGED_OUT_SIGNALS: list[str] = []
    LOGGED_IN_SIGNALS: list[str] = []

    def __init__(
        self,
        driver,
        dry_run: bool = False,
        controlled_mode: bool = False,
        max_scan_per_keyword: int = 6,
        filter_config: Optional[dict[str, Any]] = None,
        postulaciones_csv: Optional[str] = None,
    ):
        self.driver = driver
        self.dry_run = dry_run
        self.controlled_mode = controlled_mode
        self.max_scan_per_keyword = max(1, int(max_scan_per_keyword))
        self.search_url = ""
        self.postulaciones_csv = (postulaciones_csv or "").strip() or None
        self.relevance = RelevanceFilter(filter_config)

    def _is_relevant(self, title, keyword_low):
        return self.relevance.is_relevant(title, keyword_low)

    def is_logged_in(self) -> Optional[bool]:
        """
        True/False si se pudo determinar por heurística de texto de página;
        None si no se pudo confirmar (sitio sin LOGIN_CHECK_URL, error de red,
        o página sin señales claras — no bloquea la corrida por sí solo).
        """
        if not self.LOGIN_CHECK_URL:
            return None
        try:
            self.driver.get(self.LOGIN_CHECK_URL)
            get_random_delay(1.5, 2.5)
            page_text = (
                self.driver.execute_script(
                    "return document.body ? document.body.innerText.toLowerCase() : '';"
                )
                or ""
            )
        except Exception as e:
            print(f"[{self.sitio}] No se pudo verificar sesión: {e}")
            return None

        has_in = any(s in page_text for s in self.LOGGED_IN_SIGNALS)
        has_out = any(s in page_text for s in self.LOGGED_OUT_SIGNALS)

        if has_in and not has_out:
            return True
        if has_out and not has_in:
            return False
        return None


class WizardApplyMixin:
    """
    Requiere en la subclase: self.driver, self.sitio, y las constantes de
    clase CONTINUE_XPATHS / SUBMIT_XPATHS con los selectores propios del sitio.
    """

    CONTINUE_XPATHS: list[str] = []
    SUBMIT_XPATHS: list[str] = []

    def _has_visible_form_fields(self):
        try:
            els = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[type='radio'], select, input[type='text'], input[type='number'], textarea"
            )
            return any(e.is_displayed() for e in els)
        except Exception:
            return False

    def _get_input_label_or_aria(self, inp):
        """Obtiene contexto del input (label asociado o aria-label)."""
        try:
            inp_id = inp.get_attribute("id")
            if inp_id:
                labels = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{inp_id}']")
                if labels:
                    return labels[0].text or ""
            aria = inp.get_attribute("aria-label") or ""
            if aria:
                return aria
            parent = inp.find_elements(By.XPATH, "./ancestor::label[1]")
            if parent:
                return parent[0].text or ""
        except Exception:
            pass
        return ""

    def _get_radio_label(self, radio_el):
        try:
            radio_id = radio_el.get_attribute("id")
            if radio_id:
                labels = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{radio_id}']")
                if labels:
                    return labels[0].text or ""
            parent = radio_el.find_elements(By.XPATH, "./ancestor::label[1]")
            if parent:
                return parent[0].text or ""
        except Exception:
            pass
        return ""

    def _click_continue_button(self):
        for xp in self.CONTINUE_XPATHS:
            try:
                btn = self.driver.find_element(By.XPATH, xp)
                if btn.is_displayed():
                    self.driver.execute_script("arguments[0].click();", btn)
                    get_random_delay(1.0, 2.0)
                    return True
            except Exception:
                continue
        return False

    def _find_submit_button(self):
        for xp in self.SUBMIT_XPATHS:
            try:
                btn = self.driver.find_element(By.XPATH, xp)
                if btn.is_displayed():
                    return btn
            except Exception:
                continue
        return None

    def _click_submit_button(self):
        btn = self._find_submit_button()
        if btn:
            self.driver.execute_script("arguments[0].click();", btn)
            get_random_delay(1.5, 2.5)
            return True
        return False

    def _capture_apply_failure_debug(self, id_value=None, id_label="id", title=""):
        try:
            os.makedirs("screenshots", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = self.sitio.lower()
            safe_id = re.sub(r"[^0-9A-Za-z_-]+", "_", str(id_value or "unknown"))
            safe_title = re.sub(r"[^0-9A-Za-z_-]+", "_", (title or "sin_titulo")).strip("_")[:50]

            page_path = take_screenshot(self.driver, f"{prefix}_fail_{safe_id}_{timestamp}")
            log_path = os.path.join("screenshots", f"{prefix}_apply_failures.log")

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(
                    f"{datetime.now().isoformat()} | "
                    f"{id_label}={id_value or 'unknown'} | "
                    f"title={safe_title} | "
                    f"url={self.driver.current_url} | "
                    f"search={self.search_url} | "
                    f"page_shot={page_path}\n"
                )

            print(f"[{self.sitio}] Debug guardado ({id_label}={id_value}, page={page_path})")
        except Exception as e:
            print(f"[{self.sitio}] No se pudo guardar debug: {e}")
