# Installation guide (Windows 11)

This guide walks you through a complete, fully-local installation on Windows 11.
Linux and macOS work the same way (only the shell commands differ).

## Quick start (recommended)

If you just want to run the app and have **Python 3.12+** installed:

1. Download or clone the project.
2. Double-click **`start.bat`** in the project root (or, in PowerShell, run
   `./start.ps1`).

On first launch it creates a local virtual environment, installs the app with
the `gui,exif,geo` extras, and opens the GUI. Later launches reuse that
environment and start instantly. The manual steps below (sections 1-7) are the
equivalent long form and are only needed if you want more control or optional
extras.

To build a **standalone executable or a Setup installer** (so end users don't
need Python at all), see ["Building a Windows installer"](#building-a-windows-installer)
below.

## 1. Prerequisites

- **Python 3.12** - install from [python.org](https://www.python.org/downloads/)
  and tick *"Add python.exe to PATH"*. Verify:
  ```powershell
  py -3.12 --version
  ```
- **Git** (optional, to clone the repository).
- **Microsoft Visual C++ Redistributable** - required by some wheels
  (Pillow, PySide6). Usually already present on Windows 11.

## 2. Get the code

```powershell
git clone https://github.com/andreaswilde76-web/photo-organizer-ai.git
cd photo-organizer-ai
```

## 3. Create a virtual environment

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

> If PowerShell blocks the activation script, run once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## 4. Install the application

Install the core plus the recommended extras (GUI, richer EXIF, offline
geocoding):

```powershell
pip install -e ".[gui,exif,geo]"
```

Optional extras:

| Extra     | Enables                                             | Notes |
| --------- | --------------------------------------------------- | ----- |
| `gui`     | the PySide6 desktop application                     | recommended |
| `exif`    | richer EXIF parsing                                 | recommended |
| `geo`     | offline reverse geocoding (city/country)            | recommended |
| `raw`     | RAW photo decoding (CR2/NEF/ARW/DNG)                | needs `rawpy` |
| `faces`   | face detection                                      | needs CMake + dlib |
| `openai`  | optional OpenAI Vision backend                      | cloud, opt-in |
| `dev`     | ruff, black, mypy, pytest                           | development |

Example (everything except cloud):

```powershell
pip install -e ".[gui,exif,geo,raw]"
```

### Installing `faces` (optional)

Face detection uses `face_recognition`, which depends on `dlib`. On Windows the
easiest route is:

```powershell
pip install cmake
pip install dlib
pip install -e ".[faces]"
```

## 5. Install a local vision model (recommended)

The default backend is **Ollama**, which runs vision models locally.

1. Download and install Ollama from [ollama.com](https://ollama.com).
2. Pull a multimodal model (choose one):
   ```powershell
   ollama pull qwen2.5vl:7b     # good quality/speed balance
   ollama pull llava            # lightweight
   ollama pull minicpm-v        # strong on scenes
   ```
3. Ollama runs a local server at `http://localhost:11434` automatically.

> **No GPU?** The models also run on CPU (slower). You can also set
> `ai.enabled: false` to sort purely by metadata + date.

### GPU acceleration

Ollama uses your GPU automatically when a supported NVIDIA/AMD GPU and drivers
are present - no extra configuration is needed. Keep `performance.use_gpu: true`
in the config.

## 6. Configure

```powershell
copy config.example.yaml config.yaml
notepad config.yaml
```

Set at least `source_dir` and `target_dir`. See the
[user guide](user_guide.md) for every option.

## 7. Run

```powershell
# GUI
photo-organizer-gui

# or headless
photo-organizer --config config.yaml
```

## Building a Windows installer

To distribute the app to machines **without** Python, build a standalone
package. All build assets live in [`packaging/windows/`](../packaging/windows/).

> These builds must run **on Windows** - PyInstaller and Inno Setup produce
> native binaries and cannot be cross-compiled.

### Standalone executable

From the project root:

```powershell
packaging\windows\build_exe.bat
```

Output: `dist\PhotoOrganizerAI\PhotoOrganizerAI.exe` (a self-contained folder).

### Setup installer (Setup.exe)

Install [Inno Setup 6](https://jrsoftware.org/isdl.php), then run:

```powershell
packaging\windows\build_installer.bat
```

This builds the executable and compiles the installer. Output:
`dist\installer\PhotoOrganizerAI-Setup.exe` - a single file you can share; it
installs the app with Start-menu (and optional desktop) shortcuts and an
uninstaller.

See [`packaging/windows/README.md`](../packaging/windows/README.md) for details
and how to add a custom icon.

## Troubleshooting

| Symptom | Fix |
| ------- | --- |
| `Ollama server not reachable` | Ensure Ollama is installed and running; check `ai.ollama.host`. |
| HEIC files not read | Ensure `pillow-heif` is installed (it is a core dependency). |
| RAW files skipped | Install the `raw` extra (`pip install -e ".[raw]"`). |
| GUI does not start | Install the `gui` extra; update the VC++ redistributable. |
| Slow analysis | Use a smaller model, lower `ai.max_image_size`, or set `ai.enabled: false`. |
