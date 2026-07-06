"""Determine the most trustworthy capture date for a media file.

The resolution order requested by the specification is:

1. EXIF ``DateTimeOriginal``
2. EXIF ``DateTime`` / media creation date
3. Video media-creation date (container)
4. GPS timestamp
5. Date encoded in the file name
6. Filesystem modification time

If none of these yield a plausible date, the caller may fall back to a vision
model estimate (handled by the pipeline, recorded as
:attr:`DateSource.AI_ESTIMATE`).
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from ..logging_setup import get_logger
from ..models import DateSource
from .metadata import ExtractedMetadata

__all__ = ["DateExtractor", "DateResult"]

_LOG = get_logger("media.date_extractor")

# A future-proof sanity window; anything outside is rejected as implausible.
_MIN_YEAR = 1970
_MAX_YEAR = 2100

# Ordered filename patterns -> parsing format.
_FILENAME_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # 2023-07-14_18-30-00 / 20230714_183000 / 2023-07-14 18.30.00
    (
        re.compile(r"(20\d{2})[-_.]?(\d{2})[-_.]?(\d{2})[-_ T]?(\d{2})[-_.]?(\d{2})[-_.]?(\d{2})"),
        "ymdhms",
    ),
    # IMG_20230714_183000
    (re.compile(r"(20\d{2})(\d{2})(\d{2})[-_](\d{2})(\d{2})(\d{2})"), "ymdhms"),
    # 2023-07-14 (date only)
    (re.compile(r"(20\d{2})[-_.](\d{2})[-_.](\d{2})"), "ymd"),
    # 20230714 (compact date only, avoids matching random 8-digit ids poorly)
    (re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)"), "ymd"),
    # Unix-style epoch-ish is intentionally not parsed to avoid false hits.
)


class DateResult:
    """The chosen capture date together with its provenance."""

    __slots__ = ("date", "source")

    def __init__(self, date: datetime | None, source: DateSource) -> None:
        self.date = date
        self.source = source

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"DateResult(date={self.date!r}, source={self.source.value})"


def _plausible(dt: datetime | None) -> datetime | None:
    """Return *dt* only if it falls inside the plausible year window."""
    if dt is None:
        return None
    if _MIN_YEAR <= dt.year <= _MAX_YEAR:
        return dt
    return None


class DateExtractor:
    """Resolve a capture date from metadata, filename and filesystem info."""

    def resolve(self, path: Path, metadata: ExtractedMetadata) -> DateResult:
        """Return the best :class:`DateResult` for *path* / *metadata*."""
        candidates: list[tuple[datetime | None, DateSource]] = [
            (metadata.datetime_original, DateSource.DATETIME_ORIGINAL),
            (metadata.media_creation, DateSource.MEDIA_CREATION),
            (metadata.gps_timestamp, DateSource.GPS_TIMESTAMP),
            (self._from_filename(path), DateSource.FILENAME),
            (self._from_filesystem(path), DateSource.FILESYSTEM),
        ]
        for dt, source in candidates:
            plausible = _plausible(dt)
            if plausible is not None:
                return DateResult(plausible, source)
        return DateResult(None, DateSource.UNKNOWN)

    # -- individual sources ---------------------------------------------- #
    def _from_filename(self, path: Path) -> datetime | None:
        name = path.name
        for pattern, kind in _FILENAME_PATTERNS:
            match = pattern.search(name)
            if not match:
                continue
            groups = [int(g) for g in match.groups()]
            try:
                if kind == "ymdhms":
                    dt = datetime(*groups[:6])  # type: ignore[arg-type]
                else:
                    dt = datetime(groups[0], groups[1], groups[2])
            except ValueError:
                continue
            if _plausible(dt):
                return dt
        return None

    def _from_filesystem(self, path: Path) -> datetime | None:
        try:
            stat = path.stat()
        except OSError:  # pragma: no cover - defensive
            return None
        # st_mtime is the most reliable "content" timestamp cross-platform.
        return datetime.fromtimestamp(stat.st_mtime)
