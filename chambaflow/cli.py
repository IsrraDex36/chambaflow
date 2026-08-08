import csv
import enum
import os
import random
import subprocess
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import List, Optional

import typer

from chambaflow.driver import setup_driver, log_postulacion, cleanup_old_screenshots
from chambaflow.config import load_config, ensure_config_exists
from chambaflow.browser_detect import detect_os, detect_available_browsers
from chambaflow.state import (
    normalize_keywords,
    rotate_keyword_list,
    load_run_state,
    save_run_state,
    count_postulaciones_hoy,
)
from chambaflow.bots.occ import BotOCC
from chambaflow.bots.computrabajo import BotComputrabajo
from chambaflow.bots.indeed import BotIndeed

SITIOS_DISPONIBLES = ["occ", "computrabajo", "indeed"]


class Sitio(str, enum.Enum):
    occ = "occ"
    computrabajo = "computrabajo"
    indeed = "indeed"


app = typer.Typer(
    add_completion=False,
    help="ChambaFlow — bot de postulación automática de empleos (OCC, Computrabajo, Indeed).",
)
config_app = typer.Typer(add_completion=False, help="Ver o editar config.yaml.")
app.add_typer(config_app, name="config")

# Caracteres de estrella para el fondo del banner. Ponderados hacia "." para
# que se vea disperso; blancas siempre (no azules) por pedido explícito.
_STAR_CHARS = [".", ".", ".", "·", "*"]


def _starfield_line(width, density):
    return "".join(
        random.choice(_STAR_CHARS) if random.random() < density else " "
        for _ in range(width)
    )


def _render_on_starfield(lines, density=0.10, pad_top=0, pad_bottom=0, min_width=0):
    """
    Dibuja `lines` (texto del wordmark, centrado) sobre un fondo real de
    estrellas blancas: filas en blanco arriba/abajo (pad_top/pad_bottom) y
    relleno lateral si min_width > ancho del texto, todo cubierto de estrellas
    salvo donde cae un carácter del wordmark. Devuelve un rich.text.Text ya
    coloreado: wordmark en blanco brillante, estrellas en blanco tenue.
    """
    from rich.text import Text

    width = max(min_width, max(len(line) for line in lines))
    centered_lines = [line.center(width) for line in lines]
    blank = " " * width
    all_lines = [blank] * pad_top + centered_lines + [blank] * pad_bottom

    text = Text()
    for i, line in enumerate(all_lines):
        star_line = _starfield_line(width, density)
        for ch, star in zip(line, star_line):
            if ch != " ":
                text.append(ch, style="bold white")
            elif star != " ":
                text.append(star, style="dim white")
            else:
                text.append(" ")
        if i != len(all_lines) - 1:
            text.append("\n")
    return text, width


def choose_sitios_interactive():
    """
    Menú en consola minimalista:
    - Lista simple de sitios disponibles.
    - ESPACIO para marcar/desmarcar, ENTER para confirmar.
    Devuelve lista de sitios elegidos o None para usar config.yaml.
    """
    try:
        import questionary
        print()
        print("────────────────────────")
        print(" Sitios disponibles")
        print("────────────────────────")
        print("Espacio = marcar/desmarcar · Enter = confirmar")
        print("Si no marcas ninguno o cancelas (Ctrl+C), se usa la lista 'sitios' de config.yaml.")
        print()

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

