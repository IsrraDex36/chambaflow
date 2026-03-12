import time
import random
import csv
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

try:
    from fake_useragent import UserAgent
except Exception:
    UserAgent = None

def get_random_delay(min_s=3, max_s=10):
    time.sleep(random.uniform(min_s, max_s))

def setup_driver(
    headless=True,
    session_dir="session_data",
    rotate_user_agent=False,
    stealth_mode=False,
    browser="chrome",
    debugger_address=""
):
    options = Options()
    if debugger_address:
        options.add_experimental_option("debuggerAddress", debugger_address)
        print(f"Conectando a navegador existente en {debugger_address}")
    
    # Selección de navegador (por defecto: Chrome)
    browser = (browser or "chrome").strip().lower()
    if browser == "brave":
        brave_path = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
        if not os.path.exists(brave_path):
            brave_path = os.path.join(os.environ.get("LOCALAPPDATA", ""), r"BraveSoftware\Brave-Browser\Application\brave.exe")
        if os.path.exists(brave_path):
            options.binary_location = brave_path
            print("Usando navegador: Brave")
        else:
            print("Brave no encontrado, usando Chrome por defecto.")
    else:
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Google\Chrome\Application\chrome.exe"),
        ]
        chrome_path = next((p for p in chrome_paths if os.path.exists(p)), "")
        if chrome_path:
            options.binary_location = chrome_path
        print("Usando navegador: Chrome")

    if rotate_user_agent and UserAgent is not None:
        try:
            ua = UserAgent()
            options.add_argument(f"user-agent={ua.random}")
        except Exception:
            print("No se pudo rotar User-Agent, se usará el del navegador.")
    if headless:
        options.add_argument("--headless=new")
    # Flags de estabilidad para evitar fallos de arranque con perfiles persistentes.
    options.add_argument("--remote-debugging-port=0")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    
    # Estas opciones pueden ayudar en algunos casos, pero también elevar captchas.
    # Por estabilidad de sesión, quedan desactivadas por defecto.
    if stealth_mode:
        options.add_argument("--disable-blink-features=AutomationControlled")
    
    if session_dir and not debugger_address:
        os.makedirs(session_dir, exist_ok=True)
        options.add_argument(f"--user-data-dir={os.path.abspath(session_dir)}")
    
    try:
        # Selenium Manager (integrado) suele resolver mejor las versiones del navegador.
        driver = webdriver.Chrome(options=options)
    except Exception:
        # Fallback al flujo anterior si Selenium Manager falla por entorno.
        service = ChromeService(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    
    if stealth_mode:
        # execute cdp command to hide WebDriver
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })
    return driver

def log_postulacion(csv_path, sitio, vacante, empresa, status):
    file_exists = os.path.isfile(csv_path)
    with open(csv_path, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['Fecha', 'Sitio', 'Vacante', 'Empresa', 'Status'])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), sitio, vacante, empresa, status])

def take_screenshot(driver, name_prefix="error"):
    os.makedirs("screenshots", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"screenshots/{name_prefix}_{timestamp}.png"
    driver.save_screenshot(path)
    return path
