# Build the Windows release of playlist2mp3-gui.
#
# Produces a fully self-contained folder and zip:
#
#   dist\playlist2mp3-gui-windows-x64\
#     playlist2mp3-gui.exe
#     README.txt
#     bin\yt-dlp.exe
#     bin\ffmpeg.exe
#     bin\ffprobe.exe
#     bin\spotdl\spotdl.exe      (PyInstaller onedir build)
#
# Run from PowerShell:  .\packaging\build_windows.ps1
# Version (optional):   $env:P2M_VERSION = "1.2.3"
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $ROOT

$VERSION = if ($env:P2M_VERSION) { $env:P2M_VERSION } else { "1.0.0" }
$env:P2M_VERSION = $VERSION
$STAGE_NAME = "playlist2mp3-gui-windows-x64"
$STAGE = Join-Path $ROOT "dist\$STAGE_NAME"
$BIN = Join-Path $STAGE "bin"
$VENV = Join-Path $ROOT ".build-venv"
$PY = Join-Path $VENV "Scripts\python.exe"

Write-Host "==> Building playlist2mp3 $VERSION for Windows"

if (-not (Test-Path $PY)) {
    python -m venv $VENV
}
& $PY -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
& $PY -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) { throw "dependency install failed" }

# --- GUI executable -------------------------------------------------------
& $PY -m PyInstaller --noconfirm --clean packaging/playlist2mp3-gui.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller (GUI) failed" }

# --- spotdl (frozen, so Spotify support works without installing anything) --
& $PY -m pip install "spotdl>=4.2,<5"
if ($LASTEXITCODE -ne 0) { throw "spotdl install failed" }
& $PY -m PyInstaller --noconfirm --clean packaging/spotdl.spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller (spotdl) failed" }

# --- assemble the release folder -----------------------------------------
Remove-Item -Recurse -Force $STAGE -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $BIN | Out-Null

Copy-Item (Join-Path $ROOT "dist\playlist2mp3-gui.exe") $STAGE

Write-Host "==> Downloading yt-dlp"
Invoke-WebRequest -UseBasicParsing `
    -Uri "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe" `
    -OutFile (Join-Path $BIN "yt-dlp.exe")

Write-Host "==> Downloading ffmpeg + ffprobe"
$TMP = Join-Path ([System.IO.Path]::GetTempPath()) ("p2m-ffmpeg-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force $TMP | Out-Null
try {
    $FFMPEG_ZIP = Join-Path $TMP "ffmpeg.zip"
    Invoke-WebRequest -UseBasicParsing `
        -Uri "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip" `
        -OutFile $FFMPEG_ZIP
    Expand-Archive -Path $FFMPEG_ZIP -DestinationPath $TMP -Force

    $FFMPEG = Get-ChildItem -Path $TMP -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
    if (-not $FFMPEG) { throw "ffmpeg.exe not found in the downloaded archive" }
    $FFPROBE = Join-Path $FFMPEG.Directory.FullName "ffprobe.exe"
    if (-not (Test-Path $FFPROBE)) { throw "ffprobe.exe not found next to ffmpeg.exe" }

    Copy-Item $FFMPEG.FullName $BIN
    Copy-Item $FFPROBE $BIN

    # GPL compliance: ship the license text that comes with the build.
    $LICENSE = Get-ChildItem -Path $TMP -Recurse -Include "LICENSE.txt", "LICENSE" |
        Select-Object -First 1
    if ($LICENSE) { Copy-Item $LICENSE.FullName (Join-Path $BIN "ffmpeg-LICENSE.txt") }
}
finally {
    Remove-Item -Recurse -Force $TMP -ErrorAction SilentlyContinue
}

Write-Host "==> Bundling spotdl"
Copy-Item -Recurse (Join-Path $ROOT "dist\spotdl") (Join-Path $BIN "spotdl")
if (-not (Test-Path (Join-Path $BIN "spotdl\spotdl.exe"))) {
    throw "frozen spotdl.exe is missing"
}

# --- smoke test the bundled tools ----------------------------------------
Write-Host "==> Smoke-testing bundled tools"
& (Join-Path $BIN "yt-dlp.exe") --version
if ($LASTEXITCODE -ne 0) { throw "bundled yt-dlp does not run" }

& (Join-Path $BIN "ffmpeg.exe") -version | Select-Object -First 1
if ($LASTEXITCODE -ne 0) { throw "bundled ffmpeg does not run" }

& (Join-Path $BIN "ffprobe.exe") -version | Select-Object -First 1
if ($LASTEXITCODE -ne 0) { throw "bundled ffprobe does not run" }

& (Join-Path $BIN "spotdl\spotdl.exe") --version
if ($LASTEXITCODE -ne 0) { throw "bundled spotdl does not run" }

# --- README + zip ---------------------------------------------------------
$README = @"
playlist2mp3 $VERSION - Windows x64
====================================

Double-click playlist2mp3-gui.exe. Nothing else needs to be installed: yt-dlp,
ffmpeg, ffprobe and spotdl are included in the bin folder.

Paste a YouTube or Spotify link, press Load, tick the tracks you want and press
Download. Files are written to the folder shown under "Output folder"
(%USERPROFILE%\Music by default).

Notes
-----
- Windows SmartScreen may warn about an unsigned app. Choose "More info"
  then "Run anyway".
- Spotify links are handled by the bundled spotdl. A free Spotify account is
  enough; no API keys are needed.
- Keep the exe next to the bin folder. If you move the exe, move the whole
  folder.
- ffmpeg is licensed under the GPL; see bin\ffmpeg-LICENSE.txt.

Source: https://github.com/Fr0sch/Playlist2Mp3
"@
Set-Content -Path (Join-Path $STAGE "README.txt") -Value $README -Encoding UTF8

$ZIP = Join-Path $ROOT "dist\$STAGE_NAME.zip"
Remove-Item -Force $ZIP -ErrorAction SilentlyContinue
Write-Host "==> Creating $ZIP"
Compress-Archive -Path $STAGE -DestinationPath $ZIP -CompressionLevel Optimal

Write-Host ""
Write-Host "Built: $ZIP"
