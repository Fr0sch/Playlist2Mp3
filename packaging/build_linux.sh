#!/usr/bin/env bash
# Build playlist2mp3-gui for Linux with PyInstaller.
# Produces dist/playlist2mp3-gui (one-file binary).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null; then
    echo "python3 is required" >&2
    exit 1
fi

VENV="$ROOT/.build-venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip >/dev/null
"$VENV/bin/pip" install -r requirements-dev.txt

"$VENV/bin/pyinstaller" --noconfirm packaging/playlist2mp3-gui.spec

echo
echo "Built: $ROOT/dist/playlist2mp3-gui"
echo "Note: yt-dlp, ffmpeg and spotdl must be installed on the target system."