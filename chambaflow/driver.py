import time
import random
import csv
import os
import shutil
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from chambaflow.browser_detect import find_browser_path

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
        brave_path = find_browser_path("brave")
        if brave_path:
            options.binary_location = brave_path
            print("Usando navegador: Brave")
        elif not debugger_address:
            print("Brave no encontrado, usando Chrome por defecto.")
    else:
        chrome_path = find_browser_path("chrome")
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

CSV_HEADER = ['Fecha', 'Hora', 'Sitio', 'Keyword', 'Vacante', 'Empresa', 'Status']
_LEGACY_CSV_HEADER = ['Fecha', 'Sitio', 'Vacante', 'Empresa', 'Status']


def _migrate_legacy_csv(csv_path):
    """
    Formato viejo: una sola columna 'Fecha' con fecha+hora juntas y sin
    'Keyword'. Si el CSV existente tiene ese header exacto, lo reescribe al
    header actual (separa Fecha/Hora, agrega Keyword vacío en filas viejas)
    y deja un respaldo .bak antes de tocarlo. No hace nada si el header ya
    es el actual, es desconocido, o el archivo no existe.
    """
    if not os.path.isfile(csv_path):
        return
    with open(csv_path, newline='', encoding='utf-8') as f:
        rows = list(csv.reader(f))
    if not rows or rows[0] != _LEGACY_CSV_HEADER:
        return

    backup_path = csv_path + '.bak'
    if not os.path.isfile(backup_path):
        shutil.copyfile(csv_path, backup_path)

    migrated = [CSV_HEADER]
    for row in rows[1:]:
        if len(row) < 5:
            continue
        fecha_hora, sitio, vacante, empresa, status = row[:5]
        fecha, _, hora = fecha_hora.partition(' ')
        migrated.append([fecha, hora, sitio, '', vacante, empresa, status])

    tmp_path = csv_path + '.tmp'
    with open(tmp_path, mode='w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerows(migrated)
    os.replace(tmp_path, csv_path)


def log_postulacion(csv_path, sitio, vacante, empresa, status, keyword=""):
    _migrate_legacy_csv(csv_path)
    file_exists = os.path.isfile(csv_path)
    now = datetime.now()
    with open(csv_path, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(CSV_HEADER)
        writer.writerow([
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            sitio,
            keyword,
            vacante,
            empresa,
            status,
        ])

def take_screenshot(driver, name_prefix="error"):
    os.makedirs("screenshots", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"screenshots/{name_prefix}_{timestamp}.png"
    driver.save_screenshot(path)
    return path
