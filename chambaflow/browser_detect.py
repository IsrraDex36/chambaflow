"""
Detección de sistema operativo y navegadores instalados (Brave/Chrome).

Antes vivía disperso e incompleto dentro de driver.setup_driver(): sin ruta
de Chrome en mac y sin ninguna ruta Linux. Aquí queda centralizado para que
setup_driver() y la pantalla de bienvenida (chambaflow/cli.py) usen la misma
fuente de verdad.
"""
from __future__ import annotations

import os
import platform
from typing import Optional


def detect_os() -> str:
    system = platform.system()
    return {"Darwin": "macOS", "Windows": "Windows", "Linux": "Linux"}.get(system, system)


def _candidates(browser: str) -> list[str]:
    os_name = detect_os()
    local_appdata = os.environ.get("LOCALAPPDATA", "")

    paths: dict[str, dict[str, list[str]]] = {
        "brave": {
            "macOS": [
                "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            ],
            "Windows": [
                r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                os.path.join(local_appdata, r"BraveSoftware\Brave-Browser\Application\brave.exe"),
            ],
            "Linux": [
                "/usr/bin/brave-browser",
                "/usr/bin/brave",
            ],
        },
        "chrome": {
            "macOS": [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            ],
            "Windows": [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.join(local_appdata, r"Google\Chrome\Application\chrome.exe"),
            ],
            "Linux": [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/chromium-browser",
            ],
        },
    }
    return paths.get(browser, {}).get(os_name, [])


def find_browser_path(browser: str) -> Optional[str]:
    browser = (browser or "").strip().lower()
    return next((p for p in _candidates(browser) if p and os.path.exists(p)), None)


def detect_available_browsers() -> dict[str, Optional[str]]:
    return {"brave": find_browser_path("brave"), "chrome": find_browser_path("chrome")}
