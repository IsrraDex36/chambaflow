import argparse
import yaml
import os
import urllib.request
import urllib.error
from utils import setup_driver, log_postulacion
from cv_bot_occ import BotOCC
from cv_bot_indeed import BotIndeed

def load_config(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def debugger_is_available(debugger_address):
    if not debugger_address:
        return True
    try:
        urllib.request.urlopen(f"http://{debugger_address}/json/version", timeout=2)
        return True
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False

def main():
    parser = argparse.ArgumentParser(description="Bot de Postulación de Empleos Headless")
    parser.add_argument('--config', default='config.yaml', help='Ruta al archivo de configuración')
    parser.add_argument('--dry-run', action='store_true', help='Ejecutar sin hacer postulaciones reales')
    args = parser.parse_args()

    config = load_config(args.config)
    keywords = config.get('keywords', [])
    sitios = config.get('sitios', [])
    cv_path = os.path.abspath(config.get('cv_path', 'tu_cv.pdf'))
    max_dia = config.get('max_postulaciones_dia', 10)
    session_dir = config.get('session_dir', '')
    rotate_user_agent = config.get('rotate_user_agent', False)
    stealth_mode = config.get('stealth_mode', False)
    browser = config.get('browser', 'chrome')
    debugger_address = config.get('debugger_address', '')
    controlled_mode = config.get('controlled_mode', True)
    occ_max_scan_per_keyword = config.get('occ_max_scan_per_keyword', 6)
    if not session_dir:
        session_dir = "session_data_chrome" if str(browser).lower() == "chrome" else "session_data_brave"
    
    print(f"Iniciando bot... Dry run: {args.dry_run}")
    
    if not os.path.exists(cv_path):
        with open(cv_path, 'w') as f:
            f.write("Fake CV content")

    # Regla operativa: primero navegador, después bot.
    if debugger_address and not debugger_is_available(debugger_address):
        print(f"Error: no se detectó navegador en {debugger_address}.")
        print("Primero abre Brave/Chrome en modo depuración y luego ejecuta el bot.")
        return
            
    # Para Indeed, necesitamos ver la pantalla para el login o los captchas
    driver = setup_driver(
        headless=False,
        session_dir=session_dir,
        rotate_user_agent=rotate_user_agent,
        stealth_mode=stealth_mode,
        browser=browser,
        debugger_address=debugger_address
    )
    
    try:
        bots = []
        if 'occ' in sitios:
            occ_filter = config.get('occ_filter', {})
            bots.append(
                BotOCC(
                    driver,
                    dry_run=args.dry_run,
                    controlled_mode=controlled_mode,
                    max_scan_per_keyword=occ_max_scan_per_keyword,
                    filter_config=occ_filter,
                )
            )
        if 'indeed' in sitios:
            api_key = config.get('gemini_api_key', '')
            user_profile = config.get('user_profile', '')
            bots.append(BotIndeed(driver, dry_run=args.dry_run, api_key=api_key, user_profile=user_profile))
            
        csv_log = "postulaciones.csv"
        total_aplicaciones = 0
        
        for bot in bots:
            for keyword in keywords:
                if total_aplicaciones >= max_dia:
                    print("Límite diario alcanzado.")
                    break
                apps = bot.search_and_apply(keyword, cv_path, max_dia - total_aplicaciones)
                total_aplicaciones += apps
                
                if args.dry_run and apps > 0:
                    for i in range(apps):
                        log_postulacion(csv_log, bot.sitio, f"Vacante Simulada {keyword} #{i+1}", "Empresa Test SA", "Simulado (Dry Run)")
                
    finally:
        driver.quit()
        print("Driver cerrado.")

if __name__ == "__main__":
    main()
