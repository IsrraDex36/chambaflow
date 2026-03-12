from utils import get_random_delay, take_screenshot
import re
import os
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, StaleElementReferenceException
)


# ─────────────────────────────────────────────────────────────
#  ESTRUCTURA REAL DE COMPUTRABAJO MX (HTML inspeccionado 2026-03)
#
#  Búsqueda:
#    https://mx.computrabajo.com/trabajo-de-{keyword}
#    ej: https://mx.computrabajo.com/trabajo-de-desarrollador-react
#
#  Paginación: botón con data-path
#    <span class="b_primary w48 buildLink cp"
#          data-path="https://mx.computrabajo.com/trabajo-de-desarrollador-en-remoto?p=2">
#        Siguiente
#    </span>
#
#  Card en el listado:
#    <article class="box_offer" data-id="91308949D246B6B861373E686DCF3405"
#             data-offers-grid-offer-item-container="">
#      <h2 class="fs18 fwB prB">
#        <a class="js-o-link fc_base" href="/ofertas-de-trabajo/...">Título</a>
#      </h2>
#      <p class="dFlex vm_fx fs16 fc_base mt5">
#        <a offer-grid-article-company-url="">Empresa S.A.</a>  <!-- o <span> -->
#      </p>
#      <p class="fs16 fc_base mt5">
#        <span class="mr10">Ciudad, Estado</span>
#      </p>
#      <!-- Badge "Ya postulado": -->
#      <span class="tag postulated" applied-offer-tag="">Postulado</span>
#    </article>
#
#  Panel derecho (se renderiza vía Handlebars al hacer click en la card):
#    <div data-offers-grid-detail-container="">
#      <p class="title_offer" data-offers-grid-detail-title="">Título</p>
#      <!-- Botón postular (no logueado → redirige a login): -->
#      <span data-apply-link data-href-offer-apply="https://candidato.mx.computrabajo.com/candidate/apply/?oi=...">
#          Postularme
#      </span>
#      <!-- Badge ya postulado: -->
#      <div class="sub_box_top" offer-detail-applied="">Ya aplicaste a esta oferta</div>
#    </div>
#
#  Apply flow (candidato logueado):
#    Navega a https://candidato.mx.computrabajo.com/candidate/apply/?oi=...
#    Flujo multi-paso similar a OCC: datos personales, CV, preguntas opcionales, confirmar.
# ─────────────────────────────────────────────────────────────

CARD_SEL     = "article.box_offer[data-offers-grid-offer-item-container]"
DETAIL_SEL   = "[data-offers-grid-detail-container]"
APPLY_BTN_SEL = "[data-apply-link][data-href-offer-apply]"


