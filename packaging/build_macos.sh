#!/usr/bin/env bash
# Build the macOS release of playlist2mp3-gui (Apple Silicon / arm64).
#
# Produces:
#   dist/playlist2mp3-gui.app                       (double-clickable bundle)
#   dist/playlist2mp3-gui-macos-arm64.zip           (release asset)
#
# Run from the repo root:  ./packaging/build_macos.sh
# Version (optional):      P2M_VERSION=1.2.3 ./packaging/build_macos.sh
#
# The app is ad-hoc signed (not notarized). It finds yt-dlp/ffmpeg from
# Homebrew (/opt/homebrew/bin) even when launched from Finder; install them
# with:  brew install yt-dlp ffmpeg spotdl
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="${P2M_VERSION:-1.0.0}"
VERSION="${VERSION#v}"
APP="dist/playlist2mp3-gui.app"
STAGE_NAME="playlist2mp3-gui-macos-arm64"
STAGE="dist/$STAGE_NAME"
ZIP="dist/$STAGE_NAME.zip"

if ! command -v python3 >/dev/null; then
    echo "python3 is required (brew install python)" >&2
    exit 1
fi

VENV="$ROOT/.build-venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip >/dev/null
"$VENV/bin/pip" install -r requirements-dev.txt

# The spec bakes P2M_VERSION into Info.plist (CFBundleShortVersionString /
# CFBundleVersion), so pass it through the environment.
echo "==> Building playlist2mp3 $VERSION for macOS"
P2M_VERSION="$VERSION" "$VENV/bin/pyinstaller" --noconfirm --clean \
    packaging/playlist2mp3-gui.spec

if [ ! -d "$APP" ]; then
    echo "build did not produce $APP" >&2
    exit 1
fi

# Belt and braces for local builds: make sure the version really is in the
# bundle, then re-sign (editing Info.plist invalidates the signature).
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" \
    "$APP/Contents/Info.plist" >/dev/null 2>&1 || true
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $VERSION" \
    "$APP/Contents/Info.plist" >/dev/null 2>&1 || true

echo "==> Ad-hoc signing"
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

echo "==> Architecture: $(lipo -archs "$APP/Contents/MacOS/playlist2mp3-gui" 2>/dev/null || echo unknown)"
echo "==> Version: $(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$APP/Contents/Info.plist")"

# Stage the app together with a short readme, then zip the folder with ditto.
# ditto preserves executable bits and symlinks; `zip -r` does not always do so,
# and `actions/upload-artifact` flattens bundles, which is why the old artifact
# unpacked to loose Contents/ files instead of a .app.
rm -rf "$STAGE" "$ZIP"
mkdir -p "$STAGE"
ditto "$APP" "$STAGE/playlist2mp3-gui.app"

cat > "$STAGE/README.txt" <<EOF
playlist2mp3 $VERSION - macOS (Apple Silicon / arm64)
=====================================================

Drag playlist2mp3-gui.app into your Applications folder and open it.

The app needs three command line tools, install them once with Homebrew:

    brew install yt-dlp ffmpeg spotdl

(spotdl is only needed for Spotify links; YouTube works with yt-dlp + ffmpeg.)

The app is ad-hoc signed but not notarized. On first launch macOS may say it
cannot verify the app. Either right-click the app and choose "Open", or run:

    xattr -dr com.apple.quarantine /Applications/playlist2mp3-gui.app

Source: https://github.com/Fr0sch/Playlist2Mp3
EOF

echo "==> Creating $ZIP"
ditto -c -k --sequesterRsrc --keepParent "$STAGE" "$ZIP"
rm -rf "$STAGE"

echo
echo "Built: $ROOT/$APP"
echo "       $ROOT/$ZIP"
shasum -a 256 "$ZIP"
