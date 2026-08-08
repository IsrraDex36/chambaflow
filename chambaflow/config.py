import os
import shutil
import sys

import yaml

if getattr(sys, "frozen", False):
    # Ejecutable de PyInstaller (--onefile): __file__ no apunta a un archivo
    # real en disco. sys._MEIPASS es el directorio temporal donde se
    # descomprimen los datos embebidos vía `datas=` en chambaflow.spec
    # (ver docs/BUILD.md) en cada arranque.
    _PROJECT_ROOT = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    # chambaflow/config.py -> chambaflow/ -> raíz del proyecto
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_TEMPLATE_PATH = os.path.join(_PROJECT_ROOT, "config", "config.example.yaml")


def ensure_config_exists(config_path, template_path=None):
    """
    Si config_path no existe, lo crea copiando la plantilla
    config/config.example.yaml y avisa en consola. No hace nada (ni pisa
    nada) si config_path ya existe. Devuelve True si tuvo que crearlo.
    """
    if os.path.isfile(config_path):
        return False
    template_path = template_path or DEFAULT_TEMPLATE_PATH
    if not os.path.isfile(template_path):
        return False
    shutil.copyfile(template_path, config_path)
    print(
        f"No existía '{config_path}'; se creó copiando la plantilla "
        f"'{template_path}'. Ábrelo y ajusta tus datos antes de correr el bot."
    )
    return True


def load_config(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)
