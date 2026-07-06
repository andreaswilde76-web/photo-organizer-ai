# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build specification for PhotoOrganizer AI (Windows).

Build a standalone application folder that end users can run without a Python
installation:

    pip install -e ".[gui,exif,geo,package]"
    pyinstaller packaging\\windows\\PhotoOrganizerAI.spec

The result is dist\\PhotoOrganizerAI\\PhotoOrganizerAI.exe (one-folder build,
which starts faster and is friendlier to antivirus than one-file). The Inno
Setup script (installer.iss) then wraps that folder into a Setup installer.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# ``__file__`` is not defined when a .spec is exec'd, but ``SPECPATH`` is.
SPEC_DIR = Path(SPECPATH).resolve()
PROJECT_ROOT = SPEC_DIR.parent.parent

icon_path = SPEC_DIR / "app.ico"
icon = str(icon_path) if icon_path.is_file() else None

# Bundle the example config next to the executable so first-run users have a
# template to copy to config.yaml.
datas = [(str(PROJECT_ROOT / "config.example.yaml"), ".")]

# pillow-heif and reverse_geocoder ship data files / dynamic submodules that
# PyInstaller does not always pick up automatically.
datas += collect_data_files("pillow_heif")
datas += collect_data_files("reverse_geocoder")

hiddenimports = []
hiddenimports += collect_submodules("photo_organizer")
hiddenimports += collect_submodules("pillow_heif")

block_cipher = None

a = Analysis(
    [str(SPEC_DIR / "entry_point.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Trim heavy, unused optional backends to keep the build smaller. Users who
    # enable them install the extras separately and run from source.
    excludes=["tkinter", "torch", "face_recognition", "rawpy", "matplotlib"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PhotoOrganizerAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowed GUI app, no console window
    disable_windowed_traceback=False,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PhotoOrganizerAI",
)
