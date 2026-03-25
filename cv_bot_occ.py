from utils import get_random_delay, take_screenshot, log_postulacion
import re
import os
import unicodedata
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException
)


# ─────────────────────────────────────────────────────────────
#  ESTRUCTURA REAL DE OCC (HTML inspeccionado 2026-03)
#
#  Cada card en el panel izquierdo es:
#    <div data-offers-grid-offer-item-container
#         data-id="21003063"
#         id="jobcard-21003063"
#         class="... cursor-pointer ...">
#      <div data-recent-container>
#        <h2>Título</h2>
#        <span>Sueldo</span>
#        <span class="line-clamp-title"><a>Empresa</a></span>
#        <p>Ciudad</p>
#        <div data-recent-apply class="hidden">Ya estás postulado.</div>
#      </div>
#    </div>
#
#  El click handler está en el div raíz con data-offers-grid-offer-item-container.
#  NO hay <a> apuntando a la vacante — OCC carga el detalle en el
#  panel derecho via JS (Handlebars template #templateDetailOffer).
#
#  El botón de postular en el panel derecho tiene el atributo [apply-btn].
# ─────────────────────────────────────────────────────────────

CARD_SEL = "[data-offers-grid-offer-item-container]"


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def spanish_relative_days_ago(text: str) -> int | None:
    """
    Interpreta textos típicos de antigüedad en español (listados OCC / MX):
    'hace 1 semana', 'hace 3 días', 'ayer', 'hoy', 'hace 2 meses', etc.
    Devuelve días aproximados desde la publicación, o None si no hay patrón claro.
    """
    if not text or not str(text).strip():
        return None
    t = _strip_accents(str(text).lower())

    m = re.search(r"hace\s+(\d+)\s+mes(?:es)?\b", t)
    if m:
        return int(m.group(1)) * 30
    if re.search(r"hace\s+(?:un|una|1)\s+mes\b", t):
        return 30

    m = re.search(r"hace\s+(\d+)\s+semanas?\b", t)
    if m:
        return int(m.group(1)) * 7
    if re.search(r"hace\s+(?:una|1)\s+semana\b", t):
        return 7

    m = re.search(r"hace\s+(\d+)\s+dias?\b", t)
    if m:
        return int(m.group(1))
    if re.search(r"hace\s+(?:un|1)\s+dia\b", t):
        return 1

    if re.search(r"hace\s+(\d+)\s+horas?\b", t):
        return 0
    if re.search(r"hace\s+pocos?\s+minutos?\b", t):
        return 0
    if re.search(r"\b(hoy|publicad[oa]\s+hoy)\b", t):
        return 0
    if re.search(r"\bayer\b", t):
        return 1

    return None


