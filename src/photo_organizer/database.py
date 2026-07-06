"""SQLite persistence and analysis cache.

The database serves two purposes:

* **Cache** - already-analysed files (keyed by content hash) are never analysed
  again, which makes re-runs cheap.
* **Resume** - a job table records which files have already been placed into the
  target structure, so an interrupted run can be resumed safely.

The layer is intentionally thin: it stores/loads :class:`MediaFile` records and
exposes a small, typed API. JSON is used for the flexible sub-objects (analysis,
geo, persons) to keep the schema stable while remaining queryable enough.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any

from .logging_setup import get_logger
from .models import (
    DateSource,
    GeoInfo,
    ImageAnalysis,
    MediaFile,
    MediaKind,
)

__all__ = ["Database"]

_LOG = get_logger("database")

_SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS media (
    file_hash    TEXT PRIMARY KEY,
    path         TEXT NOT NULL,
    kind         TEXT NOT NULL,
    size         INTEGER NOT NULL,
    capture_date TEXT,
    date_source  TEXT,
    camera_model TEXT,
    face_count   INTEGER DEFAULT 0,
    exif_json    TEXT,
    geo_json     TEXT,
    persons_json TEXT,
    analysis_json TEXT,
    description  TEXT,
    event_id     INTEGER,
    analyzed_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_media_event ON media(event_id);

CREATE TABLE IF NOT EXISTS placements (
    file_hash    TEXT PRIMARY KEY,
    source_path  TEXT NOT NULL,
    target_path  TEXT NOT NULL,
    operation    TEXT NOT NULL,
    done         INTEGER NOT NULL DEFAULT 0,
    placed_at    TEXT
);
"""


