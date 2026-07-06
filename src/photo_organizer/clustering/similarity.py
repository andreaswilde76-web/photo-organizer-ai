"""Similarity / distance helpers used by the event clusterer."""

from __future__ import annotations

import math

from ..models import MediaFile

__all__ = ["haversine_km", "visual_similarity"]

_EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance between two points in kilometres."""
    r_lat1, r_lat2 = math.radians(lat1), math.radians(lat2)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_lat / 2) ** 2 + math.cos(r_lat1) * math.cos(r_lat2) * math.sin(d_lon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def visual_similarity(first: MediaFile, second: MediaFile) -> float:
    """Return a 0..1 visual similarity between two media files.

    Prefers cosine similarity of vision embeddings when available; otherwise
    falls back to a keyword (scene/tags/objects) Jaccard overlap. Returns a
    neutral 0.5 when neither file has visual information.
    """
    fa, sa = first.analysis, second.analysis
    if fa is None or sa is None:
        return 0.5
    if fa.embedding and sa.embedding:
        return max(0.0, _cosine(fa.embedding, sa.embedding))
    ka, kb = set(fa.keywords()), set(sa.keywords())
    if not ka and not kb:
        return 0.5
    return _jaccard(ka, kb)
