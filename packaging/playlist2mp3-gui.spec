# -*- mode: python ; coding: utf-8 -*-
#
# Build:  pyinstaller packaging/playlist2mp3-gui.spec
#
# Produces a one-file executable on Linux/Windows and a double-clickable
# `playlist2mp3-gui.app` bundle on macOS. On Apple Silicon the app is built
# for arm64 (override with the P2M_ARCH environment variable).
import os
import platform
import sys


def _find_root(start):
    d = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(d, "playlist2mp3_gui.py")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            raise SystemExit("could not locate the playlist2mp3 project root")
        d = parent


ROOT = _find_root(SPECPATH)

IS_MAC = sys.platform == "darwin"


def _target_arch():
    override = os.environ.get("P2M_ARCH")
    if override:
        return override
    if not IS_MAC:
        return None
    machine = platform.machine()
    return {"aarch64": "arm64"}.get(machine, machine)


TARGET_ARCH = _target_arch()

a = Analysis(
    [os.path.join(ROOT, "playlist2mp3_gui.py")],
    pathex=[ROOT],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "test", "unittest"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="playlist2mp3-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=TARGET_ARCH,
    codesign_identity=os.environ.get("P2M_CODESIGN_IDENTITY") or None,
    entitlements_file=None,
)

if IS_MAC:
    app = BUNDLE(
        exe,
        name="playlist2mp3-gui.app",
        icon=None,
        bundle_identifier="com.playlist2mp3.gui",
        info_plist={
            "CFBundleName": "playlist2mp3",
            "CFBundleDisplayName": "playlist2mp3",
            "CFBundleShortVersionString": "1.0.0",
            "CFBundleVersion": "1.0.0",
            "LSMinimumSystemVersion": "12.0",
            "NSHighResolutionCapable": True,
        },
    )