#!/usr/bin/env bash
# Build playlist2mp3-gui for macOS (Apple Silicon) with PyInstaller.
# Produces dist/playlist2mp3-gui.app (double-clickable app bundle).
# Run from the repo root:  ./packaging/build_macos.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null; then
    echo "python3 is required (brew install python)" >&2
    exit 1
fi

VENV="$ROOT/.build-venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip >/dev/null
"$VENV/bin/pip" install -r requirements-dev.txt

# P2M_ARCH=universal2 can be exported for a universal build (needs universal
# Python + universal wheels). Default: the machine's own architecture (arm64
# on Apple Silicon).
"$VENV/bin/pyinstaller" --noconfirm packaging/playlist2mp3-gui.spec

echo
echo "Built: $ROOT/dist/playlist2mp3-gui.app"
echo "Note: yt-dlp, ffmpeg and spotdl must be installed on the target system."
echo "      brew install yt-dlp ffmpeg spotdl"
echo "      Homebrew's /opt/homebrew/bin is searched even when launched from Finder."
