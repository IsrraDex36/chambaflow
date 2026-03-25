from utils import get_random_delay, take_screenshot, log_postulacion
import re
import os
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException,
    ElementClickInterceptedException,
)

# ─────────────────────────────────────────────────────────────
#  ESTRUCTURA REAL DE INDEED MX (HTML inspeccionado 2026-03)
#
#  Búsqueda:
#    https://mx.indeed.com/jobs?q={keyword}&l=
#    ej: https://mx.indeed.com/jobs?q=desarrollador+react
#
#  Cards en el listado:
#    <div class="cardOutline tapItem ... result job_{JK}">
#      <a data-jk="{JK}" class="jcs-JobTitle">
#        <span title="Título">Título</span>
#      </a>
#      <span data-testid="company-name">Empresa</span>
#      <div data-testid="text-location">Ciudad</div>
#      <!-- IndeedApply (postulación directa): -->
#      <span data-testid="indeedApply">Postúlate rápidamente</span>
#    </div>
#
#  Panel de detalle (lado derecho):
#    <div id="vjs-container"> o <div id="viewJobSSRRoot">
#      <button href="...applystart..." aria-label="Postularse en la página de la empresa">
#          → SKIP: redirige a sitio externo
#      </button>
#      <button data-testid="indeedApply" o span[data-testid="indeedApply"]>
#          → OK: flujo interno Indeed
#      </button>
#    </div>
#
#  Flujo IndeedApply (ventana/iframe aparte):
#    Indeed abre un modal/popup con pasos:
#    1. Datos de contacto (pre-rellenados si ya tiene perfil)
#    2. CV (usar el existente o subir nuevo)
#    3. Preguntas adicionales del empleador
#    4. Revisión y envío
#    Confirmación: texto "Tu solicitud fue enviada" / "Application submitted"
# ─────────────────────────────────────────────────────────────

# Selectores principales
CARD_SEL      = "div.cardOutline.tapItem[class*='result']"
JK_ATTR       = "data-jk"                     # en el <a> del título
TITLE_SEL     = "a.jcs-JobTitle span[title]"
COMPANY_SEL   = "span[data-testid='company-name']"
LOCATION_SEL  = "div[data-testid='text-location']"
QUICK_APPLY   = "span[data-testid='indeedApply']"  # badge "Postúlate rápidamente"

# Panel de detalle
DETAIL_PANEL  = "#vjs-container, #viewJobSSRRoot, .fastviewjob"
APPLY_EXT_BTN = "button[aria-label*='página de la empresa']"   # SKIP
APPLY_NOW_BTN = "button[data-testid='indeedApply'], .ia-IndeedApplyButton, button[aria-label*='Postularse ahora'], button[aria-label*='Apply now']"

# IndeedApply modal/popup
MODAL_SEL     = "div[id*='indeedapply'], iframe[id*='ia-'], div.ia-BasePage, div[class*='ia-']"


