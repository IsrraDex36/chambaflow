import argparse
import yaml
import os
import urllib.request
import urllib.error
from datetime import datetime

from utils import setup_driver, log_postulacion
from search_session import (
    normalize_keywords,
    rotate_keyword_list,
    load_run_state,
    save_run_state,
    count_postulaciones_hoy,
)
from cv_bot_occ import BotOCC
from cv_bot_computrabajo import BotComputrabajo
from cv_bot_indeed import BotIndeed

SITIOS_DISPONIBLES = ["occ", "computrabajo", "indeed"]


def load_config(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def choose_sitios_interactive():
    """
    Menú en consola minimalista:
    - Lista simple de sitios disponibles.
    - ESPACIO para marcar/desmarcar, ENTER para confirmar.
    Devuelve lista de sitios elegidos o None para usar config.yaml.
    """
    try:
        import questionary
        # Presentación neutra y simple en texto plano
        print()
        print("────────────────────────")
        print(" Sitios disponibles")
        print("────────────────────────")
        for idx, s in enumerate(SITIOS_DISPONIBLES, start=1):
            print(f"  [{idx}] {s}")
        print()
        print("Selecciona uno o más sitios.")
        print("Espacio = marcar/desmarcar · Enter = confirmar")

        choices = [
            questionary.Choice(title=f"  {s}", value=s)
            for s in SITIOS_DISPONIBLES
        ]
        seleccion = questionary.checkbox(
            "  ¿Qué sitio(s) quieres ejecutar?",
            choices=choices,
            instruction="  ",
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
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        from rich.align import Align

        console = Console()
        # Banner ASCII personalizado
        ascii_banner = (
            "██████╗██╗  ██╗ █████╗ ███╗   ███╗██████╗  █████╗ ███████╗██╗      ██████╗ ██╗    ██╗\n"
            "██╔════╝██║  ██║██╔══██╗████╗ ████║██╔══██╗██╔══██╗██╔════╝██║     ██╔═══██╗██║    ██║\n"
            "██║     ███████║███████║██╔████╔██║██████╔╝███████║█████╗  ██║     ██║   ██║██║ █╗ ██║\n"
            "██║     ██╔══██║██╔══██║██║╚██╔╝██║██╔══██╗██╔══██║██╔══╝  ██║     ██║   ██║██║███╗██║\n"
            "╚██████╗██║  ██║██║  ██║██║ ╚═╝ ██║██████╔╝██║  ██║██║     ███████╗╚██████╔╝╚███╔███╔╝\n"
            " ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝ "
        )

        content = Text(ascii_banner, style="bold white")
        content.append("\n\n")
        content.append("Bot de Postulación Automática", style="bold white")

        panel = Panel(
            Align.center(content),
            border_style="white",
            padding=(1, 2),
            title="[bold white]Bienvenido[/bold white]",
            subtitle="[bold white]v1.0[/bold white]"
        )
        console.print(panel)
        print()
    except ImportError:
        pass
        
    parser = argparse.ArgumentParser(description="Bot de Postulación de Empleos Headless")
    parser.add_argument('--config', default='config.yaml', help='Ruta al archivo de configuración')
    parser.add_argument('--dry-run', action='store_true', help='Ejecutar sin hacer postulaciones reales')
    parser.add_argument('--sitios', type=str, metavar='LISTA',
                        help='Sitios a ejecutar (sin menú), ej: occ,computrabajo')
    args = parser.parse_args()

    config = load_config(args.config)
    keywords = normalize_keywords(config.get('keywords', []))
    sitios = config.get('sitios', [])

    daily_cfg = config.get('daily_quota') or {}
    count_from_csv = bool(daily_cfg.get('count_from_csv', False))
    count_simulated_for_quota = bool(daily_cfg.get('count_simulated_for_quota', False))
    csv_log = config.get('postulaciones_csv') or daily_cfg.get('csv_path', 'postulaciones.csv')

    search_cfg = config.get('search') or {}
    rotate_keywords = bool(search_cfg.get('rotate_keywords', True))
    state_file = (search_cfg.get('state_file') or 'chambaflow_state.yaml').strip()
    reset_rotation_daily = bool(search_cfg.get('reset_keyword_rotation_daily', False))

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
    max_dia_cfg = int(config.get('max_postulaciones_dia', 10))

    used_today = 0
    if count_from_csv:
        used_today = count_postulaciones_hoy(
            csv_log, count_simulated=count_simulated_for_quota
        )
    remaining_quota = max(0, max_dia_cfg - used_today)

    if count_from_csv:
        print(
            f"Cuota diaria (CSV): {used_today}/{max_dia_cfg} hoy · "
            f"restantes en esta sesión: {remaining_quota}"
        )

    run_state: dict = {}
    keyword_offset = 0
    today_str = datetime.now().strftime('%Y-%m-%d')
    if rotate_keywords and state_file and keywords:
        run_state = load_run_state(state_file)
        keyword_offset = int(run_state.get('keyword_offset', 0))
        if reset_rotation_daily and run_state.get('rotation_date') != today_str:
            keyword_offset = 0
            run_state['keyword_offset'] = 0
        run_state['rotation_date'] = today_str
    session_dir = config.get('session_dir', '')
    rotate_user_agent = config.get('rotate_user_agent', False)
    stealth_mode = config.get('stealth_mode', False)
    browser = config.get('browser', 'chrome')
    debugger_address = config.get('debugger_address', '')
    controlled_mode = config.get('controlled_mode', True)
    occ_max_scan_per_keyword = config.get('occ_max_scan_per_keyword', 6)
    occ_modal_cfg = config.get('occ_modal') or {}
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
                    postulaciones_csv=csv_log,
                    modal_config=occ_modal_cfg,
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
                    postulaciones_csv=csv_log,
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
                    postulaciones_csv=csv_log,
                )
            )
        total_aplicaciones = 0
        if keywords and rotate_keywords:
            kw_list = rotate_keyword_list(keywords, keyword_offset)
        else:
            kw_list = list(keywords)
        keyword_slots = 0

        if rotate_keywords and keywords:
            print(f"Búsquedas en orden (rotación offset={keyword_offset}): {', '.join(kw_list)}")

        for bot in bots:
            for keyword in kw_list:
                if remaining_quota <= 0 or total_aplicaciones >= remaining_quota:
                    if remaining_quota <= 0:
                        print("Límite diario alcanzado (cuota restante = 0).")
                    break
                keyword_slots += 1
                apps = bot.search_and_apply(
                    keyword, cv_path, remaining_quota - total_aplicaciones
                )
                total_aplicaciones += apps

                if args.dry_run and apps > 0:
                    for i in range(apps):
                        log_postulacion(
                            csv_log,
                            bot.sitio,
                            f"Vacante Simulada {keyword} #{i+1}",
                            "Empresa Test SA",
                            "Simulado (Dry Run)",
                        )
            if remaining_quota <= 0 or total_aplicaciones >= remaining_quota:
                break

        if rotate_keywords and keywords and state_file:
            new_offset = (keyword_offset + keyword_slots) % len(keywords)
            run_state['keyword_offset'] = new_offset
            if reset_rotation_daily:
                run_state['rotation_date'] = today_str
            save_run_state(state_file, run_state)
            if keyword_slots > 0:
                print(f"Rotación guardada: próximo inicio en offset {new_offset}.")
                
    finally:
        driver.quit()
        print("Driver cerrado.")

if __name__ == "__main__":
    main()
