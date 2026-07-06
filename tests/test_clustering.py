"""Tests for event clustering and similarity helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from photo_organizer.clustering.event_clusterer import EventClusterer
from photo_organizer.clustering.similarity import haversine_km, visual_similarity
from photo_organizer.config import ClusteringConfig
from photo_organizer.models import GeoInfo, ImageAnalysis, MediaFile, MediaKind


def _media(
    name: str,
    when: datetime | None,
    *,
    lat: float | None = None,
    lon: float | None = None,
    tags: list[str] | None = None,
) -> MediaFile:
    geo = GeoInfo(latitude=lat, longitude=lon) if lat is not None and lon is not None else None
    analysis = ImageAnalysis(tags=tags or []) if tags else None
    return MediaFile(
        path=Path(name),
        kind=MediaKind.PHOTO,
        size=10,
        file_hash=name,
        capture_date=when,
        geo=geo,
        analysis=analysis,
    )


def test_haversine_known_distance() -> None:
    # Berlin -> Munich is roughly 504 km.
    d = haversine_km(52.52, 13.405, 48.137, 11.575)
    assert 480 < d < 520


def test_time_gap_splits_events() -> None:
    base = datetime(2023, 1, 1, 10, 0)
    files = [
        _media("a", base),
        _media("b", base + timedelta(minutes=30)),
        _media("c", base + timedelta(days=2)),
    ]
    clusters = EventClusterer(ClusteringConfig()).cluster(files)
    assert len(clusters) == 2
    assert [len(c) for c in clusters] == [2, 1]


def test_location_jump_splits_within_time_window() -> None:
    base = datetime(2023, 1, 1, 10, 0)
    files = [
        _media("a", base, lat=52.52, lon=13.405),
        _media("b", base + timedelta(minutes=10), lat=40.7, lon=-74.0),  # far away
    ]
    clusters = EventClusterer(ClusteringConfig(max_distance_km=25)).cluster(files)
    assert len(clusters) == 2


def test_undated_files_grouped_separately() -> None:
    base = datetime(2023, 1, 1, 10, 0)
    files = [_media("a", base), _media("b", None)]
    clusters = EventClusterer(ClusteringConfig()).cluster(files)
    assert clusters[-1][0].path.name == "b"


def test_visual_similarity_by_keywords() -> None:
    a = _media("a", None, tags=["beach", "sea"])
    b = _media("b", None, tags=["beach", "sea"])
    c = _media("c", None, tags=["gym", "indoor"])
    assert visual_similarity(a, b) > visual_similarity(a, c)
