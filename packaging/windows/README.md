# Windows packaging

This folder contains everything needed to ship **PhotoOrganizer AI** on
Windows 11 — either as a quick double-click launcher (run from source) or as a
proper standalone installer.

## Option A — Run from source (no build)

Fastest way to use the app. Requires Python 3.12+ on PATH.

1. Download / clone the project.
2. Double-click **`start.bat`** in the project root (or run `./start.ps1` in
   PowerShell).

On first launch it creates a local `.venv`, installs the app with the
`gui,exif,geo` extras, and starts the GUI. Later launches reuse the environment
and open instantly.

## Option B — Standalone executable (no Python needed by the user)

Produces `dist\PhotoOrganizerAI\PhotoOrganizerAI.exe`, a self-contained folder
that runs on machines without Python installed.

```bat
:: from the project root
packaging\windows\build_exe.bat
```

This creates/uses `.venv`, installs the `package` extra (PyInstaller), and runs
[`PhotoOrganizerAI.spec`](PhotoOrganizerAI.spec).

## Option C — Windows installer (Setup.exe)

Wraps the standalone build into an installer with Start-menu and optional
desktop shortcuts, plus an uninstaller.

**Prerequisite:** [Inno Setup 6](https://jrsoftware.org/isdl.php).

```bat
:: from the project root
packaging\windows\build_installer.bat
```

This runs `build_exe.bat` and then compiles
[`installer.iss`](installer.iss) with Inno Setup's `ISCC.exe`. Output:

```
dist\installer\PhotoOrganizerAI-Setup.exe
```

Distribute that single file — users run it to install the app.

## Files

| File | Purpose |
|------|---------|
| `entry_point.py` | PyInstaller entry script (calls the GUI `main()`) |
| `PhotoOrganizerAI.spec` | PyInstaller build spec (one-folder, windowed) |
| `build_exe.bat` | Builds the standalone executable |
| `installer.iss` | Inno Setup script for the Setup installer |
| `build_installer.bat` | Builds the exe **and** compiles the installer |
| `app.ico` | *(optional)* application icon; auto-detected by the spec/installer if present |

## Notes

- The build must run **on Windows** — PyInstaller and Inno Setup produce
  native Windows binaries and cannot be cross-compiled from Linux/macOS.
- Drop an `app.ico` into this folder to brand the executable and installer; the
  spec and `installer.iss` pick it up automatically (uncomment the
  `SetupIconFile` line in `installer.iss`).
- Optional heavy backends (`faces`, `raw`, local torch models) are excluded
  from the frozen build to keep it small. Users who need them run from source
  with the matching extra, e.g. `pip install -e ".[gui,faces]"`.
- The bundled `config.example.yaml` sits next to the executable; copy it to
  `config.yaml` and edit it to change defaults (source/target folders, AI
  backend, language, …).
