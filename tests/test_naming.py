"""Tests for event naming and filesystem-name utilities."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from photo_organizer.clustering.naming import EventNamer
from photo_organizer.models import GeoInfo, ImageAnalysis, MediaFile, MediaKind
from photo_organizer.organizer.naming_utils import month_folder, sanitize_name


def _media(
    when: datetime | None = None, *, city: str | None = None, tags: list[str] | None = None
) -> MediaFile:
    geo = GeoInfo(latitude=1.0, longitude=2.0, city=city) if city else None
    analysis = ImageAnalysis(tags=tags or []) if tags else None
    return MediaFile(
        path=Path("x.jpg"),
        kind=MediaKind.PHOTO,
        size=1,
        file_hash="h",
        capture_date=when,
        geo=geo,
        analysis=analysis,
    )


def test_generic_fallback_when_no_signal() -> None:
    namer = EventNamer("de")
    assert namer.name([_media()], 3) == "Event 03"


def test_holiday_naming_christmas() -> None:
    namer = EventNamer("de")
    name = namer.name([_media(datetime(2023, 12, 24))], 1)
    assert "Weihnachten" in name


def test_location_and_scene() -> None:
    namer = EventNamer("de")
    files = [_media(datetime(2023, 7, 1), city="Palma", tags=["beach"]) for _ in range(3)]
    name = namer.name(files, 1)
    assert "Palma" in name
    assert "Strand" in name


def test_sanitize_windows_invalid_chars() -> None:
    assert sanitize_name("a<b>c") == "a b c"
    assert ":" not in sanitize_name("Trip: Rome")
    assert sanitize_name("   ...   ", fallback="Event") == "Event"
    assert sanitize_name("CON") == "_CON"


def test_month_folder() -> None:
    assert month_folder(7, "de") == "07 Juli"
    assert month_folder(1, "en") == "01 January"
    assert month_folder(13, "de") == "12 Dezember"
