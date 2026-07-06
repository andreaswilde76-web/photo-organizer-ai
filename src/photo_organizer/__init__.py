"""PhotoOrganizer AI.

A fully local, AI-assisted tool that analyses a photo/video collection and
sorts it into a ``Year/Month/Event`` folder structure.

The package is intentionally modular so that every heavy or optional component
(vision model, geocoding, face detection, GUI) can be swapped or disabled
without affecting the core pipeline.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
