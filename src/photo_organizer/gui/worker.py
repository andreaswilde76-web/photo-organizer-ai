"""Background workers that run the pipeline off the GUI thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ..config import Config
from ..database import Database
from ..organizer.planner import OrganizePlan
from ..pipeline import Pipeline, PipelineResult

__all__ = ["AnalyzeWorker", "OrganizeWorker"]


class AnalyzeWorker(QObject):
    """Runs :meth:`Pipeline.analyze` and reports progress via Qt signals."""

    progress = Signal(int, int, str)  # done, total, message
    finished = Signal(object)  # PipelineResult
    failed = Signal(str)

    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config = config
        self._pipeline: Pipeline | None = None

    def run(self) -> None:
        """Entry point executed inside the worker thread."""
        try:
            db = Database(self._config.database_path)
            self._pipeline = Pipeline(self._config, db)
            result: PipelineResult = self._pipeline.analyze(
                progress=lambda d, t, m: self.progress.emit(d, t, m)
            )
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

    # -- control (thread-safe: they only set events) --------------------- #
    def pause(self) -> None:
        if self._pipeline:
            self._pipeline.pause()

    def resume(self) -> None:
        if self._pipeline:
            self._pipeline.resume()

    def stop(self) -> None:
        if self._pipeline:
            self._pipeline.stop()

    @property
    def pipeline(self) -> Pipeline | None:
        return self._pipeline


class OrganizeWorker(QObject):
    """Runs the move/copy execution of a confirmed plan."""

    progress = Signal(int, int, str)
    finished = Signal(object)  # ExecutionResult
    failed = Signal(str)

    def __init__(self, pipeline: Pipeline, plan: OrganizePlan) -> None:
        super().__init__()
        self._pipeline = pipeline
        self._plan = plan

    def run(self) -> None:
        try:
            result = self._pipeline.organize(
                self._plan, progress=lambda d, t, m: self.progress.emit(d, t, m)
            )
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
