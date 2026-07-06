"""Content hashing used for cache keys and duplicate detection."""

from __future__ import annotations

import hashlib
from pathlib import Path

__all__ = ["hash_file"]

_CHUNK = 1024 * 1024  # 1 MiB


def hash_file(path: str | Path, *, algorithm: str = "sha256", partial: bool = False) -> str:
    """Return the hex digest of *path*.

    Parameters
    ----------
    path:
        File to hash.
    algorithm:
        Any algorithm supported by :mod:`hashlib` (default ``sha256``).
    partial:
        When ``True`` only the first and last chunk plus the file size are
        hashed. This is much faster for very large videos while still being an
        excellent cache key. Full hashing is the default for correctness.
    """
    p = Path(path)
    hasher = hashlib.new(algorithm)
    size = p.stat().st_size
    with p.open("rb") as fh:
        if partial and size > 3 * _CHUNK:
            hasher.update(fh.read(_CHUNK))
            fh.seek(-_CHUNK, 2)
            hasher.update(fh.read(_CHUNK))
            hasher.update(str(size).encode("ascii"))
        else:
            for chunk in iter(lambda: fh.read(_CHUNK), b""):
                hasher.update(chunk)
    return hasher.hexdigest()
