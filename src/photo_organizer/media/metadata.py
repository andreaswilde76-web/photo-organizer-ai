"""Extract EXIF / container metadata from photos and videos.

Photo EXIF is read with Pillow (with ``pillow-heif`` registered for HEIC). Video
creation dates are read from the container where possible using only the standard
library, so no external ``ffmpeg``/``exiftool`` binary is required (though the
result improves when they are present). Everything degrades gracefully: missing
or unreadable metadata simply yields ``None`` values.
"""

from __future__ import annotations

import contextlib
import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..logging_setup import get_logger
from ..models import GeoInfo

__all__ = ["ExtractedMetadata", "MetadataExtractor"]

_LOG = get_logger("media.metadata")

# Register HEIC support for Pillow if available.
try:  # pragma: no cover - depends on optional dependency
    import pillow_heif

    pillow_heif.register_heif_opener()
    _HEIF_OK = True
except Exception:
    _HEIF_OK = False


@dataclass
class ExtractedMetadata:
    """Container for all metadata extracted from a single file."""

    datetime_original: datetime | None = None
    media_creation: datetime | None = None
    gps_timestamp: datetime | None = None
    geo: GeoInfo | None = None
    camera_model: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class MetadataExtractor:
    """Extract capture-relevant metadata from photos and videos."""

    def extract(self, path: Path, *, is_video: bool) -> ExtractedMetadata:
        """Return :class:`ExtractedMetadata` for *path*.

        Any failure is caught and results in an empty/partial result rather than
        raising, because a single unreadable file must never abort a large run.
        """
        try:
            if is_video:
                return self._extract_video(path)
            return self._extract_photo(path)
        except Exception as exc:
            _LOG.debug("Metadata extraction failed for %s: %s", path, exc)
            return ExtractedMetadata()

    # -- photos ----------------------------------------------------------- #
    def _extract_photo(self, path: Path) -> ExtractedMetadata:
        from PIL import ExifTags, Image

        result = ExtractedMetadata()
        with Image.open(path) as img:
            exif = img.getexif()
            if not exif:
                return result

            tag_map = {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
            result.raw = {str(k): _stringify(v) for k, v in tag_map.items()}
            result.camera_model = _clean_str(tag_map.get("Model"))

            # DateTimeOriginal lives in the Exif IFD.
            dto = None
            with contextlib.suppress(Exception):
                exif_ifd = exif.get_ifd(ExifTags.IFD.Exif)
                if exif_ifd:
                    dto = exif_ifd.get(ExifTags.Base.DateTimeOriginal)
                    result.raw.update(
                        {str(ExifTags.TAGS.get(k, k)): _stringify(v) for k, v in exif_ifd.items()}
                    )
            dto = dto or tag_map.get("DateTimeOriginal")
            result.datetime_original = _parse_exif_datetime(dto)

            # Fall back to plain DateTime tag as a media-creation hint.
            result.media_creation = _parse_exif_datetime(tag_map.get("DateTime"))

            # GPS.
            with contextlib.suppress(Exception):
                gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo)
                if gps_ifd:
                    result.geo, result.gps_timestamp = _parse_gps(gps_ifd)
        return result

    # -- videos ----------------------------------------------------------- #
    def _extract_video(self, path: Path) -> ExtractedMetadata:
        result = ExtractedMetadata()
        ext = path.suffix.lower()
        if ext in {".mp4", ".mov", ".m4v"}:
            result.media_creation = _read_mp4_creation_time(path)
        return result


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _clean_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().strip("\x00")
    return text or None


def _stringify(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if isinstance(value, (tuple, list)):
        return [_stringify(v) for v in value]
    return value


def _parse_exif_datetime(value: Any) -> datetime | None:
    """Parse EXIF datetime strings like ``2023:07:14 18:30:00``."""
    if not value:
        return None
    text = str(value).strip().strip("\x00")
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y:%m:%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _dms_to_decimal(dms: Any, ref: Any) -> float | None:
    """Convert an EXIF (degrees, minutes, seconds) tuple to decimal degrees."""
    try:
        degrees = _to_float(dms[0]) or 0.0
        minutes = _to_float(dms[1]) or 0.0
        seconds = _to_float(dms[2]) or 0.0
    except (TypeError, IndexError):
        return None
    decimal = degrees + minutes / 60.0 + seconds / 3600.0
    if ref and str(ref).upper() in {"S", "W"}:
        decimal = -decimal
    return decimal


def _parse_gps(gps_ifd: dict[int, Any]) -> tuple[GeoInfo | None, datetime | None]:
    """Parse the GPS IFD into a :class:`GeoInfo` and optional timestamp."""
    from PIL.ExifTags import GPS

    lat = _dms_to_decimal(gps_ifd.get(GPS.GPSLatitude), gps_ifd.get(GPS.GPSLatitudeRef))
    lon = _dms_to_decimal(gps_ifd.get(GPS.GPSLongitude), gps_ifd.get(GPS.GPSLongitudeRef))
    geo = None
    if lat is not None and lon is not None and not (lat == 0.0 and lon == 0.0):
        geo = GeoInfo(latitude=lat, longitude=lon)

    timestamp: datetime | None = None
    date_stamp = gps_ifd.get(GPS.GPSDateStamp)
    time_stamp = gps_ifd.get(GPS.GPSTimeStamp)
    if date_stamp and time_stamp:
        with contextlib.suppress(Exception):
            d = datetime.strptime(str(date_stamp).strip(), "%Y:%m:%d")
            hours = int(_to_float(time_stamp[0]) or 0)
            minutes = int(_to_float(time_stamp[1]) or 0)
            seconds = int(_to_float(time_stamp[2]) or 0)
            timestamp = d.replace(hour=hours, minute=minutes, second=seconds)
    return geo, timestamp


# QuickTime/MP4 epoch is 1904-01-01; convert to Unix by subtracting these secs.
_MP4_EPOCH_OFFSET = 2082844800


def _read_mp4_creation_time(path: Path) -> datetime | None:
    """Read the creation time from an MP4/MOV ``mvhd`` atom (stdlib only)."""
    try:
        with path.open("rb") as fh:
            data = fh.read(64 * 1024)
        idx = data.find(b"mvhd")
        if idx == -1:
            return None
        version = data[idx + 4]
        if version == 1:
            raw = data[idx + 12 : idx + 20]
            seconds = struct.unpack(">Q", raw)[0]
        else:
            raw = data[idx + 8 : idx + 12]
            seconds = struct.unpack(">I", raw)[0]
        if seconds <= _MP4_EPOCH_OFFSET:
            return None
        return datetime(1904, 1, 1) + timedelta(seconds=seconds)
    except (OSError, struct.error):  # pragma: no cover - defensive
        return None
