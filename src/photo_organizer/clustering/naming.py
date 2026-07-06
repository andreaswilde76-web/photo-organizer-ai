"""Derive human-friendly event names from clustered media.

Naming combines several deterministic signals so it works even without an AI
model available:

* **Holidays** detected from the date (Christmas, New Year, ...).
* **Location** from reverse-geocoded GPS (city / landmark).
* **Dominant scene** from vision tags (beach, mountains, restaurant, ...).

When nothing meaningful can be derived, a generic ``Event NN`` name is used.
Names are localisable; German (``de``) and English (``en``) are bundled.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from ..logging_setup import get_logger
from ..models import MediaFile

__all__ = ["EventNamer"]

_LOG = get_logger("clustering.naming")

# Map canonical scene keywords to localised, human-friendly labels.
_SCENE_LABELS: dict[str, dict[str, str]] = {
    "beach": {"de": "Strand", "en": "Beach"},
    "strand": {"de": "Strand", "en": "Beach"},
    "mountains": {"de": "Berge", "en": "Mountains"},
    "berge": {"de": "Berge", "en": "Mountains"},
    "hiking": {"de": "Wanderung", "en": "Hiking"},
    "wandern": {"de": "Wanderung", "en": "Hiking"},
    "snow": {"de": "Schnee", "en": "Snow"},
    "forest": {"de": "Wald", "en": "Forest"},
    "wald": {"de": "Wald", "en": "Forest"},
    "restaurant": {"de": "Restaurant", "en": "Restaurant"},
    "food": {"de": "Essen", "en": "Food"},
    "gym": {"de": "Fitnessstudio", "en": "Gym"},
    "fitness": {"de": "Fitnessstudio", "en": "Gym"},
    "concert": {"de": "Konzert", "en": "Concert"},
    "sport": {"de": "Sport", "en": "Sport"},
    "wedding": {"de": "Hochzeit", "en": "Wedding"},
    "birthday": {"de": "Geburtstag", "en": "Birthday"},
    "pets": {"de": "Haustiere", "en": "Pets"},
    "pet": {"de": "Haustiere", "en": "Pets"},
    "city": {"de": "Stadt", "en": "City"},
    "home": {"de": "Zuhause", "en": "Home"},
    "sunset": {"de": "Sonnenuntergang", "en": "Sunset"},
    "park": {"de": "Park", "en": "Park"},
    "vacation": {"de": "Urlaub", "en": "Vacation"},
    "travel": {"de": "Reise", "en": "Travel"},
}

_HOLIDAY_LABELS = {
    "christmas": {"de": "Weihnachten", "en": "Christmas"},
    "new_year": {"de": "Silvester", "en": "New Year"},
    "halloween": {"de": "Halloween", "en": "Halloween"},
    "easter_hint": {"de": "Ostern", "en": "Easter"},
}


def _detect_holiday(date: datetime) -> str | None:
    """Return a holiday key for well-known fixed-date holidays, else ``None``."""
    month, day = date.month, date.day
    if month == 12 and 23 <= day <= 26:
        return "christmas"
    if (month == 12 and day >= 31) or (month == 1 and day == 1):
        return "new_year"
    if month == 10 and day == 31:
        return "halloween"
    return None


class EventNamer:
    """Produce localised, meaningful names for events."""

    def __init__(self, language: str = "de", min_cluster_size: int = 1) -> None:
        self._language = language if language in {"de", "en"} else "en"
        self._min_cluster_size = min_cluster_size

    def _loc(self, table: dict[str, dict[str, str]], key: str) -> str | None:
        entry = table.get(key)
        return entry.get(self._language) if entry else None

    def name(self, files: list[MediaFile], index: int) -> str:
        """Return the best name for the event made of *files*.

        *index* is the 1-based position used for the generic ``Event NN``
        fallback.
        """
        generic = f"Event {index:02d}"
        if not files:
            return generic
        if len(files) < self._min_cluster_size:
            return generic

        location = self._dominant_location(files)
        scene = self._dominant_scene(files)
        holiday = self._dominant_holiday(files)

        parts: list[str] = []
        if holiday:
            parts.append(holiday)
        if location:
            parts.append(location)
        if scene and scene != location:
            parts.append(scene)

        # Deduplicate while keeping order.
        seen: dict[str, None] = {}
        for part in parts:
            seen.setdefault(part, None)
        name = " ".join(seen)
        return name.strip() or generic

    # -- signal extraction ------------------------------------------------ #
    def _dominant_location(self, files: list[MediaFile]) -> str | None:
        labels: Counter[str] = Counter()
        for media in files:
            if media.geo:
                label = media.geo.landmark or media.geo.city or media.geo.country
                if label:
                    labels[label] += 1
        if not labels:
            return None
        return labels.most_common(1)[0][0]

    def _dominant_scene(self, files: list[MediaFile]) -> str | None:
        counter: Counter[str] = Counter()
        for media in files:
            if not media.analysis:
                continue
            for keyword in media.analysis.keywords():
                label = self._loc(_SCENE_LABELS, keyword)
                if label:
                    counter[label] += 1
        if not counter:
            return None
        return counter.most_common(1)[0][0]

    def _dominant_holiday(self, files: list[MediaFile]) -> str | None:
        counter: Counter[str] = Counter()
        for media in files:
            if media.capture_date:
                key = _detect_holiday(media.capture_date)
                if key:
                    counter[key] += 1
        if not counter:
            return None
        key = counter.most_common(1)[0][0]
        return self._loc(_HOLIDAY_LABELS, key)
