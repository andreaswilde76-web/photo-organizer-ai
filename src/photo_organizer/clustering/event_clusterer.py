"""Group media files into events by combining multiple signals.

The clusterer walks the media files in chronological order and decides, for each
consecutive pair, whether they belong to the same event. The decision combines:

* **temporal proximity** - the primary signal (time gap vs. ``max_time_gap``),
* **spatial proximity** - GPS distance vs. ``max_distance_km`` (a strong split
  signal: a large jump in location almost always means a new event),
* **visual/scene similarity** - vision tags/embeddings pull borderline photos
  together or push them apart (weighted by ``visual_weight``).

This "break-point" strategy is a form of temporal-constrained agglomerative
clustering and works well for personal photo libraries where events are
naturally ordered in time. Files without a capture date are grouped separately.
"""

from __future__ import annotations

from ..config import ClusteringConfig
from ..logging_setup import get_logger
from ..models import MediaFile
from .similarity import haversine_km, visual_similarity

__all__ = ["EventClusterer"]

_LOG = get_logger("clustering.event")


class EventClusterer:
    """Cluster media files into events using time, location and vision cues."""

    def __init__(self, config: ClusteringConfig) -> None:
        self._config = config

    def cluster(self, files: list[MediaFile]) -> list[list[MediaFile]]:
        """Return a list of clusters (each a list of :class:`MediaFile`).

        Dated files are clustered chronologically; undated files (no capture
        date at all) are returned as one trailing cluster so they are never
        silently dropped.
        """
        dated = sorted(
            (f for f in files if f.capture_date is not None),
            key=lambda f: f.capture_date,  # type: ignore[arg-type,return-value]
        )
        undated = [f for f in files if f.capture_date is None]

        clusters: list[list[MediaFile]] = []
        current: list[MediaFile] = []
        for media in dated:
            if not current:
                current = [media]
                continue
            if self._same_event(current[-1], media):
                current.append(media)
            else:
                clusters.append(current)
                current = [media]
        if current:
            clusters.append(current)

        if undated:
            clusters.append(undated)

        _LOG.info(
            "Clustered %d files into %d events (%d undated).",
            len(files),
            len(clusters),
            len(undated),
        )
        return clusters

    # -- decision -------------------------------------------------------- #
    def _same_event(self, previous: MediaFile, current: MediaFile) -> bool:
        """Return ``True`` if *current* belongs to the same event as *previous*."""
        assert previous.capture_date and current.capture_date  # dated by caller
        gap_hours = abs((current.capture_date - previous.capture_date).total_seconds()) / 3600.0

        # A large location jump is a hard split, regardless of time.
        if previous.geo and current.geo:
            distance = haversine_km(
                previous.geo.latitude,
                previous.geo.longitude,
                current.geo.latitude,
                current.geo.longitude,
            )
            if distance > self._config.max_distance_km:
                return False

        # Within the base time window: same event.
        if gap_hours <= self._config.max_time_gap_hours:
            return True

        # Beyond the window, strong visual similarity can still bridge a gap up
        # to twice the window (e.g. a multi-day trip photographed at one place).
        if gap_hours <= self._config.max_time_gap_hours * 2:
            similarity = visual_similarity(previous, current)
            score = similarity * self._config.visual_weight
            return score >= 0.35

        return False
