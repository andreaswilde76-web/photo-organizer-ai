"""Tests for content hashing."""

from __future__ import annotations

from pathlib import Path

from photo_organizer.hashing import hash_file


def test_hash_is_stable_and_content_sensitive(tmp_path: Path) -> None:
    a = tmp_path / "a.bin"
    b = tmp_path / "b.bin"
    a.write_bytes(b"hello world")
    b.write_bytes(b"hello world")
    assert hash_file(a) == hash_file(b)

    b.write_bytes(b"different")
    assert hash_file(a) != hash_file(b)


def test_partial_hash_large_file(tmp_path: Path) -> None:
    big = tmp_path / "big.bin"
    big.write_bytes(b"\x00" * (5 * 1024 * 1024) + b"tail")
    digest = hash_file(big, partial=True)
    assert len(digest) == 64  # sha256 hex length
