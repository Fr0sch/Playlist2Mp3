#!/usr/bin/env bash
# Build the Linux release of playlist2mp3-gui.
#
# Produces:
#   dist/playlist2mp3-gui                           (one-file binary)
#   dist/playlist2mp3-gui-linux-x64.tar.gz          (release asset)
#
# Run from the repo root:  ./packaging/build_linux.sh
# Version (optional):      P2M_VERSION=1.2.3 ./packaging/build_linux.sh
#
# Needs yt-dlp + ffmpeg on PATH at runtime (and spotdl for Spotify links).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="${P2M_VERSION:-1.0.0}"
VERSION="${VERSION#v}"
STAGE_NAME="playlist2mp3-gui-linux-x64"
STAGE="dist/$STAGE_NAME"
TARBALL="dist/$STAGE_NAME.tar.gz"

if ! command -v python3 >/dev/null; then
    echo "python3 is required" >&2
    exit 1
fi

VENV="$ROOT/.build-venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip >/dev/null
"$VENV/bin/pip" install -r requirements-dev.txt

echo "==> Building playlist2mp3 $VERSION for Linux"
P2M_VERSION="$VERSION" "$VENV/bin/pyinstaller" --noconfirm --clean \
    packaging/playlist2mp3-gui.spec

if [ ! -x "dist/playlist2mp3-gui" ]; then
    echo "build did not produce dist/playlist2mp3-gui" >&2
    exit 1
fi

rm -rf "$STAGE" "$TARBALL"
mkdir -p "$STAGE"
cp dist/playlist2mp3-gui "$STAGE/"

cat > "$STAGE/README.txt" <<EOF
playlist2mp3 $VERSION - Linux x86_64
====================================

Make the binary executable and run it:

    chmod +x playlist2mp3-gui
    ./playlist2mp3-gui

The app needs yt-dlp and ffmpeg on PATH:

    sudo pacman -S yt-dlp ffmpeg      # Arch
    sudo apt install yt-dlp ffmpeg    # Debian/Ubuntu

Spotify links additionally need spotdl (https://github.com/spotDL/spotify-downloader).

Source: https://github.com/Fr0sch/Playlist2Mp3
EOF

echo "==> Creating $TARBALL"
tar -czf "$TARBALL" -C dist "$STAGE_NAME"
rm -rf "$STAGE"

echo
echo "Built: $ROOT/dist/playlist2mp3-gui"
echo "       $ROOT/$TARBALL"
sha256sum "$TARBALL"
