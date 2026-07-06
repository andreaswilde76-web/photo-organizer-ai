"""Abstract base class for all vision backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

from ..models import ImageAnalysis

__all__ = ["VisionModel"]


class VisionModel(ABC):
    """Interface every vision backend must implement.

    Implementations should be safe to call from multiple threads and must never
    raise for ordinary "the model could not answer" situations - they should
    return an empty :class:`ImageAnalysis` / ``None`` instead, so the pipeline
    keeps running over large collections.
    """

    #: Human-readable backend name, e.g. ``"ollama"``.
    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Return ``True`` if the backend is reachable and usable."""

    @abstractmethod
    def analyze_image(self, image_path: Path) -> ImageAnalysis:
        """Analyse a single image and return structured tags/description."""

    @abstractmethod
    def estimate_date(self, image_path: Path) -> datetime | None:
        """Estimate the likely capture date from image content, or ``None``."""

    @abstractmethod
    def describe_event(self, keywords: list[str], location: str | None = None) -> str | None:
        """Produce a one-sentence description for an event from *keywords*."""

    def close(self) -> None:  # pragma: no cover - optional override
        """Release any resources held by the backend."""
        return None
