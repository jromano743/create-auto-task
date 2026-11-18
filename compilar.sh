
#!/usr/bin/env bash

set -e

echo "================================"
echo "   CREATE AUTO TASK - BUILD"
echo "================================"

# Verificar entorno virtual
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "Activando entorno virtual..."
    source .venv/bin/activate
fi

# Limpiar compilaciones anteriores
rm -rf build dist

# Compilar CLI
echo "[1/2] Compilando CLI..."

pyinstaller \
    --name create-auto-task \
    --onefile \
    --clean \
    --paths src \
    src/create_auto_task/interfaces/cli/cli.py

# Compilar GUI
echo "[2/2] Compilando GUI..."

pyinstaller \
    --name create-auto-task-gui \
    --onefile \
    --windowed \
    --clean \
    --paths src \
    --collect-all PySide6 \
    src/create_auto_task/interfaces/gui/app.py

echo ""
echo "Build completado."
echo "Ejecutables disponibles en ./dist/"
