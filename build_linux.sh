#!/usr/bin/env sh

set -eu

cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD=python
else
    echo "Python 3 não foi encontrado." >&2
    exit 1
fi

if ! "$PYTHON_CMD" -c "import tkinter" >/dev/null 2>&1; then
    echo "O suporte ao Tkinter não está instalado." >&2
    echo "Ubuntu/Debian: sudo apt install python3-tk python3-venv" >&2
    echo "Fedora: sudo dnf install python3-tkinter" >&2
    echo "Arch Linux/Manjaro: sudo pacman -S tk" >&2
    exit 1
fi

echo "[1/3] Criando ambiente de compilação..."
"$PYTHON_CMD" -m venv .venv-build-linux
. .venv-build-linux/bin/activate

echo "[2/3] Instalando dependências..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

echo "[3/3] Gerando aplicativo Linux..."
pyinstaller \
    --noconfirm \
    --clean \
    --windowed \
    --name AssinaPDF \
    --add-data "assets:assets" \
    --collect-all customtkinter \
    app.py

echo
echo "Aplicativo criado em dist/AssinaPDF/AssinaPDF"
echo "Execute com: ./dist/AssinaPDF/AssinaPDF"
