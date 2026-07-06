"""Swappable AI vision backends.

All backends implement :class:`~photo_organizer.ai.base.VisionModel`. Use
:func:`~photo_organizer.ai.factory.create_vision_model` to instantiate the one
selected in the configuration.
"""

from __future__ import annotations

from .base import VisionModel
from .factory import create_vision_model

__all__ = ["VisionModel", "create_vision_model"]