class BotIndeed:
    def __init__(
        self,
        driver,
        dry_run: bool = False,
        controlled_mode: bool = False,
        max_scan_per_keyword: int = 6,
        filter_config: dict | None = None,
        postulaciones_csv: str | None = None,
    ):
        self.driver = driver
        self.dry_run = dry_run
        self.sitio = "Indeed"
        self.controlled_mode = controlled_mode
        self.max_scan_per_keyword = max(1, int(max_scan_per_keyword))
        self.search_url = ""
        self.main_window = None
        self.postulaciones_csv = (postulaciones_csv or "").strip() or None

        fc = filter_config or {}
        self.contact = fc.get("contact", {})
        self.filter_exclude_terms = [
            t.lower() for t in fc.get("exclude_terms", [
                "java ",
                " spring boot",
                "springboot",
                "spring framework",
                "hibernate",
                "jakarta ee",
                "j2ee",
                "jee",
            ])
        ]
        self.filter_exclude_regex = fc.get("exclude_regex", [])
        self.filter_tech_terms = [
            t.lower() for t in fc.get("include_tech_terms", [
                "react", "frontend", "front-end", "full stack", "fullstack",
                "developer", "desarrollador", "programador", "software",
                "backend", "typescript", "javascript", "next", "next.js",
                "angular", "vue", ".net", "web", "python", "node",
            ])
        ]
        self.filter_keyword_ignore = set(
            t.lower() for t in fc.get("keyword_ignore_tokens", [
                "remoto", "mexico", "méxico", "puebla", "cdmx",
                "junior", "sr", "senior", "jr", "de", "en", "y", "-", "/",
            ])
        )
        self.include_title_must_contain_any = [
            str(t).lower().strip() for t in fc.get("include_title_must_contain_any", []) if str(t).strip()
        ]

    # ─────────────────────────────────────────────
    # ENTRY POINT
    # ─────────────────────────────────────────────

    def search_and_apply(self, keyword, cv_path, max_apps):
        apps_done = 0
        keyword_low = (keyword or "").lower()

        q = re.sub(r"\s+", "+", keyword.strip())
        self.search_url = f"https://mx.indeed.com/jobs?q={q}&l="
        self.main_window = None

        try:
            print(f"[{self.sitio}] Buscando: {keyword}")
            self.driver.get(self.search_url)
            get_random_delay(2.5, 4.0)
            self.main_window = self.driver.current_window_handle

            if self.dry_run:
                print(f"[{self.sitio}] [DRY-RUN] Simulando búsqueda...")
                return min(2, max_apps)

            max_scan = (
                self.max_scan_per_keyword
                if self.controlled_mode
                else max(30, max_apps * 8)
            )
            seen_jks: set[str] = set()
            page_num = 1

            while apps_done < max_apps:
                if not self._wait_for_cards():
                    print(f"[{self.sitio}] No se cargaron cards en pág {page_num}.")
                    break

                job_items = self._collect_job_items(limit=max_scan)
                new_items = [j for j in job_items if j["jk"] not in seen_jks]
                print(
                    f"[{self.sitio}] Pág {page_num}: "
                    f"{len(job_items)} cards ({len(new_items)} nuevas, "
                    f"{sum(1 for j in new_items if j.get('quick_apply'))} con IndeedApply)"
                )

                if not new_items:
                    print(f"[{self.sitio}] Sin nuevas vacantes en pág {page_num}.")
                    break

                for idx, item in enumerate(new_items):
                    if apps_done >= max_apps:
                        break

                    jk      = item["jk"]
                    title   = item.get("title") or "Sin título"
                    company = item.get("company") or ""
                    seen_jks.add(jk)

                    # Solo IndeedApply (tiene badge "Postúlate rápidamente")
                    if not item.get("quick_apply"):
                        print(f"[{self.sitio}] Saltada (no es IndeedApply): {title}")
                        continue

                    if not self._is_relevant(title, keyword_low):
                        print(f"[{self.sitio}] Saltada (no relevante): {title}")
                        continue

                    print(
                        f"[{self.sitio}] [{idx+1}/{len(new_items)}] "
                        f"{title} — {company}"
                    )

                    # Hacer click en la card para cargar el panel
                    if not self._click_card(jk, title):
                        print(f"[{self.sitio}] No se pudo abrir card: {title}")
                        continue

                    # Verificar en el panel si es IndeedApply (no externa)
                    if self._is_external_apply():
                        print(f"[{self.sitio}] Saltada (apply externo en panel): {title}")
                        continue

                    if self.apply_to_job(cv_path, jk=jk, title=title, company=company):
                        apps_done += 1

                if apps_done >= max_apps:
                    break

                next_url = self._get_next_page_url()
                if not next_url:
                    print(f"[{self.sitio}] Sin página siguiente, fin.")
                    break

                page_num += 1
                self.driver.get(next_url)
                get_random_delay(2.0, 3.5)
                self.main_window = self.driver.current_window_handle

        except Exception as e:
            take_screenshot(self.driver, "indeed_main_error")
            print(f"[{self.sitio}] Error principal: {e}")

        print(f"[{self.sitio}] Postulaciones '{keyword}': {apps_done}")
        return apps_done

    # ─────────────────────────────────────────────
    # ESPERA Y CONTEO DE CARDS
    # ─────────────────────────────────────────────

    def _wait_for_cards(self, timeout=15):
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "div.cardOutline")
                )
            )
            get_random_delay(0.8, 1.5)
            return True
        except TimeoutException:
            src = (self.driver.page_source or "").lower()
            if "captcha" in src or "robot" in src:
                print(f"[{self.sitio}] ⚠️  CAPTCHA detectado. Esperando 30s...")
                get_random_delay(28, 35)
                return len(self.driver.find_elements(By.CSS_SELECTOR, "div.cardOutline")) > 0
            return False

    # ─────────────────────────────────────────────
    # PAGINACIÓN
    # ─────────────────────────────────────────────

    def _get_next_page_url(self):
        """
        Indeed MX pagina con un parámetro &start=N en la URL,
        o tiene un botón "Siguiente" / aria-label="Next Page".
        """
        try:
            # Botón "Siguiente" o "Next"
            btns = self.driver.find_elements(
                By.CSS_SELECTOR,
                "a[aria-label='Next Page'], a[aria-label='Siguiente página'], "
                "a[data-testid='pagination-page-next']"
            )
            for btn in btns:
                href = btn.get_attribute("href")
                if href:
                    return href

            # Fallback: incrementar &start= en la URL actual
            current = self.driver.current_url
            m = re.search(r"[?&]start=(\d+)", current)
            start = int(m.group(1)) if m else 0
            next_start = start + 10
            if "start=" in current:
                return re.sub(r"start=\d+", f"start={next_start}", current)
            sep = "&" if "?" in current else "?"
            return f"{current}{sep}start={next_start}"

        except Exception as e:
            print(f"[{self.sitio}] Error obteniendo siguiente página: {e}")
        return None

    # ─────────────────────────────────────────────
    # RECOLECCIÓN DE VACANTES
    # ─────────────────────────────────────────────

    def _collect_job_items(self, limit=100):
        """
        Lee jk, título, empresa, ubicación y si tiene IndeedApply de cada card.

        HTML confirmado:
          <div class="cardOutline tapItem result job_{JK}" ...>
            <a data-jk="{JK}" class="jcs-JobTitle">
              <span title="Título">Título</span>
            </a>
            <span data-testid="company-name">Empresa</span>
            <div data-testid="text-location">Ciudad</div>
            <span data-testid="indeedApply">Postúlate rápidamente</span>  ← solo si IndeedApply
          </div>
        """
        try:
            items = self.driver.execute_script("""
                const cards = document.querySelectorAll('div.cardOutline');
                const results = [];

                cards.forEach(card => {
                    // jk desde el enlace del título
                    const link = card.querySelector('a[data-jk]');
                    if (!link) return;
                    const jk = link.getAttribute('data-jk');
                    if (!jk) return;

                    const titleEl = link.querySelector('span[title]');
                    const title = titleEl ? titleEl.getAttribute('title') : (link.innerText || '').trim();

                    const compEl = card.querySelector("[data-testid='company-name']");
                    const company = compEl ? compEl.innerText.trim() : '';

                    const locEl = card.querySelector("[data-testid='text-location']");
                    const location = locEl ? locEl.innerText.trim() : '';

                    // IndeedApply: badge "Postúlate rápidamente"
                    const iaEl = card.querySelector("[data-testid='indeedApply']");
                    const quick_apply = !!iaEl;

                    results.push({ jk, title, company, location, quick_apply });
                });

                return results.slice(0, arguments[0]);
            """, limit)
            return items or []
        except Exception as e:
            print(f"[{self.sitio}] Error recolectando items: {e}")
            return []

    # ─────────────────────────────────────────────
    # CLICK EN CARD → PANEL DERECHO
    # ─────────────────────────────────────────────

    def _click_card(self, jk, expected_title=""):
        """
        Hace click en la card con data-jk=jk para cargar el panel derecho.
        Indeed carga el detalle inline sin navegación completa.
        """
        link_css = f"a[data-jk='{jk}']"

        # Intento 1: JS click en el enlace del título
        try:
            link = self.driver.find_element(By.CSS_SELECTOR, link_css)
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center',behavior:'smooth'});",
                link
            )
            get_random_delay(0.5, 0.9)
            self.driver.execute_script("arguments[0].click();", link)
            get_random_delay(1.8, 3.0)

            if self._panel_loaded():
                return True
        except StaleElementReferenceException:
            pass
        except Exception as e:
            print(f"[{self.sitio}] JS click error jk={jk[:8]}…: {e}")

        # Intento 2: ActionChains
        try:
            link = self.driver.find_element(By.CSS_SELECTOR, link_css)
            ActionChains(self.driver).move_to_element(link).pause(0.3).click().perform()
            get_random_delay(1.8, 3.0)
            if self._panel_loaded():
                return True
        except Exception as e:
            print(f"[{self.sitio}] ActionChains error jk={jk[:8]}…: {e}")

        # Intento 3: verificar igual
        return self._panel_loaded()

    def _panel_loaded(self, timeout=5):
        """Verifica que el panel de detalle está visible."""
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "#vjs-container, #viewJobSSRRoot, .fastviewjob, .jobsearch-ViewJobContainer")
                )
            )
            return True
        except TimeoutException:
            return False

    # ─────────────────────────────────────────────
    # VERIFICACIÓN TIPO DE APPLY EN PANEL
    # ─────────────────────────────────────────────

    def _is_external_apply(self):
        """
        True si el panel solo muestra "Postularse en la página de la empresa"
        y no hay botón de IndeedApply.
        """
        try:
            # Botón externo presente
            ext_btns = self.driver.find_elements(
                By.CSS_SELECTOR,
                "button[aria-label*='página de la empresa'], "
                "a[aria-label*='página de la empresa']"
            )
            has_external = any(b.is_displayed() for b in ext_btns)

            # Botón IndeedApply presente
            ia_btns = self.driver.find_elements(
                By.CSS_SELECTOR,
                ".ia-IndeedApplyButton, button[data-testid='indeedApply'], "
                "button[aria-label*='Postularse ahora'], button[aria-label*='Apply now'], "
                "span[id*='indeedApplyButton'], button[id*='indeedApplyButton']"
            )
            has_ia = any(b.is_displayed() for b in ia_btns)

            if has_external and not has_ia:
                return True
            return False
        except Exception:
            return False

    # ─────────────────────────────────────────────
    # FILTRADO DE RELEVANCIA
    # ─────────────────────────────────────────────

    def _is_relevant(self, title, keyword_low):
        title_low = (title or "").lower().strip()
        if not title_low:
            return False

        if self.include_title_must_contain_any:
            if not any(term in title_low for term in self.include_title_must_contain_any):
                return False

        for term in self.filter_exclude_terms:
            if term and term in title_low:
                return False

        for pattern in self.filter_exclude_regex:
            try:
                if re.search(pattern, title_low):
                    return False
            except re.error:
                continue

        if any(t in title_low for t in self.filter_tech_terms):
            return True

        tokens = [
            t.strip()
            for t in keyword_low.replace("/", " ").replace("-", " ").split()
            if t.strip() and t.strip().lower() not in self.filter_keyword_ignore
        ]
        return any(tok in title_low for tok in tokens)

    # ─────────────────────────────────────────────
    # POSTULACIÓN
    # ─────────────────────────────────────────────

    def apply_to_job(self, cv_path, jk=None, title="", company=""):
        """
        Flujo de postulación IndeedApply:
        1. Click en botón IndeedApply del panel
        2. Indeed abre nueva ventana/popup con el formulario
        3. Completar pasos del formulario
        4. Volver a la ventana principal
        """
        windows_before = set(self.driver.window_handles)

        if not self._click_indeed_apply():
            print(f"[{self.sitio}] No se encontró botón IndeedApply para: {title}")
            return False

        print(f"[{self.sitio}] Aplicando a: {title}")
        get_random_delay(2.5, 4.0)

        # Indeed puede abrir nueva ventana o iframe modal
        new_windows = set(self.driver.window_handles) - windows_before
        success = False

        if new_windows:
            # Cambiar a la nueva ventana
            new_win = new_windows.pop()
            self.driver.switch_to.window(new_win)
            get_random_delay(1.5, 2.5)
            print(f"[{self.sitio}] Nueva ventana abierta: {self.driver.current_url[:60]}")

            success = self._handle_indeed_apply_flow(cv_path, jk=jk, title=title)

            # Cerrar ventana de apply y volver a la principal
            try:
                self.driver.close()
            except Exception:
                pass
            try:
                self.driver.switch_to.window(self.main_window)
            except Exception:
                handles = self.driver.window_handles
                if handles:
                    self.driver.switch_to.window(handles[0])
            get_random_delay(1.0, 2.0)

        else:
            # Modal en la misma ventana (iframe u overlay)
            success = self._handle_indeed_apply_inline(cv_path, jk=jk, title=title)

        if success and self.postulaciones_csv and not self.dry_run:
            log_postulacion(
                self.postulaciones_csv,
                self.sitio,
                title or "Sin título",
                company or "",
                "Postulado",
            )
        return success

    def _try_click_apply_button(self, btn):
        """
        Intenta clic en el botón con varias estrategias (Indeed carga el handler por JS).
        Orden: ActionChains (simula ratón real) → clic nativo → clic por JavaScript.
        """
        def scroll_to():
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center', behavior:'instant'});", btn
            )
            get_random_delay(0.4, 0.7)

        scroll_to()

        # 1) ActionChains: simula movimiento del ratón + clic (React/Indeed suelen reaccionar)
        try:
            ac = ActionChains(self.driver)
            ac.move_to_element(btn).pause(0.2).click().perform()
            get_random_delay(0.5, 1.0)
            return True
        except (ElementClickInterceptedException, StaleElementReferenceException, Exception):
            pass

        # 2) Clic nativo de Selenium (dispara eventos reales del navegador)
        try:
            btn.click()
            get_random_delay(0.5, 1.0)
            return True
        except (ElementClickInterceptedException, StaleElementReferenceException, Exception):
            pass

        # 3) Clic por JavaScript (bypass si algo tapa el botón)
        try:
            self.driver.execute_script("arguments[0].click();", btn)
            get_random_delay(0.5, 1.0)
            return True
        except (StaleElementReferenceException, Exception):
            pass

        return False

    def _click_indeed_apply(self):
        """
        Hace click en el botón IndeedApply del panel de detalle.
        Indeed carga el botón y el handler por JavaScript; se espera a que sea
        clickeable y se prueba ActionChains, clic nativo y clic JS.
        """
        # 1) Esperar a que el widget de apply esté en DOM (data-click-handler se adjunta después)
        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    ".indeed-apply-widget, #indeedApplyButton, #jobsearch-ViewJobButtons-container"
                ))
            )
        except TimeoutException:
            pass
        get_random_delay(0.8, 1.5)  # dar tiempo a que el handler "attached" esté listo

        # 2) Scroll al contenedor de botones
        try:
            container = self.driver.find_element(
                By.CSS_SELECTOR,
                "#jobsearch-ViewJobButtons-container, #applyButtonLinkContainer, "
                "#vjs-container, #viewJobSSRRoot"
            )
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center', behavior:'smooth'});",
                container
            )
            get_random_delay(0.5, 1.0)
        except Exception:
            pass

        # 3) Esperar a que el botón sea clickeable (no solo presente)
        btn = None
        try:
            btn = WebDriverWait(self.driver, 12).until(
                EC.element_to_be_clickable((By.ID, "indeedApplyButton"))
            )
        except TimeoutException:
            try:
                btn = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((
                        By.CSS_SELECTOR,
                        "button[data-testid='indeedApplyButton-test'], "
                        ".jobsearch-IndeedApplyButton button, .ia-IndeedApplyButton button"
                    ))
                )
            except TimeoutException:
                pass

        if btn and self._try_click_apply_button(btn):
            return True

        # 4) Fallback: recorrer selectores y probar cada candidato
        selectors = [
            "#indeedApplyButton",
            "button[data-testid='indeedApplyButton-test']",
            ".jobsearch-IndeedApplyButton button",
            ".ia-IndeedApplyButton button",
            "button[aria-label*='Postularse ahora']",
            "button[aria-label*='Apply now']",
            "button[id*='indeedApplyButton']",
            ".indeed-apply-button",
            "span.indeed-apply-button-label",
            "#jobsearch-ViewJobButtons-container button:not([aria-label*='Guardar']):not([aria-label*='Compartir']):not([aria-label*='No me interesa'])",
        ]
        for sel in selectors:
            try:
                for candidate in self.driver.find_elements(By.CSS_SELECTOR, sel):
                    if not candidate.is_displayed():
                        continue
                    label = (candidate.get_attribute("aria-label") or "").lower()
                    if "página de la empresa" in label:
                        continue
                    if self._try_click_apply_button(candidate):
                        return True
            except (StaleElementReferenceException, Exception):
                continue

        # 5) XPath por texto dentro del botón
        try:
            for candidate in self.driver.find_elements(By.XPATH,
                "//button[contains(., 'Postularse ahora') or contains(., 'Apply now') or contains(., 'Postúlate')]"
            ):
                label = (candidate.get_attribute("aria-label") or "").lower()
                if "página de la empresa" in label or not candidate.is_displayed():
                    continue
                if self._try_click_apply_button(candidate):
                    return True
        except Exception:
            pass

        # 6) Último recurso: disparar evento click por JS en el primer botón con id indeedApplyButton
        try:
            el = self.driver.execute_script(
                "var el = document.getElementById('indeedApplyButton');"
                "if (el) { el.scrollIntoView({block:'center'}); return el; } return null;"
            )
            if el:
                self.driver.execute_script(
                    "arguments[0].dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));",
                    el
                )
                get_random_delay(0.5, 1.0)
                return True
        except Exception as e:
            print(f"[{self.sitio}] Fallback dispatchEvent apply: {e}")

        return False

    # ─────────────────────────────────────────────
    # FLUJO INDEED APPLY (nueva ventana)
    # ─────────────────────────────────────────────

    def _handle_indeed_apply_flow(self, cv_path, jk=None, title=""):
        """
        Navega el wizard IndeedApply en la nueva ventana.
        Indeed abre: https://m5.apply.indeed.com/... o similar
        Pasos típicos:
          1. Datos de contacto / confirmación
          2. CV (usar existente o subir nuevo)
          3. Preguntas del empleador
          4. Revisión → Enviar
        """
        max_steps = 12
        for step in range(1, max_steps + 1):
            get_random_delay(1.0, 2.0)
            print(f"[{self.sitio}] Apply step {step}/{max_steps} | URL: {self.driver.current_url[:60]}")

            page_type = self._detect_indeed_page_type()
            print(f"[{self.sitio}] Tipo de paso: {page_type}")

            if page_type == "confirmation":
                print(f"[{self.sitio}] ✅ Postulación confirmada: {title}")
                return True

            if page_type == "already_applied":
                print(f"[{self.sitio}] Ya postulado: {title}")
                return False

            if page_type == "error":
                print(f"[{self.sitio}] Error en el flujo: {title}")
                self._capture_apply_failure_debug(jk=jk, title=title)
                return False

            if page_type == "cv":
                self._handle_cv_step(cv_path)

            elif page_type == "questions":
                self._handle_questions_step()

            elif page_type == "contact":
                # Datos de contacto: normalmente pre-rellenados
                self._handle_contact_step()

            elif page_type == "review":
                if self._click_submit_button():
                    get_random_delay(2.5, 4.0)
                    if self._indeed_application_confirmed():
                        return True
                    continue
                break

            # Intentar continuar al siguiente paso
            if not self._click_continue_button():
                # Puede que ya estemos en el último paso o hubo un error
                get_random_delay(1.0, 1.5)
                if self._indeed_application_confirmed():
                    return True
                # Intentar submit directo
                if self._click_submit_button():
                    get_random_delay(2.0, 3.5)
                    if self._indeed_application_confirmed():
                        return True
                break

            get_random_delay(1.2, 2.2)

        if self._indeed_application_confirmed():
            return True

        self._capture_apply_failure_debug(jk=jk, title=title)
        return False

    def _handle_indeed_apply_inline(self, cv_path, jk=None, title=""):
        """
        Maneja el caso donde IndeedApply es un modal/overlay en la misma ventana.
        """
        try:
            # Buscar iframe de IndeedApply
            iframes = self.driver.find_elements(
                By.CSS_SELECTOR, "iframe[id*='ia-'], iframe[src*='indeed']"
            )
            if iframes:
                self.driver.switch_to.frame(iframes[0])
                result = self._handle_indeed_apply_flow(cv_path, jk=jk, title=title)
                self.driver.switch_to.default_content()
                return result

            # Sin iframe: manejar como overlay en página actual
            return self._handle_indeed_apply_flow(cv_path, jk=jk, title=title)

        except Exception as e:
            print(f"[{self.sitio}] Error en apply inline: {e}")
            try:
                self.driver.switch_to.default_content()
            except Exception:
                pass
            return False

    # ─────────────────────────────────────────────
    # DETECCIÓN DE TIPO DE PASO (ventana IndeedApply)
    # ─────────────────────────────────────────────

    def _detect_indeed_page_type(self):
        """
        Identifica el paso actual del wizard IndeedApply.
        """
        try:
            page_text = (
                self.driver.execute_script(
                    "return document.body ? document.body.innerText.toLowerCase() : '';"
                ) or ""
            )
            url = self.driver.current_url.lower()

            # ── Confirmación ──
            if any(s in page_text for s in [
                "tu solicitud fue enviada",
                "solicitud enviada",
                "application submitted",
                "your application was sent",
                "postulación enviada",
                "se envió tu solicitud",
                "gracias por postularte",
            ]) or "submitted" in url or "confirmation" in url:
                return "confirmation"

            # ── Ya postulado ──
            if any(s in page_text for s in [
                "ya te postulaste",
                "ya aplicaste",
                "already applied",
                "you've already applied",
            ]):
                return "already_applied"

            # ── Error / bloqueo ──
            if any(s in page_text for s in [
                "something went wrong",
                "algo salió mal",
                "inténtalo de nuevo",
                "try again",
            ]):
                return "error"

            # ── CV ──
            if any(s in page_text for s in [
                "curriculum", "currículum", "resume", "cv",
                "subir cv", "upload resume", "adjuntar",
            ]) and self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']"):
                return "cv"

            # ── Datos de contacto ──
            if any(s in page_text for s in [
                "información de contacto", "contact information",
                "nombre", "first name", "last name", "apellido",
                "correo electrónico", "email address", "teléfono", "phone",
            ]) and self.driver.find_elements(
                By.CSS_SELECTOR, "input[type='email'], input[type='tel']"
            ):
                return "contact"

            # ── Preguntas del empleador ──
            if any(s in page_text for s in [
                "preguntas", "questions", "qualifications",
                "¿cuántos años", "how many years", "do you have",
                "experience", "experiencia",
            ]):
                return "questions"

            # ── Revisión / envío ──
            if any(s in page_text for s in [
                "review", "revisar", "enviar solicitud",
                "submit application", "send application",
                "confirmar", "confirm",
            ]):
                return "review"

            if self._find_submit_button():
                return "review"

            if self._has_visible_form_fields():
                return "questions"

            return "unknown"

        except Exception as e:
            print(f"[{self.sitio}] Error detectando tipo de paso: {e}")
            return "unknown"

    def _has_visible_form_fields(self):
        try:
            els = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[type='radio'], select, input[type='text'], "
                "input[type='number'], textarea"
            )
            return any(e.is_displayed() for e in els)
        except Exception:
            return False

    # ─────────────────────────────────────────────
    # MANEJO DE PASOS
    # ─────────────────────────────────────────────

    def _handle_contact_step(self):
        """
        Rellena nombre, apellido y teléfono en la página de contacto de Indeed
        desde config (indeed_filter.contact). No toca email (solo lectura) ni el campo edad (oculto).
        """
        try:
            contact = self.contact or {}
            nombre = (contact.get("nombre") or "").strip()
            apellido = (contact.get("apellido") or "").strip()
            telefono = (contact.get("telefono") or "").strip()

            # Nombre
            if nombre:
                for sel in (
                    "input[name='names-first-name']",
                    "input[data-testid='name-fields-first-name-input']",
                ):
                    try:
                        el = self.driver.find_element(By.CSS_SELECTOR, sel)
                        if el.is_displayed():
                            el.clear()
                            el.send_keys(nombre)
                            get_random_delay(0.2, 0.4)
                            break
                    except Exception:
                        continue

            # Apellido
            if apellido:
                for sel in (
                    "input[name='names-last-name']",
                    "input[data-testid='name-fields-last-name-input']",
                ):
                    try:
                        el = self.driver.find_element(By.CSS_SELECTOR, sel)
                        if el.is_displayed():
                            el.clear()
                            el.send_keys(apellido)
                            get_random_delay(0.2, 0.4)
                            break
                    except Exception:
                        continue

            # Teléfono (input name="phone" dentro del fieldset; país ya suele ser México)
            if telefono:
                try:
                    tel_el = self.driver.find_element(
                        By.CSS_SELECTOR, "input[name='phone']"
                    )
                    if tel_el.is_displayed():
                        tel_el.clear()
                        tel_el.send_keys(telefono)
                        get_random_delay(0.2, 0.4)
                except Exception:
                    pass

            # Email y edad: no tocar (email readonly, edad oculto)
        except Exception as e:
            print(f"[{self.sitio}] Error en paso de contacto: {e}")

    def _handle_cv_step(self, cv_path):
        """Sube el CV o selecciona el CV existente en el perfil."""
        try:
            # Intentar usar CV existente del perfil (botón "Usar este currículum")
            use_existing = self.driver.find_elements(
                By.XPATH,
                "//button[contains(normalize-space(.), 'Usar') "
                "or contains(normalize-space(.), 'Use this') "
                "or contains(normalize-space(.), 'currículum')]"
            )
            for btn in use_existing:
                if btn.is_displayed():
                    self.driver.execute_script("arguments[0].click();", btn)
                    get_random_delay(0.8, 1.5)
                    print(f"[{self.sitio}] CV existente seleccionado.")
                    return

            # Si no hay CV existente, subir archivo
            file_inputs = self.driver.find_elements(
                By.CSS_SELECTOR, "input[type='file']"
            )
            for fi in file_inputs:
                if fi.is_displayed() or True:  # file inputs pueden estar ocultos
                    fi.send_keys(cv_path)
                    get_random_delay(1.5, 2.5)
                    print(f"[{self.sitio}] CV subido: {cv_path}")
                    return

        except Exception as e:
            print(f"[{self.sitio}] Error en paso de CV: {e}")

    def _handle_questions_step(self):
        """
        Responde preguntas del empleador en el wizard de IndeedApply.
        Tipos: select, radio, checkbox, text, number, textarea.
        """
        try:
            # 1) Selects
            for sel_el in self.driver.find_elements(By.CSS_SELECTOR, "select"):
                if not sel_el.is_displayed():
                    continue
                try:
                    sel_obj = Select(sel_el)
                    opts = [o for o in sel_obj.options if o.get_attribute("value")]
                    if len(opts) > 0:
                        sel_obj.select_by_index(1)
                    get_random_delay(0.3, 0.5)
                except Exception:
                    pass

            # 2) Radios
            radio_groups: dict[str, list] = {}
            for radio in self.driver.find_elements(
                By.CSS_SELECTOR, "input[type='radio']"
            ):
                if not radio.is_displayed():
                    continue
                name = radio.get_attribute("name") or radio.get_attribute("id") or "unnamed"
                radio_groups.setdefault(name, []).append(radio)

            prefer_positive = (
                "yes", "sí", "si", "avanzado", "advanced",
                "full time", "tiempo completo", "inmediatamente",
                "immediately", "authorized", "autorizado",
            )
            avoid_negative = ("no ", "never", "nunca", "ninguno")

            for name, radios in radio_groups.items():
                if any(r.is_selected() for r in radios):
                    continue  # ya seleccionado
                chosen = None
                for pref in prefer_positive:
                    for r in radios:
                        label_text = self._get_radio_label(r).lower()
                        if pref in label_text and not any(
                            neg in label_text for neg in avoid_negative
                        ):
                            chosen = r
                            break
                    if chosen:
                        break
                if not chosen:
                    chosen = radios[0]
                try:
                    self.driver.execute_script("arguments[0].click();", chosen)
                    get_random_delay(0.3, 0.5)
                except Exception:
                    pass

            # 3) Inputs de texto / número
            for inp in self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[type='text'], input[type='number'], textarea"
            ):
                if not inp.is_displayed():
                    continue
                if (inp.get_attribute("value") or "").strip():
                    continue
                placeholder = (inp.get_attribute("placeholder") or "").lower()
                label_ctx = self._get_input_label_or_aria(inp).lower()
                inp_type = (inp.get_attribute("type") or "text").lower()
                value = self._infer_input_value(placeholder, label_ctx, inp_type)
                if not value:
                    continue
                try:
                    inp.clear()
                    inp.send_keys(value)
                    get_random_delay(0.3, 0.5)
                except Exception:
                    pass

            # 4) Checkboxes de aceptación
            for cb in self.driver.find_elements(
                By.CSS_SELECTOR, "input[type='checkbox']"
            ):
                if not cb.is_displayed() or cb.is_selected():
                    continue
                label_text = self._get_radio_label(cb).lower()
                if any(k in label_text for k in ("acepto", "aceptar", "agree", "confirm", "entendido")):
                    try:
                        self.driver.execute_script("arguments[0].click();", cb)
                        get_random_delay(0.2, 0.4)
                    except Exception:
                        pass

            print(f"[{self.sitio}] Paso de preguntas completado.")

        except Exception as e:
            print(f"[{self.sitio}] Error en paso de preguntas: {e}")

    def _get_input_label_or_aria(self, inp):
        try:
            inp_id = inp.get_attribute("id")
            if inp_id:
                labels = self.driver.find_elements(
                    By.CSS_SELECTOR, f"label[for='{inp_id}']"
                )
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

    def _infer_input_value(self, placeholder, label_ctx, inp_type):
        ctx = f"{placeholder} {label_ctx}".lower()
        if inp_type == "number":
            return "3"
        if any(k in ctx for k in ("year", "año", "years of", "años de")):
            return "3"
        if any(k in ctx for k in ("salary", "salario", "sueldo", "compensation", "expectativa")):
            return "Según oferta"
        if any(k in ctx for k in ("experiencia", "experience", "descripción", "summary", "cover")):
            return "3 años de experiencia en desarrollo de software."
        if any(k in ctx for k in ("city", "ciudad", "location", "ubicación")):
            return "Puebla"
        return "3 años de experiencia en desarrollo de software."

    def _get_radio_label(self, radio_el):
        try:
            radio_id = radio_el.get_attribute("id")
            if radio_id:
                labels = self.driver.find_elements(
                    By.CSS_SELECTOR, f"label[for='{radio_id}']"
                )
                if labels:
                    return labels[0].text or ""
            parent = radio_el.find_elements(By.XPATH, "./ancestor::label[1]")
            if parent:
                return parent[0].text or ""
        except Exception:
            pass
        return ""

    # ─────────────────────────────────────────────
    # BOTONES DE NAVEGACIÓN
    # ─────────────────────────────────────────────

    def _click_continue_button(self):
        """Click en botón Continuar / Siguiente / Next."""
        xpaths = [
            "//button[contains(normalize-space(.), 'Continuar') and not(@disabled)]",
            "//button[contains(normalize-space(.), 'Continue') and not(@disabled)]",
            "//button[contains(normalize-space(.), 'Siguiente') and not(@disabled)]",
            "//button[contains(normalize-space(.), 'Next') and not(@disabled)]",
            "//button[@type='submit' and not(@disabled) and not(contains(normalize-space(.), 'Enviar'))]",
            "//button[contains(@class,'ia-') and not(@disabled)]",
        ]
        for xp in xpaths:
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
        xpaths = [
            "//button[not(@disabled) and (contains(normalize-space(.), 'Enviar solicitud') or contains(normalize-space(.), 'Submit application'))]",
            "//button[not(@disabled) and (contains(normalize-space(.), 'Enviar') or contains(normalize-space(.), 'Submit'))]",
            "//button[not(@disabled) and (contains(normalize-space(.), 'Confirmar') or contains(normalize-space(.), 'Confirm'))]",
            "//button[@type='submit' and not(@disabled)]",
        ]
        for xp in xpaths:
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

    # ─────────────────────────────────────────────
    # VERIFICACIÓN DE CONFIRMACIÓN
    # ─────────────────────────────────────────────

    def _indeed_application_confirmed(self):
        try:
            page_text = (self.driver.page_source or "").lower()
            url = self.driver.current_url.lower()
            signals = [
                "tu solicitud fue enviada",
                "solicitud enviada",
                "application submitted",
                "your application was sent",
                "postulación enviada",
                "se envió tu solicitud",
                "gracias por postularte",
                "application was sent",
            ]
            return any(s in page_text for s in signals) or (
                "submitted" in url or "confirmation" in url or "success" in url
            )
        except Exception:
            return False

    # ─────────────────────────────────────────────
    # NAVEGACIÓN / RECUPERACIÓN
    # ─────────────────────────────────────────────

    def _go_back_to_search(self):
        print(f"[{self.sitio}] Volviendo al listado...")
        try:
            self.driver.switch_to.window(self.main_window)
        except Exception:
            pass
        self.driver.get(self.search_url)
        get_random_delay(1.5, 2.5)

    # ─────────────────────────────────────────────
    # DEBUG EN CASO DE FALLO
    # ─────────────────────────────────────────────

    def _capture_apply_failure_debug(self, jk=None, title=""):
        try:
            os.makedirs("screenshots", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_jk = re.sub(r"[^0-9A-Za-z_-]+", "_", str(jk or "unknown"))
            safe_title = re.sub(
                r"[^0-9A-Za-z_-]+", "_", (title or "sin_titulo")
            ).strip("_")[:50]

            page_path = take_screenshot(
                self.driver, f"indeed_fail_{safe_jk}_{timestamp}"
            )
            log_path = os.path.join("screenshots", "indeed_apply_failures.log")

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(
                    f"{datetime.now().isoformat()} | "
                    f"jk={jk or 'unknown'} | "
                    f"title={safe_title} | "
                    f"url={self.driver.current_url} | "
                    f"search={self.search_url} | "
                    f"page_shot={page_path}\n"
                )

            print(f"[{self.sitio}] Debug guardado (jk={jk}, page={page_path})")
        except Exception as e:
            print(f"[{self.sitio}] No se pudo guardar debug: {e}")