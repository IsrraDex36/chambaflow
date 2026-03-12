from utils import get_random_delay, take_screenshot
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementNotInteractableException, InvalidSessionIdException
from llm_helper import answer_indeed_question
import time

class BotIndeed:
    def __init__(self, driver, dry_run=False, api_key="", user_profile=""):
        self.driver = driver
        self.dry_run = dry_run
        self.sitio = "Indeed"
        self.api_key = api_key
        self.user_profile = user_profile

    def _is_logged_in(self):
        try:
            # Señales comunes de sesión activa en Indeed.
            profile_signals = self.driver.find_elements(
                By.XPATH,
                "//a[contains(@href, '/my/profile') or contains(@href, '/account') or contains(@aria-label, 'Cuenta') or contains(@aria-label, 'Account')]"
            )
            login_link = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'account/login')]")
            if profile_signals and not login_link:
                return True
            if profile_signals and login_link:
                # En algunos layouts coexisten links de login y cuenta.
                return True
            return False
        except Exception:
            return False

    def _captcha_present(self):
        captcha_selectors = [
            "iframe[src*='recaptcha']",
            "iframe[src*='hcaptcha']",
            "div.g-recaptcha",
            "[data-testid*='captcha']",
            "#captcha",
        ]
        try:
            for selector in captcha_selectors:
                if self.driver.find_elements(By.CSS_SELECTOR, selector):
                    return True
        except Exception:
            pass

        try:
            page = self.driver.page_source.lower()
        except InvalidSessionIdException:
            return False
        except Exception:
            return False
        captcha_signals = [
            "no soy un robot",
            "i'm not a robot",
            "verify you are human",
            "verifica que eres humano",
            "recaptcha",
            "hcaptcha",
        ]
        return any(signal in page for signal in captcha_signals)

    def _wait_for_manual_captcha_resolution(self, timeout_seconds=180):
        if not self._captcha_present():
            return True

        print(f"[{self.sitio}] CAPTCHA detectado. Resuélvelo manualmente en el navegador.")
        print(f"[{self.sitio}] Esperando hasta {timeout_seconds} segundos...")

        waited = 0
        poll_seconds = 5
        while waited < timeout_seconds:
            time.sleep(poll_seconds)
            waited += poll_seconds
            if not self._captcha_present():
                print(f"[{self.sitio}] CAPTCHA resuelto, continuando flujo.")
                return True

        print(f"[{self.sitio}] CAPTCHA no resuelto a tiempo. Se omite esta operación.")
        return False

    def check_login(self):
        print(f"[{self.sitio}] Verificando sesión...")
        self.driver.get("https://mx.indeed.com/")
        get_random_delay(3, 5)
        if not self._wait_for_manual_captcha_resolution(timeout_seconds=240):
            return False
        try:
            if self._is_logged_in():
                print(f"[{self.sitio}] Sesión detectada.")
                return True

            print(f"[{self.sitio}] No se detectó sesión iniciada. Inicia sesión manualmente en el navegador.")
            print(f"[{self.sitio}] Esperando hasta 240 segundos...")
            waited = 0
            poll_seconds = 5
            while waited < 240:
                time.sleep(poll_seconds)
                waited += poll_seconds
                if not self._wait_for_manual_captcha_resolution(timeout_seconds=240):
                    return False
                if self._is_logged_in():
                    print(f"[{self.sitio}] Sesión iniciada correctamente.")
                    return True

            print(f"[{self.sitio}] No se confirmó sesión después del tiempo de espera.")
            return False
        except Exception as e:
            print(f"[{self.sitio}] Error verificando sesión: {e}")
            return False

    def search_and_apply(self, keyword, cv_path, max_apps):
        try:
            if not self.check_login():
                print(f"[{self.sitio}] Sesión no lista. Se omite búsqueda '{keyword}'.")
                return 0
        except InvalidSessionIdException:
            print(f"[{self.sitio}] La sesión del navegador se cerró. Deteniendo bot de Indeed.")
            return 0
        apps_done = 0
        try:
            print(f"[{self.sitio}] Buscando: {keyword}")
            # El parámetro sc=0kf%3Aattr%28DSQF7%29%3B filtra por "Postulación via Indeed" (Easy Apply)
            url = f"https://mx.indeed.com/jobs?q={keyword.replace(' ', '+')}&sc=0kf%3Aattr%28DSQF7%29%3B"
            self.driver.get(url)
            get_random_delay(4, 7)
            if not self._wait_for_manual_captcha_resolution(timeout_seconds=180):
                return apps_done
            
            if self.dry_run:
                print(f"[{self.sitio}] [DRY-RUN] Simulando búsqueda para '{keyword}'...")
                return min(2, max_apps)
                
            jobs = self.driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon")
            for i in range(len(jobs)):
                if apps_done >= max_apps:
                    break
                try:
                    # Refrescar la lista para evitar StaleElementReferenceException
                    jobs = self.driver.find_elements(By.CSS_SELECTOR, "div.job_seen_beacon")
                    job = jobs[i]
                    
                    title_elem = job.find_element(By.CSS_SELECTOR, "h2.jobTitle span[title]")
                    title = title_elem.get_attribute("title")
                    company = job.find_element(By.CSS_SELECTOR, "span[data-testid='company-name']").text
                    
                    print(f"[{self.sitio}] Encontrado: {title} en {company}")
                    
                    # Scroll al elemento y clic
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", job)
                    get_random_delay(1, 2)
                    job.click()
                    get_random_delay(3, 5)
                    
                    # Intentar postular
                    if self.apply_to_job(cv_path):
                        apps_done += 1
                except (StaleElementReferenceException, ElementNotInteractableException):
                    print(f"[{self.sitio}] Elemento obsoleto o no interactuable, saltando...")
                except Exception as e:
                    take_screenshot(self.driver, "indeed_job_error")
                    print(f"[{self.sitio}] Error procesando vacante: {e}")
            
        except Exception as e:
            take_screenshot(self.driver, "indeed_search_error")
            print(f"[{self.sitio}] Error principal: {e}")
        return apps_done

    def apply_to_job(self, cv_path):
        try:
            # Encontrar y cliquear el botón de postulación en el panel derecho superior
            try:
                apply_btn = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#indeedApplyButton"))
                )
                print(f"[{self.sitio}] Iniciando postulación rápida...")
                # Scroll por si acaso
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", apply_btn)
                get_random_delay(1, 2)
                self.driver.execute_script("arguments[0].click();", apply_btn)
            except TimeoutException:
                # Intento alternativo por clases si falla el ID
                apply_btn = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//button[contains(@class, 'jobsearch-JobApplyButton')]"))
                )
                print(f"[{self.sitio}] Iniciando postulación (selector alterno)...")
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", apply_btn)
                get_random_delay(1, 2)
                self.driver.execute_script("arguments[0].click();", apply_btn)

            get_random_delay(4, 7)
            
            # Cambiar a la ventana modal si Indeed Apply abrió un pop-up real (handles)
            original_window = self.driver.current_window_handle
            for window_handle in self.driver.window_handles:
                if window_handle != original_window:
                    self.driver.switch_to.window(window_handle)
                    break
            
            # Cambiar al iframe principal del formulario
            try:
                # Indeed a menudo pone iframe dentro de iframe
                iframe = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[title*='Apply'], iframe[name*='indeedapply']"))
                )
                self.driver.switch_to.frame(iframe)
                
                # Sometime there's a nested iframe
                try:
                    nested_iframe = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "iframe[title*='Indeed Apply']"))
                    )
                    self.driver.switch_to.frame(nested_iframe)
                except TimeoutException:
                    pass
            except TimeoutException:
                pass # Pudo haber abierto una nueva ventana sin iframe

            # Bucle de postulación (llenar formulario y pulsar Continuar)
            max_steps = 10
            step = 0
            while step < max_steps:
                step += 1
                get_random_delay(2, 4)
                if not self._wait_for_manual_captcha_resolution(timeout_seconds=180):
                    return False
                
                # Verificar si ya terminamos
                if "Tu postulación ha sido enviada" in self.driver.page_source or "Your application has been submitted" in self.driver.page_source:
                    print(f"[{self.sitio}] ¡Postulación exitosa detectada!")
                    break

                # 1. Identificar preguntas en la pantalla
                labels = self.driver.find_elements(By.CSS_SELECTOR, "label.ia-Questions-label")
                for label in labels:
                    pregunta_texto = label.text
                    print(f"[{self.sitio}] Pregunta detectada: {pregunta_texto}")
                    
                    # Buscar el input/select relacionado
                    input_id = label.get_attribute("for")
                    if input_id:
                        try:
                            elemento = self.driver.find_element(By.ID, input_id)
                            tag_name = elemento.tag_name
                            
                            if tag_name in ["input", "textarea"]:
                                input_type = elemento.get_attribute("type")
                                if input_type in ["text", "number", "tel"] or tag_name == "textarea":
                                    if not elemento.get_attribute("value"): # Solo llenar si está vacío
                                        respuesta = answer_indeed_question(pregunta_texto, [], self.user_profile, self.api_key)
                                        elemento.clear()
                                        elemento.send_keys(respuesta)
                            
                            elif tag_name == "select":
                                from selenium.webdriver.support.ui import Select
                                select = Select(elemento)
                                options = [opt.text for opt in select.options if opt.text.strip()]
                                respuesta = answer_indeed_question(pregunta_texto, options, self.user_profile, self.api_key)
                                try:
                                    select.select_by_visible_text(respuesta)
                                except:
                                    pass # Si falla, dejar el predeterminado
                                    
                        except Exception as e:
                            print(f"[{self.sitio}] Warning procesando input: {e}")

                # 2. Manejar Radio buttons / Checkboxes (suelen tener una estructura diferente)
                fieldset_legends = self.driver.find_elements(By.CSS_SELECTOR, "legend.ia-Questions-legend")
                for legend in fieldset_legends:
                    pregunta_texto = legend.text
                    print(f"[{self.sitio}] Pregunta (opciones) detectada: {pregunta_texto}")
                    # Para mantenerlo simple, seleccionaremos el primer radio/checkbox
                    # En una versión más robusta, usaríamos Gemini aquí también para elegir la mejor opción
                    try:
                        radios = legend.find_elements(By.XPATH, "..//input[@type='radio' or @type='checkbox']")
                        if radios:
                            if not any(r.is_selected() for r in radios):
                                self.driver.execute_script("arguments[0].click();", radios[0])
                    except:
                        pass
                
                # 3. Subir CV si lo pide explícitamente en este paso y no seleccionó el guardado
                try:
                    cv_input = self.driver.find_element(By.CSS_SELECTOR, "input[type='file']")
                    cv_input.send_keys(cv_path)
                except NoSuchElementException:
                    pass

                # 4. Pulsar Continuar o Enviar
                avanzado = False
                botones_xpath = [
                    "//button[contains(@class, 'ia-continueButton')]",
                    "//button[contains(span/text(), 'Continuar') or contains(span/text(), 'Continue')]",
                    "//button[contains(span/text(), 'Enviar postulación') or contains(span/text(), 'Submit')]"
                ]
                
                for xpath in botones_xpath:
                    try:
                        btn = self.driver.find_element(By.XPATH, xpath)
                        self.driver.execute_script("arguments[0].click();", btn)
                        avanzado = True
                        if 'Enviar' in xpath or 'Submit' in xpath:
                            get_random_delay(4, 6)
                            print(f"[{self.sitio}] Postulación enviada con éxito.")
                            step = max_steps # Forzar salida del bucle
                        break # Salir del for porque ya cliqueó
                    except NoSuchElementException:
                        continue
                        
                if not avanzado:
                    print(f"[{self.sitio}] No se encontró botón para avanzar. El formulario podría ser incompatible. Saliendo del flujo de postulación.")
                    break
                        
            # Volver a la ventana principal y restaurar contexto
            self.driver.switch_to.window(original_window)
            return True
            
        except TimeoutException:
            print(f"[{self.sitio}] Botón de Postulación Rápida no disponible o ya te postulaste.")
            return False
        finally:
            self.driver.switch_to.default_content()

