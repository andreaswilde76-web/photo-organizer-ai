"""Shared pytest fixtures and helpers."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture
def make_image(tmp_path: Path) -> Callable[..., Path]:
    """Return a factory that writes a JPEG/PNG file (>1 KiB) and returns its path.

    The image is filled with random noise so the encoded file comfortably exceeds
    the scanner's default ``min_file_size`` threshold.
    """

    def _factory(name: str, *, size: tuple[int, int] = (256, 256)) -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        noise = os.urandom(size[0] * size[1] * 3)
        img = Image.frombytes("RGB", size, noise)
        fmt = "PNG" if path.suffix.lower() == ".png" else "JPEG"
        img.save(path, format=fmt)
        return path

    return _factory