class BotComputrabajo:
    def __init__(
        self,
        driver,
        dry_run: bool = False,
        controlled_mode: bool = False,
        max_scan_per_keyword: int = 6,
        filter_config: dict | None = None,
    ):
        self.driver = driver
        self.dry_run = dry_run
        self.sitio = "Computrabajo"
        self.controlled_mode = controlled_mode
        self.max_scan_per_keyword = max(1, int(max_scan_per_keyword))
        self.search_url = ""

        fc = filter_config or {}
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

    # ─────────────────────────────────────────────
    # ENTRY POINT
    # ─────────────────────────────────────────────

    def search_and_apply(self, keyword, cv_path, max_apps):
        """
        Punto de entrada principal. Recorre páginas de resultados,
        filtra vacantes relevantes y aplica a cada una.
        """
        apps_done = 0
        keyword_low = (keyword or "").lower()

        # Construir URL de búsqueda:
        # "desarrollador react" → "desarrollador-react"
        slug = re.sub(r"\s+", "-", keyword.strip().lower())
        slug = re.sub(r"[^a-z0-9\-]", "", slug)
        self.search_url = f"https://mx.computrabajo.com/trabajo-de-{slug}"

        try:
            print(f"[{self.sitio}] Buscando: {keyword}")
            self.driver.get(self.search_url)
            get_random_delay(2.5, 4.0)

            if self.dry_run:
                print(f"[{self.sitio}] [DRY-RUN] Simulando búsqueda...")
                return min(2, max_apps)

            max_scan = (
                self.max_scan_per_keyword
                if self.controlled_mode
                else max(30, max_apps * 8)
            )
            seen_ids: set[str] = set()
            page_num = 1

            while apps_done < max_apps:
                if not self._wait_for_cards():
                    print(f"[{self.sitio}] No se cargaron cards en pág {page_num}.")
                    break

                job_items = self._collect_job_items(limit=max_scan)
                new_items = [j for j in job_items if j["oi"] not in seen_ids]
                print(
                    f"[{self.sitio}] Pág {page_num}: "
                    f"{len(job_items)} cards ({len(new_items)} nuevas)"
                )

                if not new_items:
                    print(f"[{self.sitio}] Sin nuevas vacantes en pág {page_num}.")
                    break

                for idx, item in enumerate(new_items):
                    if apps_done >= max_apps:
                        break

                    oi      = item["oi"]
                    title   = item.get("title") or "Sin título"
                    company = item.get("company") or ""
                    seen_ids.add(oi)

                    if not self._is_relevant(title, keyword_low):
                        print(f"[{self.sitio}] Saltada (no relevante): {title}")
                        continue

                    print(
                        f"[{self.sitio}] [{idx+1}/{len(new_items)}] "
                        f"{title} — {company}"
                    )

                    if not self._click_card(oi, title):
                        print(f"[{self.sitio}] No se pudo abrir card: {title}")
                        continue

                    if self.apply_to_job(cv_path, oi=oi, title=title):
                        apps_done += 1

                if apps_done >= max_apps:
                    break

                # Ir a la siguiente página
                next_url = self._get_next_page_url()
                if not next_url:
                    print(f"[{self.sitio}] Sin página siguiente, fin.")
                    break

                page_num += 1
                self.driver.get(next_url)
                get_random_delay(2.0, 3.5)

        except Exception as e:
            take_screenshot(self.driver, "computrabajo_main_error")
            print(f"[{self.sitio}] Error principal: {e}")

        print(f"[{self.sitio}] Postulaciones '{keyword}': {apps_done}")
        return apps_done

    # ─────────────────────────────────────────────
    # ESPERA Y CONTEO DE CARDS
    # ─────────────────────────────────────────────

    def _wait_for_cards(self, timeout=15):
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, CARD_SEL))
            )
            get_random_delay(0.8, 1.5)
            return True
        except TimeoutException:
            src = (self.driver.page_source or "").lower()
            if "captcha" in src or "robot" in src:
                print(f"[{self.sitio}] ⚠️  CAPTCHA detectado. Esperando 30s...")
                get_random_delay(28, 35)
                return self._count_cards() > 0
            return False

    def _count_cards(self):
        try:
            return len(self.driver.find_elements(By.CSS_SELECTOR, CARD_SEL))
        except:
            return 0

    # ─────────────────────────────────────────────
    # PAGINACIÓN
    # ─────────────────────────────────────────────

    def _get_next_page_url(self):
        """
        Computrabajo MX usa un botón con data-path para paginar:
          <span class="b_primary w48 buildLink cp"
                data-path="...?p=2" title="Siguiente">
              Siguiente
          </span>
        Devuelve la URL de la siguiente página o None si no existe.
        """
        try:
            btns = self.driver.find_elements(
                By.CSS_SELECTOR,
                "span.buildLink[data-path]"
            )
            for btn in btns:
                text = (btn.text or "").strip().lower()
                if "siguiente" in text or "next" in text:
                    url = btn.get_attribute("data-path")
                    if url:
                        return url
        except Exception as e:
            print(f"[{self.sitio}] Error obteniendo siguiente página: {e}")
        return None

    # ─────────────────────────────────────────────
    # RECOLECCIÓN DE VACANTES
    # ─────────────────────────────────────────────

    def _collect_job_items(self, limit=100):
        """
        Lee oi (data-id), título, empresa y ubicación de cada card.

        HTML real confirmado:
          <article data-id="OI_HEX" data-offers-grid-offer-item-container>
            <h2><a class="js-o-link">Título</a></h2>
            <p class="dFlex ..."><a offer-grid-article-company-url>Empresa</a></p>
            <p class="fs16 ..."><span class="mr10">Ciudad</span></p>
          </article>
        """
        try:
            items = self.driver.execute_script("""
                const cards = document.querySelectorAll(arguments[0]);
                const results = [];

                cards.forEach(card => {
                    const oi = card.getAttribute('data-id');
                    if (!oi) return;

                    // Título: enlace principal
                    const titleEl = card.querySelector('h2 a.js-o-link');
                    const title = titleEl
                        ? titleEl.innerText.trim()
                        : '';

                    // Empresa: preferir <a> con atributo, fallback a <span>
                    const compEl = card.querySelector(
                        '[offer-grid-article-company-url]'
                    );
                    const company = compEl ? compEl.innerText.trim() : '';

                    // Ubicación: primer <span class="mr10"> dentro del 2.º <p>
                    const locEl = card.querySelector('p.fs16 span.mr10');
                    const location = locEl ? locEl.innerText.trim() : '';

                    // ¿Ya postulado?
                    const appliedTag = card.querySelector('[applied-offer-tag]');
                    const already = appliedTag
                        ? !appliedTag.classList.contains('hide')
                        : false;

                    results.push({ oi, title, company, location, already_applied: already });
                });

                return results.slice(0, arguments[1]);
            """, CARD_SEL, limit)
            return items or []
        except Exception as e:
            print(f"[{self.sitio}] Error recolectando items: {e}")
            return []

    # ─────────────────────────────────────────────
    # CLICK EN CARD → PANEL DERECHO
    # ─────────────────────────────────────────────

    def _click_card(self, oi, expected_title=""):
        """
        Hace click en el artículo con data-id=oi para cargar
        el panel derecho [data-offers-grid-detail-container].

        Intento 1: JS click en el <a> del título
        Intento 2: JS click en el <article>
        Intento 3: ActionChains en el <a>
        Intento 4: verificar si el panel igual cargó
        """
        card_css = f'article.box_offer[data-id="{oi}"]'
        link_css = f'{card_css} h2 a.js-o-link'

        # ── Intento 1: JS click en el título ──
        try:
            link = self.driver.find_element(By.CSS_SELECTOR, link_css)
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center',behavior:'smooth'});",
                link
            )
            get_random_delay(0.5, 0.9)
            self.driver.execute_script("arguments[0].click();", link)
            get_random_delay(1.8, 2.8)

            if self._panel_has_content(expected_title):
                print(f"[{self.sitio}] Card {oi[:8]}… abierta (JS título) OK")
                return True
        except StaleElementReferenceException:
            print(f"[{self.sitio}] StaleElement en card {oi[:8]}…, reintentando...")
        except Exception as e:
            print(f"[{self.sitio}] JS click link error card {oi[:8]}…: {e}")

        # ── Intento 2: JS click en el article ──
        try:
            card = self.driver.find_element(By.CSS_SELECTOR, card_css)
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", card
            )
            get_random_delay(0.4, 0.7)
            self.driver.execute_script("arguments[0].click();", card)
            get_random_delay(1.8, 2.8)

            if self._panel_has_content(expected_title):
                print(f"[{self.sitio}] Card {oi[:8]}… abierta (JS article) OK")
                return True
        except Exception as e:
            print(f"[{self.sitio}] JS click article error card {oi[:8]}…: {e}")

        # ── Intento 3: ActionChains ──
        try:
            link = self.driver.find_element(By.CSS_SELECTOR, link_css)
            self.driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", link
            )
            get_random_delay(0.4, 0.7)
            ActionChains(self.driver)\
                .move_to_element(link).pause(0.3).click().perform()
            get_random_delay(1.8, 2.8)

            if self._panel_has_content(expected_title):
                print(f"[{self.sitio}] Card {oi[:8]}… abierta (ActionChains) OK")
                return True
        except Exception as e:
            print(f"[{self.sitio}] ActionChains error card {oi[:8]}…: {e}")

        # ── Intento 4: verificar panel igual ──
        if self._panel_has_content(expected_title) or self._has_apply_button():
            print(f"[{self.sitio}] Card {oi[:8]}… — panel detectado igualmente OK")
            return True

        print(f"[{self.sitio}] Falló apertura de card {oi[:8]}…")
        return False

    # ─────────────────────────────────────────────
    # VERIFICACIÓN DEL PANEL DERECHO
    # ─────────────────────────────────────────────

    def _panel_has_content(self, expected_title=""):
        """
        Verifica que el panel derecho (renderizado por Handlebars)
        cargó una vacante.

        HTML real del panel:
          <div data-offers-grid-detail-container="">
            <p class="title_offer" data-offers-grid-detail-title="">Título</p>
            <span data-apply-link data-href-offer-apply="...">Postularme</span>
          </div>
        """
        try:
            result = self.driver.execute_script("""
                const panel = document.querySelector(arguments[0]);
                if (!panel || panel.offsetParent === null) {
                    return { found: false, text: '' };
                }

                // Título renderizado por Handlebars
                const titleEl = panel.querySelector(
                    '[data-offers-grid-detail-title], .title_offer'
                );
                const txt = titleEl ? titleEl.innerText.trim() : '';

                // Botón de postulación visible
                const applyBtn = panel.querySelector(
                    '[data-apply-link][data-href-offer-apply]'
                );
                const hasBtn = !!applyBtn;

                if (txt.length > 3 || hasBtn) {
                    return { found: true, text: txt };
                }
                return { found: false, text: '' };
            """, DETAIL_SEL)

            if not result or not result.get("found"):
                return False

            if expected_title:
                panel_text = (result.get("text") or "").lower()
                short = expected_title[:35].strip().lower()
                if short and panel_text and short not in panel_text:
                    return bool(panel_text)

            return True

        except Exception as e:
            print(f"[{self.sitio}] Error verificando panel: {e}")
            return False

    def _has_apply_button(self):
        """Comprueba si el botón 'Postularme' es visible en el panel."""
        try:
            btns = self.driver.find_elements(
                By.CSS_SELECTOR, APPLY_BTN_SEL
            )
            return any(b.is_displayed() for b in btns)
        except:
            return False

    def _get_apply_url(self):
        """
        Extrae la URL de postulación del atributo data-href-offer-apply.
        El botón puede estar oculto o visible — buscamos el que tenga URL.
        """
        try:
            btns = self.driver.find_elements(
                By.CSS_SELECTOR,
                f"{DETAIL_SEL} {APPLY_BTN_SEL}"
            )
            if not btns:
                # Fallback: buscar en todo el documento
                btns = self.driver.find_elements(
                    By.CSS_SELECTOR, APPLY_BTN_SEL
                )
            for btn in btns:
                url = btn.get_attribute("data-href-offer-apply")
                if url and url.startswith("http"):
                    return url
        except Exception as e:
            print(f"[{self.sitio}] Error obteniendo URL de apply: {e}")
        return None

    def _click_postularme(self):
        """
        Hace click en el botón/link "Postularme" del panel.
        No navega con driver.get: solo click para que el sitio haga su flujo normal.
        Devuelve True si se encontró y se clickeó el elemento.
        """
        try:
            btns = self.driver.find_elements(
                By.CSS_SELECTOR,
                f"{DETAIL_SEL} {APPLY_BTN_SEL}"
            )
            if not btns:
                btns = self.driver.find_elements(
                    By.CSS_SELECTOR, APPLY_BTN_SEL
                )
            for btn in btns:
                if not btn.is_displayed():
                    continue
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", btn
                )
                get_random_delay(0.3, 0.6)
                self.driver.execute_script("arguments[0].click();", btn)
                return True
        except Exception as e:
            print(f"[{self.sitio}] Error haciendo click en Postularme: {e}")
        return False

    # ─────────────────────────────────────────────
    # NAVEGACIÓN / RECUPERACIÓN
    # ─────────────────────────────────────────────

    def _go_back_to_search(self):
        print(f"[{self.sitio}] Volviendo al listado...")
        self.driver.get(self.search_url)
        get_random_delay(1.5, 2.5)

    # ─────────────────────────────────────────────
    # FILTRADO DE RELEVANCIA
    # ─────────────────────────────────────────────

    def _is_relevant(self, title, keyword_low):
        title_low = (title or "").lower().strip()
        if not title_low:
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

    def apply_to_job(self, cv_path, oi=None, title=""):
        """
        Flujo de postulación en Computrabajo MX:
        1. Verificar si ya está postulado
        2. Solo hacer click en "Postularme" (no redirigir con driver.get)
        3. El sitio lleva al formulario; completar el flujo multi-paso
        4. Volver al listado
        """
        # ── Verificar si ya está postulado ──
        if self._already_applied_panel():
            print(f"[{self.sitio}] Ya aplicado a: {title}")
            return False

        if not self._click_postularme():
            print(f"[{self.sitio}] No se encontró botón Postularme para: {title}")
            return False

        print(f"[{self.sitio}] Aplicando a: {title}")
        get_random_delay(2.0, 3.5)

        success = self._handle_apply_flow(cv_path, oi=oi, title=title)

        # Volver al listado de búsqueda
        self._go_back_to_search()
        get_random_delay(1.5, 2.5)

        return success

    def _already_applied_panel(self):
        """Verifica si el panel muestra el badge 'Ya aplicaste'."""
        try:
            result = self.driver.execute_script("""
                const panel = document.querySelector(arguments[0]);
                if (!panel) return false;

                // Badge visible en la card activa
                const appliedTag = document.querySelector(
                    '.box_offer.sel [applied-offer-tag]:not(.hide)'
                );
                if (appliedTag) return true;

                // Sub-box en el panel de detalle
                const appliedBox = panel.querySelector('[offer-detail-applied]');
                if (appliedBox && !appliedBox.classList.contains('hide')) return true;

                return false;
            """, DETAIL_SEL)
            return bool(result)
        except:
            return False

    # ─────────────────────────────────────────────
    # FLUJO DE POSTULACIÓN (candidato.mx.computrabajo.com)
    # ─────────────────────────────────────────────

    def _handle_apply_flow(self, cv_path, oi=None, title=""):
        """
        Navega el formulario multi-paso de Computrabajo.
        Tras "Postularme" puede abrirse formulario in-page (Preguntas de selección)
        o redirigir a candidato.mx.computrabajo.com.
        """
        get_random_delay(1.5, 2.5)
        max_steps = 10
        for step in range(1, max_steps + 1):
            print(f"[{self.sitio}] Apply step {step}/{max_steps}")

            page_type = self._detect_apply_page_type()
            print(f"[{self.sitio}] Tipo de paso: {page_type}")

            if page_type == "confirmation":
                return True

            if page_type == "already_applied":
                print(f"[{self.sitio}] Ya estaba postulado (detectado en flujo).")
                return False

            if page_type == "cv_upload":
                self._handle_cv_step(cv_path)

            elif page_type == "questions":
                self._handle_questions_step()
                # Formulario in-page "Preguntas de selección" usa "Enviar mi CV", no "Continuar"
                if self._click_submit_button():
                    get_random_delay(2.0, 3.5)
                    if self._application_confirmed():
                        return True
                    continue

            elif page_type == "personal_data":
                # Datos ya deberían estar pre-rellenados para usuario logueado
                pass

            elif page_type == "review":
                if self._click_submit_button():
                    get_random_delay(2.0, 3.5)
                    if self._application_confirmed():
                        return True
                    # Puede que la confirmación sea en la siguiente página
                    continue

                if not self._click_continue_button():
                    break

            elif page_type == "unknown":
                # Formularios variables: intentar rellenar y cualquier botón de avance
                self._handle_questions_step()
                if self._click_submit_button():
                    get_random_delay(2.0, 3.0)
                    if self._application_confirmed():
                        return True
                    continue
                if not self._click_continue_button():
                    break
                get_random_delay(1.0, 1.8)
                continue

            if page_type not in ("review",):
                self._click_continue_button()

            get_random_delay(1.2, 2.2)

        if self._application_confirmed():
            return True

        self._capture_apply_failure_debug(oi=oi, title=title)
        return False

    # ─────────────────────────────────────────────
    # DETECCIÓN DE TIPO DE PASO
    # ─────────────────────────────────────────────

    def _detect_apply_page_type(self):
        """
        Identifica el paso actual del wizard de Computrabajo.
        Devuelve: 'cv_upload' | 'questions' | 'personal_data' |
                  'review' | 'confirmation' | 'already_applied' | 'unknown'
        """
        try:
            page_text = (
                self.driver.execute_script(
                    "return document.body"
                    " ? document.body.innerText.toLowerCase() : '';"
                ) or ""
            )
            url = self.driver.current_url.lower()

            # Confirmación
            if any(s in page_text for s in [
                "postulación enviada",
                "ya te has postulado",
                "solicitud enviada",
                "aplicación enviada",
                "gracias por postularte",
                "tu postulación fue",
                "felicidades",
            ]) or "success" in url or "gracias" in url:
                return "confirmation"

            # Ya postulado
            if any(s in page_text for s in [
                "ya aplicaste",
                "ya te postulaste",
                "ya has postulado",
                "ya postulado",
            ]):
                return "already_applied"

            # Subir CV
            if (
                any(s in page_text for s in [
                    "adjuntar cv", "subir cv", "curriculum",
                    "currículum", "upload cv", "resume"
                ])
                and self.driver.find_elements(
                    By.CSS_SELECTOR, "input[type='file']"
                )
            ):
                return "cv_upload"

            # Preguntas de selección (formulario in-page tras "Postularme") o preguntas adicionales
            if any(s in page_text for s in [
                "preguntas de selección",
                "ya casi estamos",
                "preguntas adicionales",
                "preguntas del empleador",
                "¿cuántos años",
                "años de experiencia",
                "nivel de inglés",
                "disponibilidad",
                "conocimientos",
            ]):
                return "questions"

            # Datos personales
            if any(s in page_text for s in [
                "datos personales",
                "información personal",
                "nombre completo",
                "teléfono",
            ]):
                return "personal_data"

            # Revisión / envío
            if any(s in page_text for s in [
                "revisar y enviar",
                "confirmar postulación",
                "enviar postulación",
                "enviar solicitud",
                "postularme",
            ]):
                return "review"

            if self._find_submit_button():
                return "review"

            # Formulario variable: hay campos rellenables en zona de apply
            if self._has_visible_form_fields():
                return "questions"

            return "unknown"

        except Exception as e:
            print(f"[{self.sitio}] Error detectando tipo de paso: {e}")
            return "unknown"

    def _has_visible_form_fields(self):
        """True si hay radios, selects o inputs visibles (formularios variables)."""
        try:
            els = self.driver.find_elements(
                By.CSS_SELECTOR,
                "input[type='radio'], select, input[type='text'], input[type='number'], textarea"
            )
            return any(e.is_displayed() for e in els)
        except Exception:
            pass
        return False

    # ─────────────────────────────────────────────
    # MANEJO DE PASOS DEL FORMULARIO
    # ─────────────────────────────────────────────

    def _handle_cv_step(self, cv_path):
        try:
            file_input = WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input[type='file']")
                )
            )
            file_input.send_keys(cv_path)
            get_random_delay(1.0, 2.0)
            print(f"[{self.sitio}] CV subido.")
        except TimeoutException:
            print(f"[{self.sitio}] No se encontró input de archivo.")
        except Exception as e:
            print(f"[{self.sitio}] Error subiendo CV: {e}")

    def _handle_questions_step(self):
        """
        Responde formularios variables (N preguntas, distintos tipos):
        - Selects → primera opción válida (no vacía)
        - Radios  → preferir opciones positivas/altas (avanzado, sí, intermedio…)
        - Text/number/textarea → valor según contexto (años→3, experiencia→texto genérico)
        - Checkboxes → marcar si tiene sentido (p. ej. "Acepto")
        """
        try:
            # 1) Selects
            for sel_el in self.driver.find_elements(By.CSS_SELECTOR, "select"):
                if not sel_el.is_displayed():
                    continue
                opts = sel_el.find_elements(By.TAG_NAME, "option")
                for opt in opts[1:]:
                    val = (opt.get_attribute("value") or "").strip()
                    if val:
                        self.driver.execute_script(
                            "arguments[0].value = arguments[1]; "
                            "arguments[0].dispatchEvent("
                            "  new Event('change', {bubbles: true}));",
                            sel_el, val
                        )
                        break
                get_random_delay(0.3, 0.5)

            # 2) Radios: preferir positivos/altos, evitar negativos
            radio_groups: dict[str, list] = {}
            for radio in self.driver.find_elements(
                By.CSS_SELECTOR, "input[type='radio']"
            ):
                if not radio.is_displayed():
                    continue
                name = radio.get_attribute("name") or "unnamed"
                radio_groups.setdefault(name, []).append(radio)

            prefer_positive = (
                "avanzado", "experto", "sí, avanzada", "sí, intermedia",
                "intermedio", "sí, básica", "básico", "sí", "si", "yes",
                "siempre", "suficiente", "muchos", "varios", "habitual",
            )
            avoid_negative = ("ninguno", "ninguna", "no ", "nunca", "nada", "poco")
            for name, radios in radio_groups.items():
                chosen = None
                for pref in prefer_positive:
                    for r in radios:
                        label_text = self._get_radio_label(r).lower().strip()
                        if pref in label_text and not any(
                            neg in label_text for neg in avoid_negative
                        ):
                            chosen = r
                            break
                    if chosen:
                        break
                if not chosen:
                    chosen = radios[-1]
                try:
                    self.driver.execute_script("arguments[0].click();", chosen)
                    get_random_delay(0.3, 0.5)
                except Exception:
                    pass

            # 3) Text / number / textarea: valor según placeholder o tipo
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

            # 4) Checkboxes: marcar los que parecen “acepto” / obligatorios
            for cb in self.driver.find_elements(
                By.CSS_SELECTOR, "input[type='checkbox']"
            ):
                if not cb.is_displayed() or cb.is_selected():
                    continue
                label_text = self._get_radio_label(cb).lower()
                if any(
                    k in label_text
                    for k in ("acepto", "aceptar", "entendido", "confirmo")
                ):
                    try:
                        self.driver.execute_script("arguments[0].click();", cb)
                        get_random_delay(0.2, 0.4)
                    except Exception:
                        pass

            print(f"[{self.sitio}] Paso de preguntas completado.")

        except Exception as e:
            print(f"[{self.sitio}] Error en paso de preguntas: {e}")

    def _get_input_label_or_aria(self, inp):
        """Obtiene contexto del input (label asociado o aria-label)."""
        try:
            inp_id = inp.get_attribute("id")
            if inp_id:
                label = self.driver.find_elements(
                    By.CSS_SELECTOR, f"label[for='{inp_id}']"
                )
                if label:
                    return label[0].text or ""
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
        """
        Infiere valor genérico según contexto (pueden variar las tareas).
        - Años / número → "3"
        - Experiencia / descripción → "3 años de experiencia"
        - Otro texto → "Sí" o texto corto genérico
        """
        ctx = f"{placeholder} {label_ctx}"
        if inp_type == "number":
            return "3"
        if any(k in ctx for k in ("año", "year", "edad", "número", "numero")):
            return "3"
        if any(k in ctx for k in ("experiencia", "descripción", "descripcion", "comentario")):
            return "3 años de experiencia"
        if any(k in ctx for k in ("sueldo", "salario", "pretensión", "pretension")):
            return "Según oferta"
        return "3 años de experiencia"

    def _get_radio_label(self, radio_el):
        try:
            radio_id = radio_el.get_attribute("id")
            if radio_id:
                label = self.driver.find_element(
                    By.CSS_SELECTOR, f"label[for='{radio_id}']"
                )
                return label.text or ""
            return radio_el.find_element(
                By.XPATH, "./ancestor::label[1]"
            ).text or ""
        except:
            return ""

    # ─────────────────────────────────────────────
    # BOTONES DE NAVEGACIÓN DEL WIZARD
    # ─────────────────────────────────────────────

    def _click_continue_button(self):
        xpaths = [
            "//button[contains(normalize-space(.), 'Continuar') and not(@disabled)]",
            "//button[contains(normalize-space(.), 'Siguiente') and not(@disabled)]",
            "//input[@type='button' and contains(@value,'Continuar')]",
            "//input[@type='submit' and not(@disabled)]",
            "//button[@type='button' and not(@disabled)]",
        ]
        for xp in xpaths:
            try:
                btn = self.driver.find_element(By.XPATH, xp)
                if btn.is_displayed():
                    self.driver.execute_script("arguments[0].click();", btn)
                    get_random_delay(1.0, 1.8)
                    return True
            except:
                continue
        return False

    def _find_submit_button(self):
        xpaths = [
            "//a[contains(normalize-space(.), 'Enviar mi CV') and not(@disabled)]",
            "//a[@data-apply-ac-kq]",
            "//button[not(@disabled) and @type='submit']",
            "//input[not(@disabled) and @type='submit']",
            "//button[not(@disabled) and contains(normalize-space(.), 'Postularme')]",
            "//button[not(@disabled) and contains(normalize-space(.), 'Enviar')]",
            "//button[not(@disabled) and contains(normalize-space(.), 'Confirmar')]",
            "//input[not(@disabled) and contains(@value,'Postularme')]",
            "//input[not(@disabled) and contains(@value,'Enviar')]",
        ]
        for xp in xpaths:
            try:
                btn = self.driver.find_element(By.XPATH, xp)
                if btn.is_displayed():
                    return btn
            except:
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

    def _application_confirmed(self):
        try:
            page_text = (self.driver.page_source or "").lower()
            url = self.driver.current_url.lower()
            signals = [
                "postulación enviada",
                "ya te has postulado",
                "solicitud enviada",
                "gracias por postularte",
                "tu postulación fue",
                "felicidades",
                "ya aplicaste",
            ]
            return any(s in page_text for s in signals) or (
                "success" in url or "gracias" in url
            )
        except:
            return False

    # ─────────────────────────────────────────────
    # DEBUG EN CASO DE FALLO
    # ─────────────────────────────────────────────

    def _capture_apply_failure_debug(self, oi=None, title=""):
        try:
            os.makedirs("screenshots", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_oi = re.sub(r"[^0-9A-Za-z_-]+", "_", str(oi or "unknown"))
            safe_title = re.sub(
                r"[^0-9A-Za-z_-]+", "_", (title or "sin_titulo")
            ).strip("_")[:50]

            page_path = take_screenshot(
                self.driver, f"computrabajo_fail_{safe_oi}_{timestamp}"
            )
            log_path = os.path.join("screenshots", "computrabajo_apply_failures.log")

            with open(log_path, "a", encoding="utf-8") as f:
                f.write(
                    f"{datetime.now().isoformat()} | "
                    f"oi={oi or 'unknown'} | "
                    f"title={safe_title} | "
                    f"url={self.driver.current_url} | "
                    f"search={self.search_url} | "
                    f"page_shot={page_path}\n"
                )

            print(f"[{self.sitio}] Debug guardado (oi={oi}, page={page_path})")
        except Exception as e:
            print(f"[{self.sitio}] No se pudo guardar debug: {e}")