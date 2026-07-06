"""Tests for the capture-date resolution pipeline."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from photo_organizer.media.date_extractor import DateExtractor
from photo_organizer.media.metadata import ExtractedMetadata
from photo_organizer.models import DateSource


def test_prefers_datetime_original(tmp_path: Path) -> None:
    path = tmp_path / "IMG_1234.jpg"
    path.write_bytes(b"x")
    meta = ExtractedMetadata(
        datetime_original=datetime(2021, 5, 1, 12, 0),
        media_creation=datetime(2010, 1, 1),
    )
    result = DateExtractor().resolve(path, meta)
    assert result.source is DateSource.DATETIME_ORIGINAL
    assert result.date == datetime(2021, 5, 1, 12, 0)


def test_falls_back_to_media_creation(tmp_path: Path) -> None:
    path = tmp_path / "clip.mp4"
    path.write_bytes(b"x")
    meta = ExtractedMetadata(media_creation=datetime(2019, 3, 3, 9, 0))
    result = DateExtractor().resolve(path, meta)
    assert result.source is DateSource.MEDIA_CREATION


def test_filename_ymd_hms() -> None:
    dt = DateExtractor()._from_filename(Path("2023-07-14_18-30-00_party.jpg"))
    assert dt == datetime(2023, 7, 14, 18, 30, 0)


def test_filename_img_compact() -> None:
    dt = DateExtractor()._from_filename(Path("IMG_20230714_183000.jpg"))
    assert dt == datetime(2023, 7, 14, 18, 30, 0)


def test_filename_date_only() -> None:
    dt = DateExtractor()._from_filename(Path("20220101_stuff.png"))
    assert dt == datetime(2022, 1, 1)


def test_filename_rejects_implausible() -> None:
    assert DateExtractor()._from_filename(Path("18990101.jpg")) is None


def test_filesystem_fallback(tmp_path: Path) -> None:
    path = tmp_path / "no_date_here.jpg"
    path.write_bytes(b"x")
    result = DateExtractor().resolve(path, ExtractedMetadata())
    assert result.source is DateSource.FILESYSTEM
    assert result.date is not None