def run_once(config_path, sitios_override=None, dry_run=False, keyword_override=None):
    config = load_config(config_path)
    keywords = normalize_keywords(config.get('keywords', []))
    sitios = sitios_override if sitios_override is not None else config.get('sitios', [])

    daily_cfg = config.get('daily_quota') or {}
    count_from_csv = bool(daily_cfg.get('count_from_csv', False))
    count_simulated_for_quota = bool(daily_cfg.get('count_simulated_for_quota', False))
    unlimited_daily = bool(daily_cfg.get('unlimited', False))
    csv_log = config.get('postulaciones_csv') or daily_cfg.get('csv_path', 'postulaciones.csv')

    search_cfg = config.get('search') or {}
    rotate_keywords = bool(search_cfg.get('rotate_keywords', True))
    state_file = (search_cfg.get('state_file') or 'chambaflow_state.yaml').strip()
    if state_file and not os.path.isabs(state_file):
        state_file = os.path.join(os.path.dirname(config_path), state_file)
    reset_rotation_daily = bool(search_cfg.get('reset_keyword_rotation_daily', False))

    cv_path = os.path.abspath(config.get('cv_path', 'tu_cv.pdf'))
    max_dia_cfg = int(config.get('max_postulaciones_dia', 10))

    used_today = 0
    if count_from_csv and not unlimited_daily:
        used_today = count_postulaciones_hoy(
            csv_log, count_simulated=count_simulated_for_quota
        )
    if unlimited_daily:
        remaining_quota = 10**9
        print("Cuota diaria: desactivada (sin límite por sesión).")
    else:
        remaining_quota = max(0, max_dia_cfg - used_today)
        if count_from_csv:
            print(
                f"Cuota diaria (CSV): {used_today}/{max_dia_cfg} hoy · "
                f"restantes en esta sesión: {remaining_quota}"
            )

    run_state: dict = {}
    keyword_offset = 0
    today_str = datetime.now().strftime('%Y-%m-%d')
    if state_file:
        run_state = load_run_state(state_file)
    if rotate_keywords and state_file and keywords:
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

    print(f"Iniciando bot... Dry run: {dry_run}")

    screenshots_retention_days = int(config.get('screenshots_retention_days', 30))
    removed = cleanup_old_screenshots(max_age_days=screenshots_retention_days)
    if removed:
        print(f"Limpieza: {removed} captura(s) de más de {screenshots_retention_days} días borrada(s) de screenshots/.")

    if not os.path.exists(cv_path):
        print(
            f"⚠ No se encontró el CV en '{cv_path}' (clave 'cv_path' en config.yaml). "
            f"El paso de subir CV va a fallar en cada postulación real."
        )

    if debugger_address and not debugger_is_available(debugger_address):
        print(f"Error: no se detectó navegador en {debugger_address}.")
        print("Primero abre Brave/Chrome en modo depuración y luego ejecuta el bot.")
        return

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
                    dry_run=dry_run,
                    controlled_mode=controlled_mode,
                    max_scan_per_keyword=occ_max_scan_per_keyword,
                    filter_config=occ_filter,
                    postulaciones_csv=csv_log,
                    modal_config=occ_modal_cfg,
                    state=run_state,
                )
            )
        if 'computrabajo' in sitios:
            ct_filter = config.get('computrabajo_filter', config.get('occ_filter', {}))
            bots.append(
                BotComputrabajo(
                    driver,
                    dry_run=dry_run,
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
                    dry_run=dry_run,
                    controlled_mode=controlled_mode,
                    max_scan_per_keyword=occ_max_scan_per_keyword,
                    filter_config=indeed_filter,
                    postulaciones_csv=csv_log,
                )
            )

        total_aplicaciones = 0
        if keyword_override:
            kw_list = [keyword_override]
        elif keywords and rotate_keywords:
            kw_list = rotate_keyword_list(keywords, keyword_offset)
        else:
            kw_list = list(keywords)
        keyword_slots = 0

        if keyword_override:
            print(f"Búsqueda forzada por --keyword: {keyword_override}")
        elif rotate_keywords and keywords:
            print(f"Búsquedas en orden (rotación offset={keyword_offset}): {', '.join(kw_list)}")

        for bot in bots:
            logged_in = bot.is_logged_in()
            if logged_in is False:
                print(
                    f"[{bot.sitio}] No hay sesión iniciada en {bot.sitio}. "
                    f"Abre esa pestaña, inicia sesión manualmente y vuelve a correr el bot. "
                    f"Saltando {bot.sitio}."
                )
                continue
            if logged_in is None:
                print(f"[{bot.sitio}] No se pudo confirmar si hay sesión iniciada; continuando de todas formas.")

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

                if dry_run and apps > 0:
                    for i in range(apps):
                        log_postulacion(
                            csv_log,
                            bot.sitio,
                            f"Vacante Simulada {keyword} #{i+1}",
                            "Empresa Test SA",
                            "Simulado",
                            keyword=keyword,
                        )
            if remaining_quota <= 0 or total_aplicaciones >= remaining_quota:
                break

        if state_file:
            if rotate_keywords and keywords and not keyword_override:
                new_offset = (keyword_offset + keyword_slots) % len(keywords)
                run_state['keyword_offset'] = new_offset
                if reset_rotation_daily:
                    run_state['rotation_date'] = today_str
                if keyword_slots > 0:
                    print(f"Rotación guardada: próximo inicio en offset {new_offset}.")
            save_run_state(state_file, run_state)

    finally:
        driver.quit()
        print("Driver cerrado.")


