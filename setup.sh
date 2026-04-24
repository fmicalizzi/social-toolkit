#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────────
# Social Media Toolkit — Setup
#
# Ejecuta una sola vez para preparar el entorno.
# Idempotente: se puede volver a ejecutar sin riesgo.
#
# Uso:
#   bash setup.sh                              # instalacion limpia
#   bash setup.sh /ruta/a/browser_profile/    # importar sesion existente
# ──────────────────────────────────────────────────────────────────────────────
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "  Social Media Toolkit — Setup"
echo "  Directorio: $SCRIPT_DIR"
echo "============================================================"
echo ""

# ── 1. Python venv ──
if [ -d "venv" ] && [ -f "venv/bin/python3" ]; then
    echo "[ok] venv ya existe"
else
    echo "[...] Creando entorno virtual Python..."
    python3 -m venv venv
    echo "[ok] venv creado"
fi

# ── 2. Dependencias Python ──
echo "[...] Instalando dependencias (playwright, yt-dlp, pyyaml)..."
venv/bin/python3 -m pip install -q --upgrade pip
venv/bin/python3 -m pip install -q -r requirements.txt
echo "[ok] Dependencias instaladas"

# ── 3. Playwright Chromium ──
echo "[...] Instalando Chromium para Playwright..."
venv/bin/playwright install chromium
echo "[ok] Chromium instalado"

# ── 4. Directorios necesarios ──
mkdir -p browser_profile
mkdir -p output
echo "[ok] Directorios creados (browser_profile/, output/)"

# ── 5. Verificar ffmpeg ──
echo ""
FFMPEG_PATH=""
if command -v /opt/homebrew/bin/ffmpeg &>/dev/null; then
    FFMPEG_PATH="/opt/homebrew/bin/ffmpeg"
elif command -v /usr/local/bin/ffmpeg &>/dev/null; then
    FFMPEG_PATH="/usr/local/bin/ffmpeg"
elif command -v ffmpeg &>/dev/null; then
    FFMPEG_PATH="$(which ffmpeg)"
fi

if [ -n "$FFMPEG_PATH" ]; then
    FFPROBE_PATH="${FFMPEG_PATH/ffmpeg/ffprobe}"
    echo "[ok] ffmpeg: $FFMPEG_PATH"
    if [ "$FFMPEG_PATH" != "/opt/homebrew/bin/ffmpeg" ]; then
        echo ""
        echo "  NOTA: Actualiza estas rutas en config.yaml:"
        echo "    conversion:"
        echo "      ffmpeg:  \"$FFMPEG_PATH\""
        echo "      ffprobe: \"$FFPROBE_PATH\""
    fi
else
    echo "[!!] ffmpeg NO encontrado"
    echo "     - Descarga y metadata funcionan sin ffmpeg."
    echo "     - La conversion VP9->H.264 requiere ffmpeg."
    echo "     macOS:  brew install ffmpeg"
    echo "     Linux:  sudo apt install ffmpeg"
fi

# ── 6. Importar browser_profile existente (opcional, via argumento) ──
echo ""
if [ -n "$1" ] && [ -d "$1" ]; then
    if [ -d "$1/Default" ]; then
        echo "[...] Importando browser_profile desde: $1"
        cp -R "$1"/* browser_profile/
        echo "[ok] Browser profile importado (sesion reutilizable)"
    else
        echo "[!!] El directorio $1 no parece un browser_profile valido (no contiene Default/)"
    fi
else
    echo "[--] Browser profile limpio."
    echo "     La primera vez que uses una plataforma con login,"
    echo "     se abrira un browser para iniciar sesion manualmente."
    echo ""
    echo "     Para importar una sesion existente:"
    echo "     bash setup.sh /ruta/a/browser_profile_existente"
fi

# ── Listo ──
echo ""
echo "============================================================"
echo "  Setup completado."
echo ""
echo "  Comandos principales:"
echo "    venv/bin/python3 cli.py --help"
echo "    venv/bin/python3 cli.py instagram snapshot @username"
echo "    venv/bin/python3 cli.py facebook snapshot pagename"
echo "    venv/bin/python3 cli.py tiktok snapshot @username"
echo "    venv/bin/python3 cli.py youtube snapshot https://youtube.com/@handle"
echo "    venv/bin/python3 cli.py twitter snapshot @username"
echo "============================================================"
