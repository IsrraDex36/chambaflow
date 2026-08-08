# Build standalone (PyInstaller)

Genera un ejecutable de un solo archivo para correr ChambaFlow sin Python/venv instalado — pensado para compartirlo o moverlo a otra máquina, **no** para reemplazar `pip install -e .` como vía de desarrollo.

## Generar el ejecutable

```bash
pip install -e ".[build]"   # agrega pyinstaller==6.22.0
pyinstaller chambaflow.spec
```

El binario queda en `dist/chambaflow` (`dist/chambaflow.exe` en Windows).

Usa siempre `chambaflow.spec`, no `pyinstaller --onefile chambaflow/cli.py` a secas — el `.spec` es lo que embebe `config/config.example.yaml` en el binario (ver gotcha 2 abajo). Si `chambaflow.spec` no existe, `pyinstaller --onefile --name chambaflow chambaflow/cli.py` lo autogenera, pero sin esa línea de `datas=`.

## Verificar que funciona

```bash
./dist/chambaflow --help
./dist/chambaflow status
./dist/chambaflow config show
```

Prueba real (la que importa): copiar el binario a una carpeta vacía, sin el repo alrededor, y correrlo ahí. Debe generar `config.yaml` desde la plantilla igual que el CLI instalado:

```bash
mkdir /tmp/chambaflow-test && cp dist/chambaflow /tmp/chambaflow-test/
cd /tmp/chambaflow-test && ./chambaflow config show
```

## Plataformas probadas

| SO | Arquitectura | Estado |
|---|---|---|
| macOS 26 | arm64 | ✅ Probado (`--help`, `status`, `config show`, `config edit`, carpeta vacía) |
| Windows | x64 | ⚠️ No probado — el `.spec` no tiene nada específico de macOS, debería funcionar igual, pero falta correrlo en una máquina Windows real |
| Linux | x64 | ⚠️ No probado |

PyInstaller no hace cross-compilation: cada plataforma necesita su propio build corrido en esa plataforma (o CI con matrix de runners).

## Las 2 gotchas resueltas

**1. Hidden imports — no hizo falta ninguno.** El primer build (`--onefile` sin tocar nada) ya arrancaba sin `ModuleNotFoundError`: los hooks de `_pyinstaller_hooks_contrib` (`hook-selenium.py`, `hook-fake_useragent.py`, `hook-certifi.py`, `hook-urllib3.py`, `hook-rich.py`, etc., instalados junto con `pyinstaller`) detectaron solos los imports dinámicos de Selenium/webdriver-manager/rich. Único warning fue `importlib_resources.trees not found` — ruido interno de un hook desactualizado, no afecta nada del proyecto.

**2. Ruta de la plantilla de config rota bajo el ejecutable.** `chambaflow/config.py::DEFAULT_TEMPLATE_PATH` se calculaba con `dirname(dirname(__file__))` asumiendo un árbol de archivos real en disco (funciona en dev y con `pip install -e .`, porque ahí sí hay un `chambaflow/config.py` real). Bajo PyInstaller `--onefile`, `__file__` no apunta a un archivo real — y `config/config.example.yaml` es un dato (YAML), no un módulo Python, así que PyInstaller no lo detecta ni lo empaqueta solo. Resultado: el ejecutable en una carpeta vacía nunca generaba `config.yaml`, y cualquier comando tronaba con `FileNotFoundError`.

Fix, en dos partes:
- `chambaflow.spec`: `datas=[('config/config.example.yaml', 'config')]` — embebe el archivo explícitamente.
- `chambaflow/config.py`: si `sys.frozen` (o sea, corriendo empacado), resuelve la raíz vía `sys._MEIPASS` (el directorio temporal donde PyInstaller descomprime esos `datas` en cada arranque) en vez de `__file__`. En dev, el comportamiento no cambió.

## Limitaciones conocidas (no resueltas, a tener en cuenta)

- **Sin firmar/notarizar.** En macOS, si el binario se distribuye por descarga/AirDrop (queda con el flag de cuarentena de Gatekeeper), va a pedir permiso explícito la primera vez ("desarrollador no identificado"). Copiado directo entre carpetas de la misma máquina (como se probó acá) no dispara ese aviso.
- **~15 MB** el binario en macOS arm64 (incluye Python + todas las dependencias).
- Sigue dependiendo de lo mismo que la versión pip: un Chrome/Brave abierto en modo `--remote-debugging-port`, con sesión iniciada a mano — el ejecutable no cambia nada de esa parte.
- No hay build automatizado en CI para esto todavía; es manual, por plataforma.
