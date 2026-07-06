# User manual

This manual explains how to use PhotoOrganizer AI, both through the desktop GUI
and the command line, and documents every configuration option.

## 1. Concepts

- **Source folder** - where your unsorted photos/videos currently live. It is
  scanned recursively (configurable).
- **Target folder** - the root under which the `Year / Month / Event` structure
  is created.
- **Event** - a group of media files that belong to the same real-world happening
  (a trip, a party, a hike). Events are detected automatically.
- **Operation** - `copy` (safe; originals stay) or `move` (originals relocated).
- **Cache** - a SQLite database that remembers analysis results per file, so
  re-runs are fast.

## 2. The workflow

1. **Analyse** - the app scans the source folder, extracts metadata, determines
   the capture date, (optionally) runs the vision model, and clusters files into
   events. Nothing is moved yet.
2. **Preview & edit** - review the proposed `Year / Month / Event` structure,
   rename events and merge/split them.
3. **Confirm** - only now are files copied or moved into the target folder.
4. **Resume** - if the process is interrupted, run it again to continue where it
   stopped.

## 3. Using the desktop GUI

Launch it with:

```
photo-organizer-gui
```

The window has four areas:

### Folders
- **Source folder / Target folder** - pick with *Browse…* or type a path.
- **Operation** - `copy` or `move`.

### Controls
- **Start** - begin analysis.
- **Pause / Resume** - temporarily halt / continue analysis.
- **Stop** - stop analysis gracefully (already-processed results are kept).
- **Organize files…** - executes the (confirmed) copy/move. Enabled after
  analysis finishes.

### Progress
A progress bar and a status line show how many files have been processed.

### Event preview (left) and Live log (right)
- The **event tree** lists every event and its files.
  - **Double-click** an event row to **rename** it.
  - **Drag a file** from one event onto another to **move** it - this is how you
    split a file out of an event or merge it into another.
  - Dragging out the last file of an event automatically removes the now-empty
    event.
  - Click **Apply edits to plan** to rebuild the placement plan from your edits.
- The **live log** streams what the app is doing, colour-coded by severity.

When you click **Organize files…**, a confirmation dialog appears; only after you
confirm are any files touched.

## 4. Using the command line

```bash
# Analyse, preview, then ask for confirmation before copying/moving
photo-organizer --config config.yaml

# Skip the confirmation prompt
photo-organizer --config config.yaml --yes

# Only analyse and print the plan (never touches files)
photo-organizer --config config.yaml --dry-run

# Override paths / operation without editing the config
photo-organizer --config config.yaml --source D:/In --target D:/Out --operation move

# Resume an interrupted run
photo-organizer --config config.yaml resume
```

## 5. Configuration reference

The config file is YAML or JSON. Unknown keys are ignored; every key is optional
and falls back to a sensible default.

| Key | Default | Description |
| --- | --- | --- |
| `source_dir` | `.` | Folder with unsorted media. |
| `target_dir` | `./Fotos` | Root of the created structure. |
| `operation` | `copy` | `copy` or `move`. |
| `database_path` | `photo_organizer.sqlite` | Cache/resume database. |
| `language` | `de` | Language for names/descriptions (`de` or `en`). |
| `logging.level` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR`. |
| `logging.file` | `photo_organizer.log` | Log file (or `null`). |
| `logging.console` | `true` | Also log to the console. |
| `media.photo_extensions` | jpg, jpeg, png, heic, webp, tif, tiff, raw, cr2, nef, arw, dng | Photo types. |
| `media.video_extensions` | mp4, mov, avi, mkv | Video types. |
| `media.recursive` | `true` | Recurse into sub-folders. |
| `media.min_file_size` | `1024` | Skip files smaller than N bytes. |
| `ai.backend` | `ollama` | `ollama`, `openai` or `null`. |
| `ai.model` | `qwen2.5vl:7b` | Model name for the backend. |
| `ai.enabled` | `true` | Turn vision analysis on/off. |
| `ai.max_image_size` | `1024` | Down-scale longest edge before analysis. |
| `ai.timeout` | `120` | Request timeout (seconds). |
| `ai.estimate_date_when_missing` | `true` | Let the model guess a date when none is found. |
| `ai.ollama.host` | `http://localhost:11434` | Ollama server URL. |
| `ai.ollama.keep_alive` | `5m` | How long Ollama keeps the model loaded. |
| `ai.openai.api_key` | `""` | OpenAI key (or `OPENAI_API_KEY` env var). |
| `ai.openai.base_url` | `https://api.openai.com/v1` | OpenAI-compatible endpoint. |
| `geo.enabled` | `true` | Offline reverse geocoding. |
| `faces.enabled` | `false` | Face detection. |
| `clustering.max_time_gap_hours` | `6.0` | Max time gap within one event. |
| `clustering.max_distance_km` | `25.0` | Max GPS distance within one event. |
| `clustering.visual_weight` | `0.4` | Weight of visual similarity (0..1). |
| `clustering.min_cluster_size` | `1` | Smaller clusters become generic `Event NN`. |
| `performance.workers` | `0` | Worker threads (`0` = auto/CPU count). |
| `performance.use_gpu` | `true` | Use the GPU if the backend supports it. |

## 6. How event names are chosen

For each event the app combines, in order of priority:

1. **Holiday** detected from the date (e.g. *Weihnachten*, *Silvester*).
2. **Location** from reverse-geocoded GPS (landmark → city → country).
3. **Dominant scene** from vision tags (e.g. *Strand*, *Berge*, *Restaurant*).

Examples: `Weihnachten`, `Palma Strand`, `Berge Wanderung`. If no meaningful
signal is available, the event is named `Event 01`, `Event 02`, …

## 7. Capture-date resolution order

1. EXIF `DateTimeOriginal`
2. EXIF / media creation date (photos: `DateTime`; videos: container `mvhd`)
3. GPS timestamp
4. Date parsed from the file name (e.g. `IMG_20230714_183000.jpg`)
5. Filesystem modification time
6. AI estimate from image content (if enabled and nothing else worked)

The chosen source is recorded per file (visible in `DEBUG` logs and stored in the
database).

## 8. Caching, performance and resume

- Each file is hashed; if an analysis for that hash already exists, it is loaded
  from the database instead of being re-analysed.
- Analysis runs across multiple threads (`performance.workers`).
- The planned placements are recorded before execution; if the run is
  interrupted, `resume` (CLI) continues with the remaining files without
  duplicating anything.

## 9. Privacy

Everything runs locally. With `ai.backend: ollama` (or `null`) and
`geo.enabled: true` (offline dataset), **no data leaves your machine**. The
OpenAI backend is the only component that would contact a cloud service, and it
is off by default.
