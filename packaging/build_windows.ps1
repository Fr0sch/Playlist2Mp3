# Build playlist2mp3-gui for Windows with PyInstaller.
# Produces dist\playlist2mp3-gui.exe (one-file binary).
# Run from PowerShell:  .\packaging\build_windows.ps1
$ErrorActionPreference = "Stop"

$ROOT = Split-Path -Parent $PSScriptRoot
Set-Location $ROOT

$VENV = Join-Path $ROOT ".build-venv"
python -m venv $VENV
& (Join-Path $VENV "Scripts\python.exe") -m pip install --upgrade pip | Out-Null
& (Join-Path $VENV "Scripts\python.exe") -m pip install -r requirements-dev.txt

& (Join-Path $VENV "Scripts\pyinstaller.exe") --noconfirm packaging/playlist2mp3-gui.spec

Write-Host ""
Write-Host "Built: $ROOT\dist\playlist2mp3-gui.exe"
Write-Host "Note: yt-dlp, ffmpeg and spotdl must be installed on the target system."