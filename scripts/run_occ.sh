#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

echo "Abriendo Brave con depuración remota (puerto 9222)..."
/Applications/Brave\ Browser.app/Contents/MacOS/Brave\ Browser \
  --remote-debugging-port=9222 \
  --user-data-dir="$(pwd)/session_data_brave" &

echo "Esperando 6 segundos a que Brave inicie..."
sleep 6

echo "Ejecutando bot de OCC..."
source venv/bin/activate
python -u main.py --config config.yaml --sitio occ