def print_welcome_banner():
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.align import Align

        console = Console()
        ascii_banner = (
            "██████╗██╗  ██╗ █████╗ ███╗   ███╗██████╗  █████╗ ███████╗██╗      ██████╗ ██╗    ██╗\n"
            "██╔════╝██║  ██║██╔══██╗████╗ ████║██╔══██╗██╔══██╗██╔════╝██║     ██╔═══██╗██║    ██║\n"
            "██║     ███████║███████║██╔████╔██║██████╔╝███████║█████╗  ██║     ██║   ██║██║ █╗ ██║\n"
            "██║     ██╔══██║██╔══██║██║╚██╔╝██║██╔══██╗██╔══██║██╔══╝  ██║     ██║   ██║██║███╗██║\n"
            "╚██████╗██║  ██║██║  ██║██║ ╚═╝ ██║██████╔╝██║  ██║██║     ███████╗╚██████╔╝╚███╔███╔╝\n"
            " ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝     ╚══════╝ ╚═════╝  ╚══╝╚══╝ "
        )
        wordmark_lines = ascii_banner.split("\n")
        wordmark_width = max(len(line) for line in wordmark_lines)

        # El wordmark ASCII (86 cols) no cabe en terminales angostas (ej. 80
        # cols, default en muchas consolas Windows) — se rompe carácter por
        # carácter. Si no cabe, se usa el título corto (también con estrellas).
        available = max(20, console.size.width - 8)  # -8: bordes + padding del Panel

        if available >= wordmark_width:
            content, _ = _render_on_starfield(wordmark_lines, density=0.08, pad_top=1, pad_bottom=1)
        else:
            compact_width = min(available, 34)
            content, _ = _render_on_starfield(
                ["ChambaFlow"], density=0.16, pad_top=1, pad_bottom=1, min_width=compact_width
            )

        content.append("\n\n")
        content.append("Bot de Postulación Automática", style="bold white")
        content.append("\n")
        content.append("OCC · Computrabajo · Indeed", style="dim white")

        panel = Panel(
            Align.center(content),
            border_style="white",
            padding=(1, 2),
            title="[bold white]Bienvenido[/bold white]",
            subtitle="[bold white]v2.0[/bold white]"
        )
        console.print(panel)
        print()
    except ImportError:
        pass


def print_browser_status(config):
    os_name = detect_os()
    found = detect_available_browsers()
    browser_cfg = str(config.get('browser', 'chrome')).strip().lower()

    parts = [f"{name.capitalize()} {'✓' if path else '✗'}" for name, path in found.items()]
    line = f"Sistema: {os_name}  |  Navegadores detectados: {', '.join(parts)}"

    try:
        from rich.console import Console
        console = Console()
        console.print(line, style="dim")
        if not found.get(browser_cfg):
            console.print(
                f"⚠ config.yaml pide browser: \"{browser_cfg}\" pero no se encontró en este equipo "
                f"(revisa 'browser' en config.yaml, o usa 'debugger_address' con un navegador ya abierto).",
                style="yellow",
            )
    except ImportError:
        print(line)
    print()


def _last_csv_row(csv_path):
    if not csv_path or not os.path.isfile(csv_path):
        return None
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return rows[-1] if rows else None


