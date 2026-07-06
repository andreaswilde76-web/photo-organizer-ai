"""Tests for the SQLite cache/persistence layer."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from photo_organizer.database import Database
from photo_organizer.models import (
    DateSource,
    GeoInfo,
    ImageAnalysis,
    MediaFile,
    MediaKind,
)


def _media() -> MediaFile:
    return MediaFile(
        path=Path("/photos/a.jpg"),
        kind=MediaKind.PHOTO,
        size=123,
        file_hash="hash-1",
        capture_date=datetime(2023, 6, 1, 12, 0),
        date_source=DateSource.DATETIME_ORIGINAL,
        geo=GeoInfo(latitude=52.5, longitude=13.4, city="Berlin", country="DE"),
        camera_model="TestCam",
        face_count=2,
        analysis=ImageAnalysis(scene="city", description="A city scene", tags=["street"]),
    )


def test_upsert_and_load_roundtrip(tmp_path: Path) -> None:
    with Database(tmp_path / "c.sqlite") as db:
        media = _media()
        db.upsert_media(media, exif={"Model": "TestCam"}, persons=["p1"])
        assert db.has_analysis("hash-1")
        loaded = db.load_media("hash-1")
        assert loaded is not None
        assert loaded.file_hash == "hash-1"
        assert loaded.capture_date == datetime(2023, 6, 1, 12, 0)
        assert loaded.geo is not None and loaded.geo.city == "Berlin"
        assert loaded.analysis is not None and loaded.analysis.scene == "city"
        assert loaded.face_count == 2


def test_update_event(tmp_path: Path) -> None:
    with Database(tmp_path / "c.sqlite") as db:
        db.upsert_media(_media())
        db.update_event("hash-1", 42)
        loaded = db.load_media("hash-1")
        assert loaded is not None and loaded.event_id == 42


def test_placements_resume_flow(tmp_path: Path) -> None:
    with Database(tmp_path / "c.sqlite") as db:
        db.record_placement("h", Path("/a.jpg"), Path("/out/a.jpg"), "copy")
        assert not db.is_placed("h")
        assert len(db.pending_placements()) == 1
        db.mark_placed("h")
        assert db.is_placed("h")
        assert db.pending_placements() == []


def test_missing_hash_returns_none(tmp_path: Path) -> None:
    with Database(tmp_path / "c.sqlite") as db:
        assert db.load_media("nope") is None
        assert not db.has_analysis("nope")
