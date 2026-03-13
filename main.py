import argparse
import yaml
import os
import urllib.request
import urllib.error
from utils import setup_driver, log_postulacion
from cv_bot_occ import BotOCC
from cv_bot_computrabajo import BotComputrabajo
from cv_bot_indeed import BotIndeed

SITIOS_DISPONIBLES = ["occ", "computrabajo", "indeed"]


def load_config(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def choose_sitios_interactive():
    """
    Menú en consola: ESPACIO para marcar/desmarcar, ENTER para confirmar.
    Devuelve lista de sitios elegidos o None para usar config.yaml.
    """
    try:
        import questionary
        choices = [
            questionary.Choice(title=f"  {s}", value=s)
            for s in SITIOS_DISPONIBLES
        ]
        print()
        print("  ¿Qué sitio(s) ejecutar? (Espacio = marcar, Enter = confirmar)")
        print()
        seleccion = questionary.checkbox(
            "  Elige uno o más:",
            choices=choices,
            instruction="  Espacio: marcar/desmarcar · Enter: confirmar",
        ).ask()
        if seleccion is None:
            return None
        if not seleccion:
            print("  Nada seleccionado; se usará config.yaml.")
            return None
        return seleccion
    except ImportError:
        print("  Instala 'questionary' para el menú con Espacio/Enter: pip install questionary")
        print("  Usando config.yaml.")
        return None
    except (KeyboardInterrupt, EOFError):
        print()
        return None


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
    parser.add_argument('--sitios', type=str, metavar='LISTA',
                        help='Sitios a ejecutar (sin menú), ej: occ,computrabajo')
    args = parser.parse_args()

    config = load_config(args.config)
    keywords = config.get('keywords', [])
    sitios = config.get('sitios', [])

    if args.sitios:
        sitios = [s.strip().lower() for s in args.sitios.split(",") if s.strip()]
        sitios = [s for s in sitios if s in SITIOS_DISPONIBLES]
        if not sitios:
            print("Ningún sitio válido en --sitios; usando config.yaml.")
            sitios = config.get('sitios', [])
    else:
        elegidos = choose_sitios_interactive()
        if elegidos is not None:
            sitios = elegidos
            print(f"  → Ejecutando: {', '.join(sitios)}")
        print()
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
        if 'computrabajo' in sitios:
            ct_filter = config.get('computrabajo_filter', config.get('occ_filter', {}))
            bots.append(
                BotComputrabajo(
                    driver,
                    dry_run=args.dry_run,
                    controlled_mode=controlled_mode,
                    max_scan_per_keyword=occ_max_scan_per_keyword,
                    filter_config=ct_filter,
                )
            )
        if 'indeed' in sitios:
            indeed_filter = config.get('indeed_filter', config.get('occ_filter', {}))
            bots.append(
                BotIndeed(
                    driver,
                    dry_run=args.dry_run,
                    controlled_mode=controlled_mode,
                    max_scan_per_keyword=occ_max_scan_per_keyword,
                    filter_config=indeed_filter,
                )
            )
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
