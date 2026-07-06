"""Execute an :class:`OrganizePlan`, moving or copying files with resume.

The executor is deliberately conservative:

* files are only touched when :meth:`Executor.execute` is called (after the user
  confirms the preview),
* every completed placement is recorded in the database so an interrupted run
  can be resumed without re-processing or duplicating files,
* an already-correctly-placed file is skipped instead of being copied again.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..config import Operation
from ..database import Database
from ..logging_setup import get_logger
from .planner import OrganizePlan, PlanEntry

__all__ = ["ExecutionResult", "Executor"]

_LOG = get_logger("organizer.executor")

ProgressCallback = Callable[[int, int, PlanEntry], None]


@dataclass
class ExecutionResult:
    """Summary of an execution run."""

    moved: int = 0
    copied: int = 0
    skipped: int = 0
    failed: int = 0

    @property
    def total(self) -> int:
        """Total number of processed entries."""
        return self.moved + self.copied + self.skipped + self.failed


class Executor:
    """Perform the planned file placements."""

    def __init__(self, database: Database, operation: Operation) -> None:
        self._db = database
        self._operation = operation

    def execute(
        self,
        plan: OrganizePlan,
        *,
        progress: ProgressCallback | None = None,
        dry_run: bool = False,
        should_stop: Callable[[], bool] | None = None,
    ) -> ExecutionResult:
        """Execute *plan*.

        Parameters
        ----------
        plan:
            The plan produced by :class:`~photo_organizer.organizer.planner.Planner`.
        progress:
            Optional ``(done, total, entry)`` callback for progress bars.
        dry_run:
            When ``True`` nothing is written; useful for validation/tests.
        should_stop:
            Optional predicate polled between files; when it returns ``True`` the
            run stops gracefully (already-placed files stay placed, enabling a
            later resume).
        """
        result = ExecutionResult()
        total = len(plan)

        # Register all intended placements first so resume knows the full plan.
        if not dry_run:
            for entry in plan.entries:
                self._db.record_placement(
                    entry.media.file_hash, entry.source, entry.target, self._operation.value
                )

        for index, entry in enumerate(plan.entries, start=1):
            if should_stop is not None and should_stop():
                _LOG.info("Execution paused/stopped by request after %d files.", index - 1)
                break
            try:
                outcome = self._place_one(entry, dry_run=dry_run)
                if outcome == "moved":
                    result.moved += 1
                elif outcome == "copied":
                    result.copied += 1
                else:
                    result.skipped += 1
                if not dry_run:
                    self._db.mark_placed(entry.media.file_hash)
            except OSError as exc:
                result.failed += 1
                _LOG.error("Failed to place %s -> %s: %s", entry.source, entry.target, exc)
            if progress is not None:
                progress(index, total, entry)

        _LOG.info(
            "Execution done: moved=%d copied=%d skipped=%d failed=%d",
            result.moved,
            result.copied,
            result.skipped,
            result.failed,
        )
        return result

    def resume(
        self,
        *,
        progress: ProgressCallback | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> ExecutionResult:
        """Resume an interrupted run using the placements stored in the database."""
        pending = self._db.pending_placements()
        _LOG.info("Resuming: %d placements still pending.", len(pending))
        result = ExecutionResult()
        total = len(pending)
        for index, (file_hash, source, target, operation) in enumerate(pending, start=1):
            if should_stop is not None and should_stop():
                break
            try:
                outcome = self._transfer(source, target, Operation(operation))
                if outcome == "moved":
                    result.moved += 1
                elif outcome == "copied":
                    result.copied += 1
                else:
                    result.skipped += 1
                self._db.mark_placed(file_hash)
            except OSError as exc:
                result.failed += 1
                _LOG.error("Resume failed for %s -> %s: %s", source, target, exc)
            if progress is not None:
                entry = PlanEntry(media=None, source=source, target=target, event_name="")  # type: ignore[arg-type]
                progress(index, total, entry)
        return result

    # -- internals ------------------------------------------------------- #
    def _place_one(self, entry: PlanEntry, *, dry_run: bool) -> str:
        if self._db.is_placed(entry.media.file_hash):
            return "skipped"
        if dry_run:
            return "skipped"
        return self._transfer(entry.source, entry.target, self._operation)

    @staticmethod
    def _transfer(source: Path, target: Path, operation: Operation) -> str:
        source = Path(source)
        target = Path(target)
        if not source.exists():
            # Nothing to do (e.g. already moved in a previous, partial run).
            return "skipped"
        if target.exists() and target.resolve() == source.resolve():
            return "skipped"
        target.parent.mkdir(parents=True, exist_ok=True)
        if operation is Operation.MOVE:
            shutil.move(str(source), str(target))
            return "moved"
        shutil.copy2(str(source), str(target))
        return "copied"
