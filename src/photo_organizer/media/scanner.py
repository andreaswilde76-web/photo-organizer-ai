"""Discover media files inside the source directory."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from ..config import MediaConfig
from ..logging_setup import get_logger
from ..models import MediaKind

__all__ = ["MediaScanner"]

_LOG = get_logger("media.scanner")


class MediaScanner:
    """Walk a source directory and yield candidate media files."""

    def __init__(self, config: MediaConfig) -> None:
        self._config = config
        self._photo_ext = {e.lower() for e in config.photo_extensions}
        self._video_ext = {e.lower() for e in config.video_extensions}
        self._all_ext = self._photo_ext | self._video_ext

    def kind_for(self, path: Path) -> MediaKind | None:
        """Return the :class:`MediaKind` for *path* or ``None`` if unsupported."""
        ext = path.suffix.lower().lstrip(".")
        if ext in self._video_ext:
            return MediaKind.VIDEO
        if ext in self._photo_ext:
            return MediaKind.PHOTO
        return None

    def scan(self, source: str | Path) -> Iterator[tuple[Path, MediaKind]]:
        """Yield ``(path, kind)`` tuples for every supported media file.

        Hidden files and files below ``min_file_size`` are skipped. Errors while
        stat-ing individual files are logged and skipped rather than aborting the
        whole scan.
        """
        root = Path(source)
        if not root.is_dir():
            raise NotADirectoryError(f"Source directory does not exist: {root}")

        iterator = root.rglob("*") if self._config.recursive else root.glob("*")
        for path in iterator:
            try:
                if not path.is_file() or path.name.startswith("."):
                    continue
                kind = self.kind_for(path)
                if kind is None:
                    continue
                if path.stat().st_size < self._config.min_file_size:
                    _LOG.debug("Skipping tiny file: %s", path)
                    continue
                yield path, kind
            except OSError as exc:  # pragma: no cover - filesystem edge cases
                _LOG.warning("Could not access %s: %s", path, exc)

    def count(self, source: str | Path) -> int:
        """Return the number of supported files (used for progress bars)."""
        return sum(1 for _ in self.scan(source))
