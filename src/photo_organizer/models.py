"""Core domain models shared across the pipeline.

These dataclasses are deliberately framework-agnostic (no Qt, no SQLite types)
so they can be used from the CLI, the GUI and the tests interchangeably.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path

__all__ = [
    "DateSource",
    "Event",
    "GeoInfo",
    "ImageAnalysis",
    "MediaFile",
    "MediaKind",
]


class MediaKind(StrEnum):
    """Whether a media file is a photo or a video."""

    PHOTO = "photo"
    VIDEO = "video"


class DateSource(StrEnum):
    """Where a media file's capture date was determined from.

    Ordered by descending trust; see
    :mod:`photo_organizer.media.date_extractor`.
    """

    EXIF_DATE = "exif_date"
    DATETIME_ORIGINAL = "datetime_original"
    MEDIA_CREATION = "media_creation"
    GPS_TIMESTAMP = "gps_timestamp"
    FILENAME = "filename"
    FILESYSTEM = "filesystem"
    AI_ESTIMATE = "ai_estimate"
    UNKNOWN = "unknown"


@dataclass
class GeoInfo:
    """Geographic information derived from GPS coordinates."""

    latitude: float
    longitude: float
    city: str | None = None
    region: str | None = None
    country: str | None = None
    landmark: str | None = None

    def label(self) -> str | None:
        """Return the most specific human-readable location label available."""
        return self.landmark or self.city or self.region or self.country


@dataclass
class ImageAnalysis:
    """Structured result of a vision-model analysis of a single image."""

    scene: str | None = None
    description: str | None = None
    tags: list[str] = field(default_factory=list)
    objects: list[str] = field(default_factory=list)
    activities: list[str] = field(default_factory=list)
    is_indoor: bool | None = None
    is_daytime: bool | None = None
    estimated_date: datetime | None = None
    # Optional visual embedding for similarity clustering.
    embedding: list[float] | None = None
    raw_response: str | None = None

    def keywords(self) -> list[str]:
        """Return a de-duplicated, ordered list of all descriptive keywords."""
        seen: dict[str, None] = {}
        for value in (self.scene, *self.tags, *self.objects, *self.activities):
            if value:
                seen.setdefault(value.strip().lower(), None)
        return list(seen)


@dataclass
class MediaFile:
    """A single photo or video together with all extracted metadata."""

    path: Path
    kind: MediaKind
    size: int
    file_hash: str
    capture_date: datetime | None = None
    date_source: DateSource = DateSource.UNKNOWN
    geo: GeoInfo | None = None
    camera_model: str | None = None
    face_count: int = 0
    analysis: ImageAnalysis | None = None
    event_id: int | None = None
    analyzed_at: datetime | None = None

    @property
    def extension(self) -> str:
        """Lower-case file extension without the leading dot."""
        return self.path.suffix.lower().lstrip(".")

    @property
    def is_video(self) -> bool:
        """Return ``True`` for video files."""
        return self.kind is MediaKind.VIDEO


@dataclass
class Event:
    """A cluster of media files that belong to the same real-world event."""

    event_id: int
    name: str
    files: list[MediaFile] = field(default_factory=list)
    description: str | None = None

    @property
    def start(self) -> datetime | None:
        """Earliest capture date within the event, if known."""
        dates = [f.capture_date for f in self.files if f.capture_date]
        return min(dates) if dates else None

    @property
    def end(self) -> datetime | None:
        """Latest capture date within the event, if known."""
        dates = [f.capture_date for f in self.files if f.capture_date]
        return max(dates) if dates else None

    @property
    def size(self) -> int:
        """Number of media files in the event."""
        return len(self.files)
