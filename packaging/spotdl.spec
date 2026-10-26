# -*- mode: python ; coding: utf-8 -*-
#
# Freeze spotdl so it can be shipped next to the GUI.
#
#   pyinstaller --noconfirm packaging/spotdl.spec
#
# Produces `dist/spotdl/` (onedir) with `spotdl` / `spotdl.exe` inside. The
# Windows build copies that folder to `<bundle>/bin/spotdl/`; p2m_core looks
# for bundled tools there and puts it on PATH for child processes.
import os

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

ROOT = os.path.dirname(SPECPATH)

# spotdl resolves its own version and yt-dlp's at runtime via importlib.metadata.
datas = copy_metadata("spotdl") + copy_metadata("yt-dlp")

# ytmusicapi ships gettext catalogues under `ytmusicapi/locales` (not a
# standard `locale` dir), which PyInstaller does not pick up automatically.
# pykakasi ships the kanji dictionary used for Japanese titles. Without these
# the frozen tool starts and then crashes with FileNotFoundError.
for package in ("spotdl", "ytmusicapi", "pykakasi"):
    datas += collect_data_files(package)

# spotdl imports providers/console commands lazily, so a plain import scan
# misses most of them. Keep every submodule.
hiddenimports = collect_submodules("spotdl") + ["yt_dlp"]

a = Analysis(
    [os.path.join(SPECPATH, "spotdl_entry.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name="spotdl",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="spotdl",
)
