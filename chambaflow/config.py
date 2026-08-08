import os
import shutil

import yaml

# chambaflow/config.py -> chambaflow/ -> raíz del proyecto -> config/config.example.yaml
DEFAULT_TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config",
    "config.example.yaml",
)


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
