"""Helpers to load and encode images for vision models."""

from __future__ import annotations

import base64
import io
from pathlib import Path

__all__ = ["encode_image_base64", "load_downscaled_jpeg"]


def load_downscaled_jpeg(path: str | Path, max_size: int) -> bytes:
    """Return JPEG bytes of *path*, down-scaled so its longest edge <= *max_size*.

    HEIC/RAW/PNG inputs are converted to RGB JPEG. This keeps request payloads
    small and uniform across backends. Requires Pillow (a core dependency).
    """
    from PIL import Image

    with Image.open(path) as opened:
        rgb = opened.convert("RGB")
        longest = max(rgb.size)
        if longest > max_size:
            scale = max_size / float(longest)
            new_size = (max(1, int(rgb.width * scale)), max(1, int(rgb.height * scale)))
            rgb = rgb.resize(new_size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        rgb.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()


def encode_image_base64(path: str | Path, max_size: int) -> str:
    """Return a base64-encoded, down-scaled JPEG string for *path*."""
    return base64.b64encode(load_downscaled_jpeg(path, max_size)).decode("ascii")
