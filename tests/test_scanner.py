"""Tests for the media scanner."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from photo_organizer.config import MediaConfig
from photo_organizer.media.scanner import MediaScanner
from photo_organizer.models import MediaKind


def test_scan_finds_supported_files(make_image: Callable[..., Path], tmp_path: Path) -> None:
    make_image("a.jpg")
    make_image("sub/b.png")
    (tmp_path / "notes.txt").write_text("ignore me")
    (tmp_path / "clip.mp4").write_bytes(b"\x00" * 2048)

    scanner = MediaScanner(MediaConfig())
    found = dict(scanner.scan(tmp_path))
    names = {p.name for p in found}
    assert "a.jpg" in names
    assert "b.png" in names
    assert "clip.mp4" in names
    assert "notes.txt" not in names
    assert found[tmp_path / "clip.mp4"] is MediaKind.VIDEO


def test_min_file_size_skips_tiny(make_image: Callable[..., Path], tmp_path: Path) -> None:
    tiny = tmp_path / "tiny.jpg"
    tiny.write_bytes(b"x")  # below default min_file_size
    scanner = MediaScanner(MediaConfig())
    assert tiny not in dict(scanner.scan(tmp_path))


def test_scan_missing_dir_raises(tmp_path: Path) -> None:
    scanner = MediaScanner(MediaConfig())
    with pytest.raises(NotADirectoryError):
        list(scanner.scan(tmp_path / "nope"))


def test_count(make_image: Callable[..., Path], tmp_path: Path) -> None:
    make_image("a.jpg")
    make_image("b.jpg")
    assert MediaScanner(MediaConfig()).count(tmp_path) == 2
