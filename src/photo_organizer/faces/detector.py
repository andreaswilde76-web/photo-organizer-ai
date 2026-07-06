"""Face detection using the optional ``face_recognition`` library.

Only *detection* (counting faces) is implemented here. Face *recognition*
(clustering identities across photos) is intentionally left as a documented
extension point: :meth:`FaceDetector.encode` already returns face embeddings
that a future recognition step can cluster.
"""

from __future__ import annotations

from pathlib import Path

from ..config import FacesConfig
from ..logging_setup import get_logger

__all__ = ["FaceDetector"]

_LOG = get_logger("faces.detector")


class FaceDetector:
    """Detect (and optionally encode) faces in an image."""

    def __init__(self, config: FacesConfig) -> None:
        self._enabled = config.enabled
        self._impl = None
        if self._enabled:
            try:
                import face_recognition

                self._impl = face_recognition
            except ImportError:
                _LOG.info(
                    "face_recognition not installed; install extra .[faces] to "
                    "enable face detection."
                )
                self._enabled = False

    @property
    def available(self) -> bool:
        """Return ``True`` if face detection is usable."""
        return self._enabled and self._impl is not None

    def count_faces(self, image_path: Path) -> int:
        """Return the number of faces detected in *image_path* (0 on failure)."""
        if not self.available:
            return 0
        try:
            image = self._impl.load_image_file(str(image_path))  # type: ignore[union-attr]
            return len(self._impl.face_locations(image))  # type: ignore[union-attr]
        except Exception as exc:
            _LOG.debug("Face detection failed for %s: %s", image_path, exc)
            return 0

    def encode(self, image_path: Path) -> list[list[float]]:
        """Return face embeddings for future recognition (empty if unavailable)."""
        if not self.available:
            return []
        try:
            image = self._impl.load_image_file(str(image_path))  # type: ignore[union-attr]
            return [list(map(float, e)) for e in self._impl.face_encodings(image)]  # type: ignore[union-attr]
        except Exception as exc:
            _LOG.debug("Face encoding failed for %s: %s", image_path, exc)
            return []
