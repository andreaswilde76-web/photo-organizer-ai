"""Offline reverse geocoding from GPS coordinates.

Uses the optional ``reverse_geocoder`` package, which ships an offline dataset -
so it works without any network access, satisfying the "fully local" goal. When
the package is not installed the geocoder degrades to a no-op that leaves the
coordinates in place.
"""

from __future__ import annotations

from ..logging_setup import get_logger
from ..models import GeoInfo

__all__ = ["ReverseGeocoder"]

_LOG = get_logger("geo.geocoding")


class ReverseGeocoder:
    """Resolve city/region/country for GPS coordinates, fully offline."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._impl = None
        if enabled:
            try:
                import reverse_geocoder

                self._impl = reverse_geocoder
            except ImportError:
                _LOG.info(
                    "reverse_geocoder not installed; install extra .[geo] for "
                    "offline city/country lookup."
                )
                self._enabled = False

    @property
    def available(self) -> bool:
        """Return ``True`` if offline geocoding is usable."""
        return self._enabled and self._impl is not None

    def enrich(self, geo: GeoInfo) -> GeoInfo:
        """Return *geo* enriched with city/region/country in-place.

        The passed :class:`GeoInfo` is mutated and also returned for
        convenience. Failures leave the coordinates untouched.
        """
        if not self.available:
            return geo
        try:
            # mode=1 uses a single-threaded, in-process KD-tree lookup.
            results = self._impl.search((geo.latitude, geo.longitude), mode=1)  # type: ignore[union-attr]
            if results:
                hit = results[0]
                geo.city = hit.get("name") or geo.city
                geo.region = hit.get("admin1") or geo.region
                geo.country = hit.get("cc") or geo.country
        except Exception as exc:
            _LOG.debug(
                "Reverse geocoding failed for (%s, %s): %s", geo.latitude, geo.longitude, exc
            )
        return geo