class BotOCC:
    def __init__(
        self,
        driver,
        dry_run: bool = False,
        controlled_mode: bool = False,
        max_scan_per_keyword: int = 6,
        filter_config: dict | None = None,
        postulaciones_csv: str | None = None,
        modal_config: dict | None = None,
    ):
        self.driver = driver
        self.dry_run = dry_run
        self.sitio = "OCC"
        self.controlled_mode = controlled_mode
        self.max_scan_per_keyword = max(1, int(max_scan_per_keyword))
        self.search_url = ""
        self.postulaciones_csv = (postulaciones_csv or "").strip() or None

        # Configuración de filtrado inyectada desde config.yaml.
        # Si no viene nada, se usan defaults razonables.
        fc = filter_config or {}
        self.filter_exclude_terms = [
            t.lower() for t in fc.get("exclude_terms", [
                # Java / Spring por defecto
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
        # Ordenar por fecha (Relevancia vs Fecha) y filtrar por rango de antigüedad [min_days_old, max_days_old].
        self.sort_by_date = fc.get("sort_by_date", True)
        self.min_days_old = max(0, int(fc.get("min_days_old", 0)))
        self.max_days_old = max(1, int(fc.get("max_days_old", 30)))
        if self.min_days_old > self.max_days_old:
            self.min_days_old = self.max_days_old
        # Si true y no se puede deducir la antigüedad ni en la card ni en el panel, no postular
        self.reject_unknown_posting_age = bool(fc.get("reject_unknown_posting_age", False))
        # Cuando ordenamos por fecha: solo procesar esta cantidad de páginas (1 = solo primera, ofertas más recientes)
        self.max_pages_when_sorted_by_date = max(1, int(fc.get("max_pages_when_sorted_by_date", 1)))
        # Si la lista no está vacía, el título debe contener al menos uno de estos términos (todo en minúsculas al comparar)
        self.include_title_must_contain_any = [
            str(t).lower().strip() for t in fc.get("include_title_must_contain_any", []) if str(t).strip()
        ]

        om = modal_config or {}
        self.modal_max_attempts = max(1, int(om.get("max_attempts", 4)))
        _pr = om.get("preferred_skill_ratings") or ["3", "2", "4", "1"]
        self.modal_preferred_ratings = [str(x) for x in _pr]

    # ─────────────────────────────────────────────
    # ENTRY POINT
    # ─────────────────────────────────────────────

    def search_and_apply(self, keyword, cv_path, max_apps):
        apps_done = 0
        self.search_url = f"https://www.occ.com.mx/empleos/de-{keyword.replace(' ', '-')}/"
        keyword_low = (keyword or "").lower()

        try:
            print(f"[{self.sitio}] Buscando: {keyword}")
            self.driver.get(self.search_url)
            get_random_delay(2.0, 3.0)

            if self.sort_by_date:
                self._apply_sort_by_date()

            if self.dry_run:
                print(f"[{self.sitio}] [DRY-RUN] Simulando búsqueda...")
                return min(2, max_apps)

            max_scan = self.max_scan_per_keyword if self.controlled_mode else max(25, max_apps * 8)

            # Recorremos todas las páginas de resultados mientras:
            # - haya más páginas
            # - no se alcance el límite de postulaciones
            page = 1
            visited_paths = set()

            while apps_done < max_apps:
                print(f"[{self.sitio}] Página {page}")

                # 1. Cargar cards haciendo scroll (lazy load) en la página actual
                self._scroll_to_load(target=max_scan)

                # 2. Leer todos los data-id de las cards presentes
                job_ids = self._collect_job_ids(limit=max_scan)
                print(f"[{self.sitio}] Cards encontradas en página {page}: {len(job_ids)}")

                for idx, job_id in enumerate(job_ids):
                    if apps_done >= max_apps:
                        print(f"[{self.sitio}] Límite alcanzado.")
                        break

                    try:
                        # Leer metadata sin abrir la vacante
                        meta = self._read_card_meta(job_id)
                        title   = meta.get("title") or "Sin título"
                        company = meta.get("company") or ""

                        if not self._is_relevant(title, keyword_low):
                            print(f"[{self.sitio}] [{page}-{idx+1}] Saltada: {title}")
                            continue

                        if meta.get("already_applied"):
                            print(f"[{self.sitio}] [{page}-{idx+1}] Ya postulado: {title}")
                            continue

                        days_ago = spanish_relative_days_ago(meta.get("card_text") or "")
                        if days_ago is not None and (
                            days_ago < self.min_days_old or days_ago > self.max_days_old
                        ):
                            print(
                                f"[{self.sitio}] [{page}-{idx+1}] Omitida "
                                f"(antigüedad ~{days_ago} días fuera de rango "
                                f"{self.min_days_old}-{self.max_days_old}): {title}"
                            )
                            continue

                        print(f"[{self.sitio}] [{page}-{idx+1}/{len(job_ids)}] {title} — {company}")

                        # Clickear la card para abrir el panel derecho
                        if not self._click_card(job_id, title):
                            print(f"[{self.sitio}] No se pudo abrir la vacante.")
                            continue

                        # Refinar antigüedad con el texto del panel (a veces solo ahí aparece "hace X días/semanas")
                        d_panel = self._days_ago_from_detail_panel()
                        if d_panel is not None:
                            days_ago = d_panel
                        if days_ago is not None and (
                            days_ago < self.min_days_old or days_ago > self.max_days_old
                        ):
                            print(
                                f"[{self.sitio}] [{page}-{idx+1}] Omitida en panel "
                                f"(antigüedad ~{days_ago} días fuera de rango "
                                f"{self.min_days_old}-{self.max_days_old}): {title}"
                            )
                            continue
                        if days_ago is None and self.reject_unknown_posting_age:
                            print(
                                f"[{self.sitio}] [{page}-{idx+1}] Omitida (sin fecha legible; "
                                f"reject_unknown_posting_age=true): {title}"
                            )
                            continue

                        # Revisar título del panel (puede ser más completo que en la card)
                        panel_title = self._get_panel_title()
                        if panel_title and not self._is_relevant(panel_title, keyword_low):
                            print(f"[{self.sitio}] Saltada (panel): {panel_title}")
                            continue

                        if self.apply_to_job(
                            cv_path, job_id=job_id, title=title, company=company
                        ):
                            apps_done += 1

                    except Exception as e:
                        take_screenshot(self.driver, f"occ_error_{page}_{idx}")
                        print(f"[{self.sitio}] Error en vacante {page}-{idx}: {e}")
                        if not self._on_search_page():
                            self._go_back_to_search()

                if apps_done >= max_apps:
                    break

                # Con orden por fecha: no pasar de N páginas (solo recientes, ~1 mes)
                if self.sort_by_date and page >= self.max_pages_when_sorted_by_date:
                    print(f"[{self.sitio}] Límite de páginas con orden por fecha ({self.max_pages_when_sorted_by_date}), solo ofertas recientes.")
                    break

                # 3. Intentar ir a la siguiente página
                next_path = self._get_next_page_path()
                if not next_path:
                    print(f"[{self.sitio}] No hay más páginas para '{keyword}'.")
                    break

                if next_path in visited_paths:
                    print(f"[{self.sitio}] Página repetida detectada ({next_path}), deteniendo para evitar bucles.")
                    break

                visited_paths.add(next_path)
                next_url = f"https://www.occ.com.mx{next_path}"
                print(f"[{self.sitio}] Navegando a siguiente página: {next_url}")
                self.driver.get(next_url)
                get_random_delay(2.0, 3.0)
                page += 1

        except Exception as e:
            take_screenshot(self.driver, "occ_main_error")
            print(f"[{self.sitio}] Error principal: {e}")

        print(f"[{self.sitio}] Postulaciones '{keyword}': {apps_done}")
        return apps_done

    # ─────────────────────────────────────────────
    # SCROLL PARA CARGAR CARDS (lazy load)
    # ─────────────────────────────────────────────

    def _scroll_to_load(self, target=25):
        """
        Scroll progresivo hacia abajo para disparar el lazy load de OCC.
        Solo hace scroll — no intenta clickear nada aquí.
        Al terminar vuelve al tope para que las cards sean clickeables.
        """
        prev_count = 0
        stable = 0

        for attempt in range(20):
            count = self._count_cards()
            print(f"[{self.sitio}] Scroll {attempt+1}: {count}/{target} cards")

            if count >= target:
                break

            if count == prev_count:
                stable += 1
                if stable >= 3:
                    print(f"[{self.sitio}] Sin más cards disponibles.")
                    break
            else:
                stable = 0

            prev_count = count
            self.driver.execute_script("window.scrollBy(0, window.innerHeight * 0.75);")
            get_random_delay(1.2, 2.0)

        # Volver al tope — imprescindible para que las cards sean visibles al hacer click
        self.driver.execute_script("window.scrollTo(0, 0);")
        get_random_delay(0.8, 1.2)

    def _count_cards(self):
        try:
            return len(self.driver.find_elements(By.CSS_SELECTOR, CARD_SEL))
        except:
            return 0

    # ─────────────────────────────────────────────
    # PAGINACIÓN
    # ─────────────────────────────────────────────

    def _get_next_page_path(self):
        """
        Devuelve el valor de data-path del botón 'siguiente' (#btn-next-offer)
        o None si ya no hay más páginas.

        Basado en el HTML real:
          <li id="btn-next-offer" ... data-path="/empleos/de-Ingeniero-de-software-remoto/?page=2">
        Cuando está deshabilitado lleva clases como 'pointer-events-none opacity-40'.
        """
        try:
            script = """
                const li = document.querySelector('#btn-next-offer');
                if (!li) return '';

                const style = window.getComputedStyle(li);
                const disabledByClass = li.classList.contains('pointer-events-none') ||
                                        li.classList.contains('opacity-40');
                const disabledByStyle = style.pointerEvents === 'none' ||
                                        parseFloat(style.opacity || '1') < 0.5;

                if (disabledByClass || disabledByStyle) return '';

                const path = li.getAttribute('data-path') || '';
                return path;
            """
            path = self.driver.execute_script(script)
            if not path:
                return None
            return str(path)
        except Exception as e:
            print(f"[{self.sitio}] Error leyendo paginación: {e}")
            return None

    # ─────────────────────────────────────────────
    # ORDENAR POR FECHA (dropdown #sort-jobs → Fecha / sort=2)
    # ─────────────────────────────────────────────

    def _apply_sort_by_date(self):
        """
        Abre el dropdown 'Ordenar por' (#results-top-filter) y elige 'Fecha'
        (opción con data-path que contiene sort=2) para ver vacantes más recientes primero.
        """
        try:
            trigger = self.driver.find_element(By.CSS_SELECTOR, "#results-top-filter")
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", trigger)
            get_random_delay(0.3, 0.6)
            trigger.click()
            get_random_delay(0.5, 1.0)
            # Opción Fecha: data-path con ?sort=2 (Relevancia es sort=1)
            option = self.driver.find_element(
                By.CSS_SELECTOR,
                "#sort-jobs [data-path*='sort=2']"
            )
            option.click()
            get_random_delay(1.5, 2.5)
            print(f"[{self.sitio}] Orden aplicado: Fecha (más recientes primero)")
        except NoSuchElementException:
            print(f"[{self.sitio}] No se encontró el ordenador por fecha; se usa orden por defecto.")
        except Exception as e:
            print(f"[{self.sitio}] Error al aplicar orden por fecha: {e}")

    # ─────────────────────────────────────────────
    # RECOLECCIÓN DE IDs
    # ─────────────────────────────────────────────

    def _collect_job_ids(self, limit=50):
        """
        Lee el atributo data-id de cada div[data-offers-grid-offer-item-container].
        Devuelve lista de strings en orden de aparición.
        """
        try:
            ids = self.driver.execute_script("""
                const cards = document.querySelectorAll(arguments[0]);
                const ids = [];
                cards.forEach(c => {
                    const id = c.getAttribute('data-id');
                    if (id) ids.push(id);
                });
                return ids.slice(0, arguments[1]);
            """, CARD_SEL, limit)
            return ids or []
        except Exception as e:
            print(f"[{self.sitio}] Error recolectando IDs: {e}")
            return []

    # ─────────────────────────────────────────────
    # LECTURA DE METADATA (sin abrir la vacante)
    # ─────────────────────────────────────────────

    def _read_card_meta(self, job_id):
        """
        Lee título, empresa, ciudad y estado de la card desde el DOM.
        Usa id="jobcard-{job_id}" — selector único y estable.
        """
        try:
            meta = self.driver.execute_script("""
                const card = document.getElementById('jobcard-' + arguments[0]);
                if (!card) return {};

                const h2 = card.querySelector('h2');
                const title = h2 ? h2.innerText.trim() : '';

                const companyEl = card.querySelector('.line-clamp-title a');
                const company = companyEl ? companyEl.innerText.trim() : '';

                const locEl = card.querySelector('.no-alter-loc-text p');
                const location = locEl ? locEl.innerText.trim() : '';

                // [data-recent-apply] sin clase 'hidden' = ya postulado
                const applyDiv = card.querySelector('[data-recent-apply]');
                const alreadyApplied = applyDiv
                    ? !applyDiv.classList.contains('hidden')
                    : false;

                // Texto completo de la card: la antigüedad se parsea en Python
                // ("hace 1 semana", "hace 3 días", "ayer", etc.)
                const card_text = card.innerText || '';

                return { title, company, location, already_applied: alreadyApplied, card_text };
            """, job_id)
            return meta or {}
        except Exception as e:
            print(f"[{self.sitio}] Error leyendo meta card {job_id}: {e}")
            return {}

    def _days_ago_from_detail_panel(self) -> int | None:
        """
        Tras abrir la vacante, el panel derecho suele incluir 'hace X días/semanas'.
        Se toma texto alrededor de [apply-btn] para no mezclar con el listado izquierdo.
        """
        try:
            text = self.driver.execute_script("""
                const btn = document.querySelector('[apply-btn]');
                if (!btn) return '';
                let n = btn;
                for (let i = 0; i < 10 && n; i++) {
                    const t = (n.innerText || '');
                    if (t.length > 100) return t.slice(0, 14000);
                    n = n.parentElement;
                }
                return (btn.innerText || '').slice(0, 4000);
            """)
            return spanish_relative_days_ago(text or "")
        except Exception:
            return None

    # ─────────────────────────────────────────────
    # CLICK EN CARD — NÚCLEO DEL FIX
    # ─────────────────────────────────────────────

    def _click_card(self, job_id, expected_title=""):
        """
        Hace click en el div raíz #jobcard-{job_id}.
        Ese div tiene el handler de OCC que carga el detalle en el panel derecho.

        Intento 1: scroll to view + JS click
        Intento 2: ActionChains (simula click de mouse real)
        Intento 3: verifica si igual apareció el botón [apply-btn]
        """
        card_css = f"#jobcard-{job_id}"

        # ── Intento 1: JS click ──
        try:
            card = self.driver.find_element(By.CSS_SELECTOR, card_css)
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});",
                card
            )
            get_random_delay(0.5, 0.9)
            self.driver.execute_script("arguments[0].click();", card)
            get_random_delay(1.5, 2.5)

            if self._panel_has_content(expected_title):
                print(f"[{self.sitio}] Card #{job_id} abierta (JS click) OK")
                return True
        except StaleElementReferenceException:
            print(f"[{self.sitio}] StaleElement en JS click, reintentando...")
        except Exception as e:
            print(f"[{self.sitio}] JS click error: {e}")

        # ── Intento 2: ActionChains ──
        try:
            card = self.driver.find_element(By.CSS_SELECTOR, card_css)
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", card
            )
            get_random_delay(0.4, 0.7)
            ActionChains(self.driver).move_to_element(card).pause(0.3).click().perform()
            get_random_delay(1.5, 2.5)

            if self._panel_has_content(expected_title):
                print(f"[{self.sitio}] Card #{job_id} abierta (ActionChains) OK")
                return True
        except Exception as e:
            print(f"[{self.sitio}] ActionChains error: {e}")

        # ── Intento 3: verificar si el panel tiene botón igual ──
        if self._has_apply_button():
            print(f"[{self.sitio}] Card #{job_id} boton [apply-btn] detectado OK")
            return True

        print(f"[{self.sitio}] Falló apertura de card #{job_id}")
        return False

    # ─────────────────────────────────────────────
    # VERIFICACIÓN DE PANEL DERECHO
    # ─────────────────────────────────────────────

    def _panel_has_content(self, expected_title=""):
        """
        Verifica que el panel derecho de OCC tiene contenido de vacante.
        OCC inyecta el detalle via Handlebars en la mitad derecha del layout.
        El botón de postular tiene el atributo [apply-btn].
        """
        try:
            result = self.driver.execute_script("""
                // 1. Botón apply-btn (inyectado por OCC via Handlebars)
                const applyBtn = document.querySelector('[apply-btn]');
                if (applyBtn && applyBtn.offsetParent !== null) {
                    return { found: true, text: '' };
                }

                // 2. Título en el panel derecho (x > 42% del viewport)
                const minX = window.innerWidth * 0.42;
                const heads = Array.from(document.querySelectorAll(
                    '[data-offers-grid-detail-title], h1, h2'
                ));
                for (const h of heads) {
                    const r = h.getBoundingClientRect();
                    if (r.left >= minX && r.width > 60 && r.height > 10) {
                        const txt = (h.innerText || '').trim();
                        if (txt.length > 4) return { found: true, text: txt };
                    }
                }

                return { found: false, text: '' };
            """)

            if not result or not result.get("found"):
                return False

            if expected_title:
                panel_text = (result.get("text") or "").lower()
                short = expected_title[:35].strip().lower()
                if short and panel_text and short not in panel_text:
                    # Título no coincide exactamente pero hay contenido — aceptar igual
                    return bool(panel_text)

            return True

        except Exception as e:
            print(f"[{self.sitio}] Error verificando panel: {e}")
            return False

    def _has_apply_button(self):
        try:
            btn = self.driver.find_element(By.CSS_SELECTOR, "[apply-btn]")
            return btn.is_displayed()
        except:
            pass
        try:
            btns = self.driver.find_elements(
                By.XPATH,
                "//*[self::button or self::a][contains(normalize-space(.), 'Postularme')]"
            )
            return any(b.is_displayed() for b in btns)
        except:
            return False

    def _get_panel_title(self):
        """Devuelve el título de la vacante en el panel derecho (puede ser más completo que en la card)."""
        try:
            result = self.driver.execute_script("""
                const minX = window.innerWidth * 0.42;
                const heads = Array.from(document.querySelectorAll(
                    '[data-offers-grid-detail-title], h1, h2'
                ));
                for (const h of heads) {
                    const r = h.getBoundingClientRect();
                    if (r.left >= minX && r.width > 60 && r.height > 10) {
                        const txt = (h.innerText || '').trim();
                        if (txt.length > 4) return txt;
                    }
                }
                return '';
            """)
            return (result or "").strip() or None
        except Exception:
            return None

    # ─────────────────────────────────────────────
    # NAVEGACIÓN
    # ─────────────────────────────────────────────

    def _on_search_page(self):
        try:
            return len(self.driver.find_elements(By.CSS_SELECTOR, CARD_SEL)) > 0
        except:
            return False

    def _go_back_to_search(self):
        print(f"[{self.sitio}] Volviendo al listado...")
        self.driver.get(self.search_url)
        get_random_delay(1.5, 2.5)
        self._scroll_to_load(target=10)

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

        # 1) Exclusiones configurables (términos y regex)
        # Términos: coincidencia por palabra completa (evita que "java" excluya "javascript")
        for term in self.filter_exclude_terms:
            t = (term or "").strip().lower()
            if not t:
                continue
            try:
                if re.search(r"\b" + re.escape(t) + r"\b", title_low):
                    return False
            except re.error:
                if t in title_low:
                    return False

        for pattern in self.filter_exclude_regex:
            try:
                if re.search(pattern, title_low):
                    return False
            except re.error:
                continue

        # 2) Inclusión por términos técnicos (stack objetivo)
        if any(t in title_low for t in self.filter_tech_terms):
            return True

        # 3) Fallback: tokens útiles de la keyword
        tokens = [
            t.strip()
            for t in keyword_low.replace("/", " ").replace("-", " ").split()
            if t.strip() and t.strip().lower() not in self.filter_keyword_ignore
        ]
        return any(tok in title_low for tok in tokens)

    # ─────────────────────────────────────────────
    # POSTULACIÓN
    # ─────────────────────────────────────────────

    def apply_to_job(self, cv_path, job_id=None, title="", company=""):
        # Esperar botón [apply-btn] — atributo real de OCC
        try:
            apply_btn = WebDriverWait(self.driver, 12).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "[apply-btn]"))
            )
        except TimeoutException:
            # Fallback por texto
            try:
                apply_btn = WebDriverWait(self.driver, 6).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        "//*[self::button or self::a]"
                        "[contains(normalize-space(.), 'Postularme') and not(@disabled)]"
                    ))
                )
            except TimeoutException:
                print(f"[{self.sitio}] Timeout: sin botón Postularme.")
                return False

        btn_text = (apply_btn.text or "").lower()
        if "ya te postulaste" in btn_text or "postulado" in btn_text:
            print(f"[{self.sitio}] Ya postulado.")
            return False

        self.driver.execute_script("arguments[0].click();", apply_btn)
        get_random_delay(0.8, 1.5)

        if not self._handle_knowledge_modal(job_id=job_id, title=title):
            print(f"[{self.sitio}] Modal de conocimientos falló.")
            return False

        # CV upload (opcional según configuración de la vacante)
        try:
            cv_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='file']")
            cv_input.send_keys(cv_path)
            get_random_delay(0.5, 1.0)
        except NoSuchElementException:
            pass

        submit = self._find_submit()
        if not submit:
            print(f"[{self.sitio}] Sin botón de envío final.")
            return False

        self.driver.execute_script("arguments[0].click();", submit)
        get_random_delay(1.5, 3.0)
        print(f"[{self.sitio}] Postulacion enviada.")
        if self.postulaciones_csv and not self.dry_run:
            log_postulacion(
                self.postulaciones_csv,
                self.sitio,
                title or "Sin título",
                company or "",
                "Postulado",
            )
        return True

    def _find_submit(self):
        xpaths = [
            "//button[not(@disabled) and @type='submit']",
            "//button[not(@disabled) and contains(., 'Postular')]",
            "//button[not(@disabled) and contains(., 'Enviar')]",
            "//*[self::button or self::a][contains(., 'Postularme') and not(@disabled)]",
        ]
        for xp in xpaths:
            try:
                return self.driver.find_element(By.XPATH, xp)
            except:
                continue
        return None

    # ─────────────────────────────────────────────
    # MODAL DE CONOCIMIENTOS
    # ─────────────────────────────────────────────

    def _job_marked_as_applied(self, job_id):
        """
        Usa la metadata de la card en el panel izquierdo para saber si
        OCC ya marcó la vacante como postulada ([data-recent-apply] visible).
        """
        try:
            meta = self._read_card_meta(job_id)
            return bool(meta.get("already_applied"))
        except Exception as e:
            print(f"[{self.sitio}] Error verificando estado de postulación para job_id={job_id}: {e}")
            return False

    def _handle_knowledge_modal(self, job_id=None, title=""):
        try:
            # Verificar si el modal realmente aparece
            modal_label = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((
                    By.XPATH,
                    "//*[contains("
                    "translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚ', 'abcdefghijklmnopqrstuvwxyzáéíóú'), "
                    "'nivel de conocimientos')]"
                ))
            )
        except TimeoutException:
            return True  # Sin modal, no bloquea el flujo

        print(f"[{self.sitio}] Modal de conocimientos detectado. Resolviendo...")

        max_attempts = self.modal_max_attempts
        for attempt in range(1, max_attempts + 1):
            modal = self._current_modal_container(modal_label)
            try:
                # Asegurar que el modal esté en vista
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", modal
                )
                get_random_delay(0.3, 0.6)
            except Exception:
                pass

            # 1. Llenar formulario de niveles (con esperas para que React estabilice)
            self._fill_knowledge_form(modal)
            get_random_delay(1.5, 2.5)  # Dar tiempo a que React habilite el botón

            # Si el botón sigue deshabilitado, intentar re-llenar una vez más
            if not self._modal_postular_enabled(modal):
                get_random_delay(0.8, 1.2)
                self._fill_knowledge_form(modal)
                get_random_delay(1.2, 2.0)

            # 2. Verificar si el botón "Postularme" se habilitó y hacer click
            if self._modal_postular_enabled(modal):
                try:
                    postular = None
                    for by, selector in [
                        (By.CSS_SELECTOR, "[skills-apply]"),
                        (By.XPATH, ".//*[self::button or self::a][contains(normalize-space(.), 'Postularme')]"),
                    ]:
                        els = modal.find_elements(by, selector)
                        for el in els:
                            if el.is_displayed():
                                postular = el
                                break
                        if postular:
                            break
                    if not postular:
                        raise NoSuchElementException("Postularme no encontrado")
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", postular)
                    get_random_delay(0.2, 0.4)
                    self.driver.execute_script("arguments[0].click();", postular)

                    # 3. Esperar explícitamente a que el modal desaparezca del DOM (más fiable que un delay fijo)
                    try:
                        WebDriverWait(self.driver, 12).until(EC.staleness_of(modal))
                        print(f"[{self.sitio}] Modal completado y cerrado exitosamente (Intento {attempt}).")
                        return True
                    except TimeoutException:
                        # Si el modal no se destruye pero ya marca la vacante como postulada en la lista,
                        # lo consideramos éxito lógico aunque visualmente quede algo abierto.
                        if job_id is not None and self._job_marked_as_applied(job_id):
                            print(f"[{self.sitio}] Modal no desapareció pero la vacante ya figura como postulada.")
                            return True

                    # 4. Si no se cerró, intentar cerrar por fallback para poder reintentar
                    if self._modal_try_close_fallback(modal_label):
                        print(f"[{self.sitio}] Modal cerrado por fallback, reintentando...")
                        get_random_delay(1.0, 1.5)

                    try:
                        if modal.is_displayed():
                            print(f"[{self.sitio}] Modal sigue visible, reintentando...")
                    except StaleElementReferenceException:
                        return True
                    continue

                except Exception as e:
                    print(f"[{self.sitio}] Error al hacer click en Postularme dentro del modal: {e}")

            print(f"[{self.sitio}] Botón inactivo o modal no cerró. Reintentando ({attempt}/{max_attempts})...")
            get_random_delay(0.8, 1.5)

        self._capture_modal_failure_debug(
            modal=modal,
            job_id=job_id,
            title=title,
            reason=f"No se logró completar/cerrar el modal tras {max_attempts} intentos."
        )
        print(f"[{self.sitio}] No se logró completar/cerrar el modal tras {max_attempts} intentos.")
        return False

    def _capture_modal_failure_debug(self, modal, job_id=None, title="", reason=""):
        """
        Guarda evidencia cuando la modal falla:
        - screenshot del modal (si existe)
        - screenshot de página completa
        - log con job_id y contexto
        """
        try:
            os.makedirs("screenshots", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_job = re.sub(r"[^0-9A-Za-z_-]+", "_", str(job_id or "unknown"))
            safe_title = re.sub(r"[^0-9A-Za-z_-]+", "_", (title or "sin_titulo")).strip("_")[:50]

            modal_path = os.path.join("screenshots", f"occ_modal_fail_job{safe_job}_{timestamp}.png")
            page_path = take_screenshot(self.driver, f"occ_page_fail_job{safe_job}")
            log_path = os.path.join("screenshots", "occ_modal_failures.log")

            modal_saved = False
            try:
                if modal and modal.is_displayed():
                    modal.screenshot(modal_path)
                    modal_saved = True
            except Exception:
                modal_saved = False

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(
                    f"{datetime.now().isoformat()} | "
                    f"job_id={job_id or 'unknown'} | "
                    f"title={safe_title or 'sin_titulo'} | "
                    f"reason={reason or 'sin_detalle'} | "
                    f"search_url={self.search_url} | "
                    f"modal_shot={modal_path if modal_saved else 'no_disponible'} | "
                    f"page_shot={page_path}\n"
                )

            print(
                f"[{self.sitio}] Debug modal guardado "
                f"(job_id={job_id or 'unknown'}, modal={'OK' if modal_saved else 'N/A'}, page={page_path})"
            )
        except Exception as e:
            print(f"[{self.sitio}] No se pudo guardar debug de modal: {e}")

    def _current_modal_container(self, modal_label):
        try:
            # Preferir el modal de habilidades OCC: data-modal="content_modal" o class modal_skills
            for sel in [
                "//*[@data-modal='content_modal']",
                "//*[contains(@class, 'modal_skills')]",
                "//*[@role='dialog' or contains(@class, 'modal')]",
            ]:
                dialogs = self.driver.find_elements(By.XPATH, sel)
                for dialog in dialogs:
                    if dialog.is_displayed():
                        return dialog
            # Fallback al contenedor más cercano si no hay estructura dialog clara
            return modal_label.find_element(By.XPATH, "./ancestor::*[self::div or self::section][1]")
        except Exception:
            return self.driver

    def _modal_try_close_fallback(self, modal_label):
        """Intenta cerrar el modal con X, Cerrar o click en overlay si no se cerró solo."""
        try:
            # Botones de cierre específicos del modal de habilidades OCC
            for css in ["[data-modal='close_modal_btn']", "[modal-skills-close-btn]"]:
                btns = self.driver.find_elements(By.CSS_SELECTOR, css)
                for b in btns:
                    if b.is_displayed():
                        self.driver.execute_script("arguments[0].click();", b)
                        get_random_delay(1.0, 1.8)
                        return True
            # Buscar botón Cerrar / X / cerrar en el documento (por si el contenedor ya está stale)
            for xpath in [
                "//*[@role='dialog' or contains(@class, 'modal')]//*[contains(translate(., 'CERRAR', 'cerrar'), 'cerrar') or .//*[local-name()='svg']]",
                "//button[contains(translate(., 'CERRAR', 'cerrar'), 'cerrar')]",
                "//*[@aria-label and contains(translate(@aria-label, 'CERRAR', 'cerrar'), 'cerrar')]",
                "//*[contains(@class, 'close') or contains(@class, 'cerrar')]",
            ]:
                btns = self.driver.find_elements(By.XPATH, xpath)
                for b in btns:
                    if b.is_displayed():
                        self.driver.execute_script("arguments[0].click();", b)
                        get_random_delay(1.0, 1.8)
                        return True
            # Click en overlay (fuera del contenido del modal)
            dialogs = self.driver.find_elements(By.XPATH, "//*[@role='dialog']")
            for d in dialogs:
                if d.is_displayed():
                    self.driver.execute_script(
                        "var e = arguments[0]; var r = e.getBoundingClientRect(); "
                        "var x = r.left - 10; var y = r.top - 10; "
                        "e.dispatchEvent(new MouseEvent('click', {view: window, bubbles: true, clientX: x, clientY: y}));",
                        d
                    )
                    get_random_delay(1.0, 1.5)
                    return True
        except Exception as e:
            print(f"[{self.sitio}] Fallback cerrar modal: {e}")
        return False

    def _fill_knowledge_form(self, modal):
        # 1) Intentar llenar por [skill-rating] / data-rating (modal OCC actual)
        try:
            WebDriverWait(self.driver, 6).until(
                lambda d: len(modal.find_elements(By.CSS_SELECTOR, "[skill-rating], button[data-rating]")) > 0
            )
            get_random_delay(0.4, 0.7)
        except TimeoutException:
            pass

        rating_btns = modal.find_elements(By.CSS_SELECTOR, "[skill-rating], button[data-rating]")
        if rating_btns:
            # Agrupar por data-id (cada habilidad: inglés, portugués, etc.)
            by_id = {}
            for btn in rating_btns:
                if not btn.is_displayed():
                    continue
                sid = btn.get_attribute("data-id") or "default"
                by_id.setdefault(sid, []).append(btn)
            # Por cada habilidad, elegir nivel: data-rating 3 = Avanzado (o 2 = Medio si no hay 3)
            preferred_ratings = list(self.modal_preferred_ratings) or ["3", "2", "4", "1"]
            for sid, btns in by_id.items():
                # Ordenar por data-rating para elegir el preferido
                by_rating = {}
                for b in btns:
                    r = b.get_attribute("data-rating")
                    if r is not None:
                        by_rating[r] = b
                clicked = False
                for r in preferred_ratings:
                    if r not in by_rating:
                        continue
                    el = by_rating[r]
                    try:
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", el
                        )
                        get_random_delay(0.2, 0.4)
                        self.driver.execute_script("arguments[0].click();", el)
                        get_random_delay(0.4, 0.7)
                        clicked = True
                        print(f"[{self.sitio}] Modal skill id={sid} -> nivel {r}")
                        break
                    except Exception:
                        pass
                if not clicked and by_rating:
                    # Cualquier nivel no cero
                    for r in ["1", "2", "3", "4"]:
                        if r in by_rating:
                            try:
                                self.driver.execute_script("arguments[0].click();", by_rating[r])
                                get_random_delay(0.4, 0.6)
                                break
                            except Exception:
                                pass
            get_random_delay(0.5, 1.0)
            return
        # 2) Fallback: llenar por texto (Avanzado, Medio, Básico, etc.)
        default_levels = ["Avanzado", "Medio", "Básico", "Basico", "Ninguno"]
        english_levels = ["Medio", "Avanzado", "Básico", "Basico", "Ninguno"]
        try:
            xpath_options = ".//*[self::button or self::label or @role='button'][" + \
                " or ".join([f"contains(normalize-space(.), '{l}')" for l in ["Avanzado", "Medio", "Básico", "Basico", "Ninguno", "Experto"]]) + "]"
            try:
                WebDriverWait(self.driver, 4).until(
                    lambda d: len(modal.find_elements(By.XPATH, xpath_options)) > 0
                )
            except TimeoutException:
                pass
            get_random_delay(0.3, 0.6)
            all_options = modal.find_elements(By.XPATH, xpath_options)
            rows = []
            for opt in all_options:
                if not opt.is_displayed():
                    continue
                loc_y = opt.location["y"]
                found_row = False
                for row in rows:
                    if abs(row["y"] - loc_y) < 25:
                        row["elements"].append(opt)
                        found_row = True
                        break
                if not found_row:
                    rows.append({"y": loc_y, "elements": [opt]})
            for row in rows:
                clicked = False
                row_text = " ".join(
                    (el.text or "").strip().lower()
                    for el in row["elements"]
                    if el is not None
                )
                is_english_row = ("ingl" in row_text or "english" in row_text)
                levels = english_levels if is_english_row else default_levels
                for level in levels:
                    if clicked:
                        break
                    for el in row["elements"]:
                        text = (el.text or "").strip().lower()
                        if level.lower() in text or level.lower() == text:
                            try:
                                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", el)
                                get_random_delay(0.25, 0.5)
                                self.driver.execute_script("arguments[0].click();", el)
                                get_random_delay(0.3, 0.5)
                                clicked = True
                                row_kind = "ingles" if is_english_row else "general"
                                print(f"[{self.sitio}] Modal fila ({row_kind}) -> {level}")
                                break
                            except Exception:
                                pass
                if not clicked:
                    row_kind = "ingles" if is_english_row else "general"
                    print(f"[{self.sitio}] Modal fila ({row_kind}) sin match de nivel.")
            get_random_delay(0.4, 0.8)
        except Exception as e:
            print(f"[{self.sitio}] Error al agrupar o procesar opciones del modal: {e}")

    def _modal_postular_enabled(self, container):
        try:
            btn = None
            for by, selector in [
                (By.CSS_SELECTOR, "[skills-apply]"),
                (By.XPATH, ".//*[self::button or self::a][contains(normalize-space(.), 'Postularme')]"),
            ]:
                els = container.find_elements(by, selector)
                for el in els:
                    if el.is_displayed():
                        btn = el
                        break
                if btn:
                    break
            if not btn:
                return False
            if btn.get_attribute("disabled"):
                return False
            if btn.get_attribute("aria-disabled") == "true":
                return False
            if "disabled" in (btn.get_attribute("class") or "").lower():
                return False
            return True
        except Exception:
            return False