def _dt_to_str(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _str_to_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:  # pragma: no cover - defensive
        return None


class Database:
    """A thread-safe wrapper around a SQLite analysis cache.

    Use it as a context manager::

        with Database(Path("cache.sqlite")) as db:
            db.upsert_media(media_file)
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        # check_same_thread=False + an explicit lock lets the pipeline's worker
        # threads share one connection safely.
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._initialise()

    # -- lifecycle -------------------------------------------------------- #
    def _initialise(self) -> None:
        with self._lock:
            self._conn.executescript(_SCHEMA)
            cur = self._conn.execute("SELECT value FROM meta WHERE key = 'schema_version'")
            row = cur.fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO meta(key, value) VALUES('schema_version', ?)",
                    (str(_SCHEMA_VERSION),),
                )
            self._conn.commit()

    def close(self) -> None:
        """Commit and close the underlying connection."""
        with self._lock:
            self._conn.commit()
            self._conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # -- media cache ------------------------------------------------------ #
    def has_analysis(self, file_hash: str) -> bool:
        """Return ``True`` if a fully analysed record exists for *file_hash*."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT analyzed_at FROM media WHERE file_hash = ?", (file_hash,)
            )
            row = cur.fetchone()
            return bool(row and row["analyzed_at"])

    def upsert_media(
        self,
        media: MediaFile,
        *,
        exif: dict[str, Any] | None = None,
        persons: list[str] | None = None,
    ) -> None:
        """Insert or update the cached record for *media*."""
        analysis_json = None
        description = None
        if media.analysis is not None:
            analysis_json = json.dumps(_analysis_to_dict(media.analysis), ensure_ascii=False)
            description = media.analysis.description
        geo_json = json.dumps(_geo_to_dict(media.geo), ensure_ascii=False) if media.geo else None
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO media(
                    file_hash, path, kind, size, capture_date, date_source,
                    camera_model, face_count, exif_json, geo_json, persons_json,
                    analysis_json, description, event_id, analyzed_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(file_hash) DO UPDATE SET
                    path=excluded.path,
                    kind=excluded.kind,
                    size=excluded.size,
                    capture_date=excluded.capture_date,
                    date_source=excluded.date_source,
                    camera_model=excluded.camera_model,
                    face_count=excluded.face_count,
                    exif_json=excluded.exif_json,
                    geo_json=excluded.geo_json,
                    persons_json=excluded.persons_json,
                    analysis_json=excluded.analysis_json,
                    description=excluded.description,
                    event_id=excluded.event_id,
                    analyzed_at=excluded.analyzed_at
                """,
                (
                    media.file_hash,
                    str(media.path),
                    media.kind.value,
                    media.size,
                    _dt_to_str(media.capture_date),
                    media.date_source.value,
                    media.camera_model,
                    media.face_count,
                    json.dumps(exif, ensure_ascii=False, default=str) if exif else None,
                    geo_json,
                    json.dumps(persons, ensure_ascii=False) if persons else None,
                    analysis_json,
                    description,
                    media.event_id,
                    _dt_to_str(media.analyzed_at or datetime.now()),
                ),
            )
            self._conn.commit()

    def load_media(self, file_hash: str) -> MediaFile | None:
        """Reconstruct a :class:`MediaFile` from the cache, or ``None``."""
        with self._lock:
            cur = self._conn.execute("SELECT * FROM media WHERE file_hash = ?", (file_hash,))
            row = cur.fetchone()
        return _row_to_media(row) if row else None

    def update_event(self, file_hash: str, event_id: int) -> None:
        """Persist the event assignment for a file."""
        with self._lock:
            self._conn.execute(
                "UPDATE media SET event_id = ? WHERE file_hash = ?", (event_id, file_hash)
            )
            self._conn.commit()

    # -- placements / resume --------------------------------------------- #
    def record_placement(self, file_hash: str, source: Path, target: Path, operation: str) -> None:
        """Record a planned placement (not yet executed)."""
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO placements(file_hash, source_path, target_path, operation, done)
                VALUES(?,?,?,?,0)
                ON CONFLICT(file_hash) DO UPDATE SET
                    source_path=excluded.source_path,
                    target_path=excluded.target_path,
                    operation=excluded.operation
                """,
                (file_hash, str(source), str(target), operation),
            )
            self._conn.commit()

    def mark_placed(self, file_hash: str) -> None:
        """Mark a placement as completed (used by the resume logic)."""
        with self._lock:
            self._conn.execute(
                "UPDATE placements SET done = 1, placed_at = ? WHERE file_hash = ?",
                (_dt_to_str(datetime.now()), file_hash),
            )
            self._conn.commit()

    def is_placed(self, file_hash: str) -> bool:
        """Return ``True`` if the file has already been placed."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT done FROM placements WHERE file_hash = ?", (file_hash,)
            )
            row = cur.fetchone()
            return bool(row and row["done"])

    def pending_placements(self) -> list[tuple[str, Path, Path, str]]:
        """Return placements that still need to be executed."""
        with self._lock:
            cur = self._conn.execute(
                "SELECT file_hash, source_path, target_path, operation "
                "FROM placements WHERE done = 0"
            )
            rows = cur.fetchall()
        return [
            (r["file_hash"], Path(r["source_path"]), Path(r["target_path"]), r["operation"])
            for r in rows
        ]

    def clear_placements(self) -> None:
        """Remove all placement records (e.g. before planning a fresh run)."""
        with self._lock:
            self._conn.execute("DELETE FROM placements")
            self._conn.commit()


# --------------------------------------------------------------------------- #
# Row <-> model conversion helpers.
# --------------------------------------------------------------------------- #
def _analysis_to_dict(a: ImageAnalysis) -> dict[str, Any]:
    return {
        "scene": a.scene,
        "description": a.description,
        "tags": a.tags,
        "objects": a.objects,
        "activities": a.activities,
        "is_indoor": a.is_indoor,
        "is_daytime": a.is_daytime,
        "estimated_date": _dt_to_str(a.estimated_date),
        "embedding": a.embedding,
    }


def _dict_to_analysis(d: dict[str, Any]) -> ImageAnalysis:
    return ImageAnalysis(
        scene=d.get("scene"),
        description=d.get("description"),
        tags=list(d.get("tags") or []),
        objects=list(d.get("objects") or []),
        activities=list(d.get("activities") or []),
        is_indoor=d.get("is_indoor"),
        is_daytime=d.get("is_daytime"),
        estimated_date=_str_to_dt(d.get("estimated_date")),
        embedding=d.get("embedding"),
    )


def _geo_to_dict(g: GeoInfo) -> dict[str, Any]:
    return {
        "latitude": g.latitude,
        "longitude": g.longitude,
        "city": g.city,
        "region": g.region,
        "country": g.country,
        "landmark": g.landmark,
    }


def _dict_to_geo(d: dict[str, Any]) -> GeoInfo:
    return GeoInfo(
        latitude=d["latitude"],
        longitude=d["longitude"],
        city=d.get("city"),
        region=d.get("region"),
        country=d.get("country"),
        landmark=d.get("landmark"),
    )


def _row_to_media(row: sqlite3.Row) -> MediaFile:
    analysis = None
    if row["analysis_json"]:
        analysis = _dict_to_analysis(json.loads(row["analysis_json"]))
    geo = None
    if row["geo_json"]:
        geo = _dict_to_geo(json.loads(row["geo_json"]))
    return MediaFile(
        path=Path(row["path"]),
        kind=MediaKind(row["kind"]),
        size=row["size"],
        file_hash=row["file_hash"],
        capture_date=_str_to_dt(row["capture_date"]),
        date_source=DateSource(row["date_source"]) if row["date_source"] else DateSource.UNKNOWN,
        geo=geo,
        camera_model=row["camera_model"],
        face_count=row["face_count"] or 0,
        analysis=analysis,
        event_id=row["event_id"],
        analyzed_at=_str_to_dt(row["analyzed_at"]),
    )