@app.command()
def run(
    config: str = typer.Option("config.yaml", "--config", help="Ruta al archivo de configuración."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Simula sin postular real (loguea 'Simulado' en el CSV)."),
    sitio: Optional[List[Sitio]] = typer.Option(
        None, "--sitio", help="Sitio a ejecutar (repetible: --sitio occ --sitio indeed). "
                              "Si se omite: menú interactivo, o la lista 'sitios' de config.yaml."
    ),
    keyword: Optional[str] = typer.Option(
        None, "--keyword", help="Si se da, busca solo este texto (ignora la rotación de keywords de config.yaml)."
    ),
):
    """Ejecuta el bot: busca y postula en los sitios configurados."""
    config_path = os.path.abspath(config)
    ensure_config_exists(config_path)
    cfg = load_config(config_path)

    print_welcome_banner()
    print_browser_status(cfg)

    sitios_override = None
    if sitio:
        sitios_override = [s.value for s in sitio]
    else:
        elegidos = choose_sitios_interactive()
        if elegidos is not None:
            sitios_override = elegidos
            print(f"  → Ejecutando: {', '.join(sitios_override)}")
        print()

    scheduler_cfg = cfg.get('scheduler') or {}
    scheduler_enabled = bool(scheduler_cfg.get('enabled', False))

    if not scheduler_enabled:
        run_once(config_path, sitios_override, dry_run=dry_run, keyword_override=keyword)
        return

    start_hour = int(scheduler_cfg.get('start_hour', 7))
    end_hour = int(scheduler_cfg.get('end_hour', 23))
    pause_min = int(scheduler_cfg.get('pause_between_runs_min', 20))

    print(f"Scheduler activo: {start_hour:02d}:00 → {end_hour:02d}:00, pausa {pause_min} min entre ejecuciones.")
    print("Ctrl+C para detener.")

    run_number = 0
    try:
        while True:
            now = datetime.now()
            if start_hour <= now.hour < end_hour:
                run_number += 1
                print(f"\n{'='*60}")
                print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] Ejecución #{run_number}")
                print(f"{'='*60}")
                try:
                    run_once(config_path, sitios_override, dry_run=dry_run, keyword_override=keyword)
                except Exception as e:
                    print(f"Error en ejecución #{run_number}: {e}")

                next_run = datetime.now() + timedelta(minutes=pause_min)
                print(f"\nPausa {pause_min} min. Próxima ejecución: {next_run.strftime('%H:%M:%S')}")
                time.sleep(pause_min * 60)
            else:
                if now.hour >= end_hour:
                    next_start = (now + timedelta(days=1)).replace(
                        hour=start_hour, minute=0, second=0, microsecond=0
                    )
                else:
                    next_start = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
                wait_sec = (next_start - now).total_seconds()
                print(f"[{now.strftime('%H:%M:%S')}] Fuera de horario. Esperando hasta {start_hour:02d}:00 ({wait_sec/3600:.1f}h).")
                time.sleep(min(wait_sec, 1800))
    except KeyboardInterrupt:
        print("\nScheduler detenido por el usuario.")


@app.command()
def status(
    config: str = typer.Option("config.yaml", "--config", help="Ruta al archivo de configuración."),
):
    """Muestra la cuota de postulaciones de hoy y la última registrada en el CSV."""
    config_path = os.path.abspath(config)
    ensure_config_exists(config_path)
    cfg = load_config(config_path)

    daily_cfg = cfg.get('daily_quota') or {}
    csv_log = cfg.get('postulaciones_csv') or daily_cfg.get('csv_path', 'postulaciones.csv')
    if not os.path.isabs(csv_log):
        csv_log = os.path.join(os.path.dirname(config_path), csv_log)
    max_dia = int(cfg.get('max_postulaciones_dia', 10))
    unlimited = bool(daily_cfg.get('unlimited', False))
    count_simulated = bool(daily_cfg.get('count_simulated_for_quota', False))

    if unlimited:
        print("Cuota diaria: desactivada (sin límite).")
    else:
        used_today = count_postulaciones_hoy(csv_log, count_simulated=count_simulated)
        print(f"Cuota diaria: {used_today}/{max_dia} hoy · restantes: {max(0, max_dia - used_today)}")

    last_row = _last_csv_row(csv_log)
    if last_row is None:
        print("Última postulación: (sin registros todavía en el CSV)")
    else:
        print(
            f"Última postulación: {last_row.get('Fecha')} {last_row.get('Hora')} · "
            f"{last_row.get('Sitio')} · {last_row.get('Keyword')} · "
            f"{last_row.get('Vacante')} ({last_row.get('Empresa')}) · {last_row.get('Status')}"
        )


@config_app.command("show")
def config_show(
    config: str = typer.Option("config.yaml", "--config", help="Ruta al archivo de configuración."),
):
    """Imprime el contenido de config.yaml."""
    config_path = os.path.abspath(config)
    ensure_config_exists(config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        content = f.read()
    try:
        from rich.console import Console
        from rich.syntax import Syntax
        Console().print(Syntax(content, "yaml", theme="ansi_dark", line_numbers=False))
    except ImportError:
        print(content)


@config_app.command("edit")
def config_edit(
    config: str = typer.Option("config.yaml", "--config", help="Ruta al archivo de configuración."),
):
    """Abre config.yaml en el editor de $EDITOR (o $VISUAL)."""
    config_path = os.path.abspath(config)
    ensure_config_exists(config_path)
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if not editor:
        typer.echo(
            "No hay $EDITOR (ni $VISUAL) configurado. "
            "Define la variable de entorno, ej. 'export EDITOR=vim', o edita el archivo a mano:"
        )
        typer.echo(config_path)
        raise typer.Exit(code=1)
    subprocess.run([editor, config_path])


def main():
    app()


if __name__ == "__main__":
    main()
