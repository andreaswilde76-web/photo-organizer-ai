"""A no-op vision backend used when AI analysis is disabled.

It lets the whole pipeline run purely on metadata + clustering, which is useful
for tests, offline environments, or when a user only wants date-based sorting.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..models import ImageAnalysis
from .base import VisionModel

__all__ = ["NullVisionModel"]


class NullVisionModel(VisionModel):
    """A backend that returns empty results for every request."""

    name = "null"

    def is_available(self) -> bool:
        return True

    def analyze_image(self, image_path: Path) -> ImageAnalysis:
        return ImageAnalysis()

    def estimate_date(self, image_path: Path) -> datetime | None:
        return None

    def describe_event(self, keywords: list[str], location: str | None = None) -> str | None:
        return None
