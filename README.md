# PhotoOrganizer AI

A fully local, AI-assisted tool that analyses a large photo & video collection
and automatically sorts it into a clean `Year / Month / Event` folder structure -
with meaningful event names such as *"Mallorca Urlaub"*, *"Weihnachten"* or
*"Wanderung"*.

```
Fotos/
├── 2022/
│   ├── 01 Januar/
│   │   ├── Silvester/
│   │   └── Event 02/
│   ├── 07 Juli/
│   │   └── Palma Strand/
│   └── ...
├── 2023/
│   └── 12 Dezember/
│       └── Weihnachten/
└── ...
```

Everything runs **100 % locally** - no cloud service is required. All AI
components are swappable and the code is modular, typed and production-ready.

---

## Features

- **Smart sorting** into `Year / Month (NN Monat) / Event` folders.
- **Meaningful event names** derived from location (GPS → city/landmark),
  detected scene (beach, mountains, restaurant, gym, concert …) and holidays
  (Christmas, New Year …); falls back to `Event 01`, `Event 02`, …
- **Robust capture-date detection**: EXIF `DateTimeOriginal` → EXIF/media
  creation date → GPS timestamp → date in the file name → filesystem date →
  optional **AI estimate** from image content.
- **Multi-signal event clustering** combining time proximity, GPS distance and
  visual/scene similarity.
- **Local vision models** via [Ollama](https://ollama.com) (Qwen2.5-VL, LLaVA,
  MiniCPM-V) with an optional OpenAI Vision fallback. The backend and model are
  chosen in the config file.
- **Reverse geocoding** (offline) for city / region / country.
- **Face detection** (optional; recognition is a documented extension point).
- **SQLite cache**: every analysed file (keyed by content hash) is stored, so
  re-runs are fast and already-analysed images are never re-analysed.
- **Preview first**: nothing is moved until you confirm; a **copy mode** is
  available as a safe alternative to moving.
- **Resume** after an interruption without duplicating or losing files.
- **Modern PySide6 desktop GUI**: folder pickers, Start / Pause / Resume,
  progress bar, live log, an editable event tree and drag-and-drop to
  merge/split events.
- **Performance**: multithreaded analysis, multi-core friendly, GPU used when
  the backend supports it, results cached.
- **Quality**: full type hints, `ruff` + `black` + `mypy` clean, unit tests.

## Supported file types

| Photos | Videos |
| ------ | ------ |
| jpg, jpeg, png, heic, webp, tif, tiff, raw (cr2/nef/arw/dng) | mp4, mov, avi, mkv |

## Quick start (Windows 11)

**Easiest:** double-click **`start.bat`** (or run `./start.ps1` in PowerShell).
On first run it creates a local virtual environment, installs the app, and opens
the GUI; later runs start instantly. Requires Python 3.12+ on PATH.

<details>
<summary>Manual steps (equivalent to <code>start.bat</code>)</summary>

```powershell
# 1. Create and activate a virtual environment (Python 3.12)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install the app with the recommended extras
pip install -e ".[gui,exif,geo]"

# 3. (Recommended) Install a local vision model via Ollama
#    Download Ollama from https://ollama.com, then:
ollama pull qwen2.5vl:7b

# 4. Configure
copy config.example.yaml config.yaml   # then edit source_dir / target_dir

# 5a. Launch the GUI
photo-organizer-gui

# 5b. …or run headless
photo-organizer --config config.yaml
```
</details>

**Build a standalone installer** (so users don't need Python): run
`packaging\windows\build_installer.bat` to produce
`dist\installer\PhotoOrganizerAI-Setup.exe`. See
[packaging/windows/README.md](packaging/windows/README.md).

See [docs/installation.md](docs/installation.md) for the detailed installation
guide and [docs/user_guide.md](docs/user_guide.md) for the full user manual.

## How it works

```
scan → hash → (cache hit? load) → metadata/EXIF → capture date
     → GPS reverse-geocode → face count → vision analysis
     → cluster into events → name events → build preview plan
     → [confirm] → move/copy (resumable)
```

## Project layout

```
src/photo_organizer/
├── config.py            # typed YAML/JSON configuration
├── logging_setup.py     # logging + GUI live-log handler
├── models.py            # domain models (MediaFile, Event, …)
├── database.py          # SQLite cache + resume store
├── hashing.py           # content hashing (cache keys)
├── media/               # scanner, metadata/EXIF, date resolution
├── ai/                  # VisionModel ABC + Ollama/OpenAI/Null backends
├── geo/                 # offline reverse geocoding
├── faces/               # optional face detection
├── clustering/          # event clustering + naming
├── organizer/           # planner (preview) + executor (move/copy/resume)
├── pipeline.py          # end-to-end orchestration (threads, cache, resume)
├── gui/                 # PySide6 desktop application
└── __main__.py          # command-line interface
```

## Configuration

The application is driven by a single YAML (or JSON) file. Copy
`config.example.yaml` to `config.yaml` and adjust it. Highlights:

```yaml
source_dir: "C:/Users/You/Pictures/Unsorted"
target_dir: "C:/Users/You/Pictures/Fotos"
operation: "copy"          # or "move"
ai:
  backend: "ollama"        # ollama | openai | null
  model: "qwen2.5vl:7b"    # any multimodal model in Ollama
  enabled: true
```

## Development

```bash
pip install -e ".[dev,gui,exif,geo]"
ruff check .
black --check .
mypy
pytest
```

## License

MIT - see [LICENSE](LICENSE).
