"""Build a preview plan mapping every media file to its target path."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..config import Config
from ..logging_setup import get_logger
from ..models import Event, MediaFile
from .naming_utils import month_folder, sanitize_name

__all__ = ["OrganizePlan", "PlanEntry", "Planner"]

_LOG = get_logger("organizer.planner")

_UNKNOWN_YEAR = {"de": "Unbekannt", "en": "Unknown"}


@dataclass
class PlanEntry:
    """A single planned placement of a media file."""

    media: MediaFile
    source: Path
    target: Path
    event_name: str


@dataclass
class OrganizePlan:
    """A full, reviewable plan for re-organising a collection."""

    entries: list[PlanEntry] = field(default_factory=list)

    def target_root_tree(self) -> dict[str, dict[str, dict[str, int]]]:
        """Return a nested ``{year: {month: {event: count}}}`` preview tree."""
        tree: dict[str, dict[str, dict[str, int]]] = {}
        for entry in self.entries:
            # target = root / year / month / event / filename
            event_dir = entry.target.parent
            month_dir = event_dir.parent
            year_dir = month_dir.parent
            year = tree.setdefault(year_dir.name, {})
            month = year.setdefault(month_dir.name, {})
            month[event_dir.name] = month.get(event_dir.name, 0) + 1
        return tree

    def __len__(self) -> int:
        return len(self.entries)


class Planner:
    """Turn clustered events into a concrete, previewable placement plan."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._language = config.language

    def build(self, events: list[Event]) -> OrganizePlan:
        """Return an :class:`OrganizePlan` for the given *events*."""
        root = Path(self._config.target_dir)
        plan = OrganizePlan()
        used_targets: set[str] = set()

        for event in events:
            safe_event = sanitize_name(event.name, fallback=f"Event {event.event_id:02d}")
            for media in event.files:
                target = self._target_for(root, media, safe_event)
                target = self._deduplicate(target, used_targets)
                used_targets.add(str(target).lower())
                plan.entries.append(
                    PlanEntry(media=media, source=media.path, target=target, event_name=event.name)
                )
        _LOG.info("Built plan with %d placements across %d events.", len(plan), len(events))
        return plan

    # -- helpers --------------------------------------------------------- #
    def _target_for(self, root: Path, media: MediaFile, safe_event: str) -> Path:
        if media.capture_date is not None:
            year = f"{media.capture_date.year:04d}"
            month = month_folder(media.capture_date.month, self._language)
        else:
            year = _UNKNOWN_YEAR.get(self._language, "Unknown")
            month = _UNKNOWN_YEAR.get(self._language, "Unknown")
        return root / year / month / safe_event / media.path.name

    @staticmethod
    def _deduplicate(target: Path, used: set[str]) -> Path:
        """Return a non-colliding target by appending ``_1``, ``_2`` if needed."""
        if str(target).lower() not in used and not target.exists():
            return target
        stem, suffix = target.stem, target.suffix
        counter = 1
        while True:
            candidate = target.with_name(f"{stem}_{counter}{suffix}")
            if str(candidate).lower() not in used and not candidate.exists():
                return candidate
            counter += 1
