"""High-level orchestration of the whole organize workflow.

The :class:`Pipeline` ties together scanning, metadata extraction, AI analysis,
clustering, naming and planning. It is UI-agnostic: the CLI and the GUI both
drive it through the same small set of callbacks. Heavy per-file work runs on a
thread pool; the analysis cache means already-processed files are skipped.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from .ai import VisionModel, create_vision_model
from .clustering import EventClusterer, EventNamer
from .config import Config
from .database import Database
from .faces import FaceDetector
from .geo import ReverseGeocoder
from .hashing import hash_file
from .logging_setup import get_logger
from .media.date_extractor import DateExtractor
from .media.metadata import MetadataExtractor
from .media.scanner import MediaScanner
from .models import DateSource, Event, MediaFile, MediaKind
from .organizer import Executor, OrganizePlan, Planner

__all__ = ["AnalysisProgress", "Pipeline", "PipelineResult"]

_LOG = get_logger("pipeline")

# progress callback signature: (done, total, message)
ProgressCallback = Callable[[int, int, str], None]


@dataclass
class AnalysisProgress:
    """Mutable progress counters shared with a UI."""

    total: int = 0
    done: int = 0
    cached: int = 0
    analyzed: int = 0
    failed: int = 0


@dataclass
class PipelineResult:
    """Result of a full analysis + clustering pass."""

    files: list[MediaFile] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    plan: OrganizePlan | None = None
    progress: AnalysisProgress = field(default_factory=AnalysisProgress)


class Pipeline:
    """Coordinates the end-to-end organisation workflow."""

    def __init__(self, config: Config, database: Database) -> None:
        self._config = config
        self._db = database
        self._scanner = MediaScanner(config.media)
        self._metadata = MetadataExtractor()
        self._dates = DateExtractor()
        self._geocoder = ReverseGeocoder(config.geo.enabled)
        self._faces = FaceDetector(config.faces)
        self._vision: VisionModel = create_vision_model(config.ai, config.language)
        self._clusterer = EventClusterer(config.clustering)
        self._namer = EventNamer(config.language, config.clustering.min_cluster_size)
        self._planner = Planner(config)
        self._pause = threading.Event()  # set == running; cleared == paused
        self._pause.set()
        self._stop = threading.Event()

    # -- control --------------------------------------------------------- #
    def pause(self) -> None:
        """Pause processing at the next file boundary."""
        self._pause.clear()

    def resume(self) -> None:
        """Resume a paused run."""
        self._pause.set()

    def stop(self) -> None:
        """Request a graceful stop."""
        self._stop.set()
        self._pause.set()

    def _should_stop(self) -> bool:
        return self._stop.is_set()

    def _wait_if_paused(self) -> None:
        self._pause.wait()

    # -- analysis -------------------------------------------------------- #
    def analyze(self, progress: ProgressCallback | None = None) -> PipelineResult:
        """Scan and analyse every media file, returning cached results too."""
        self._stop.clear()
        self._pause.set()

        _LOG.info("Scanning source directory %s ...", self._config.source_dir)
        discovered = list(self._scanner.scan(self._config.source_dir))
        result = PipelineResult()
        result.progress.total = len(discovered)
        _LOG.info("Found %d media files.", len(discovered))

        workers = self._config.performance.effective_workers()
        files: list[MediaFile] = []
        lock = threading.Lock()

        def _emit(message: str) -> None:
            if progress is not None:
                progress(result.progress.done, result.progress.total, message)

        pool = ThreadPoolExecutor(max_workers=workers)
        try:
            futures = {
                pool.submit(self._process_file, path, kind is MediaKind.VIDEO): path
                for path, kind in discovered
            }
            for future in as_completed(futures):
                if self._should_stop():
                    break
                self._wait_if_paused()
                path = futures[future]
                try:
                    media, was_cached = future.result()
                except CancelledError:
                    continue
                except Exception as exc:
                    result.progress.failed += 1
                    _LOG.error("Failed to process %s: %s", path, exc)
                else:
                    if media is None and self._should_stop():
                        # File was skipped because a stop was requested.
                        continue
                    if media is not None:
                        with lock:
                            files.append(media)
                        if was_cached:
                            result.progress.cached += 1
                        else:
                            result.progress.analyzed += 1
                with lock:
                    result.progress.done += 1
                _emit(f"Processed {path.name}")
        finally:
            # On stop, drop queued work and return promptly instead of blocking
            # until every in-flight AI request times out.
            pool.shutdown(wait=not self._should_stop(), cancel_futures=True)

        if self._should_stop():
            _LOG.info("Analysis stopped by user after %d file(s).", result.progress.done)
        result.files = files
        if not self._should_stop():
            self._build_events(result)
        return result

    def _process_file(self, path: Path, is_video: bool) -> tuple[MediaFile | None, bool]:
        """Return ``(media, was_cached)`` for a single file."""
        # Honour pause/stop from inside the worker so the controls are
        # responsive even while thousands of files are queued.
        self._wait_if_paused()
        if self._should_stop():
            return None, False
        file_hash = hash_file(path, partial=is_video)

        cached = self._db.load_media(file_hash)
        if cached is not None and self._db.has_analysis(file_hash):
            # Refresh the current on-disk path (files may have been renamed).
            cached.path = path
            return cached, True

        media = MediaFile(
            path=path,
            kind=MediaKind.VIDEO if is_video else MediaKind.PHOTO,
            size=path.stat().st_size,
            file_hash=file_hash,
        )

        meta = self._metadata.extract(path, is_video=is_video)
        media.camera_model = meta.camera_model
        if meta.geo is not None:
            media.geo = self._geocoder.enrich(meta.geo)

        date_result = self._dates.resolve(path, meta)
        media.capture_date = date_result.date
        media.date_source = date_result.source

        if not is_video:
            if self._faces.available:
                media.face_count = self._faces.count_faces(path)
            media.analysis = self._vision.analyze_image(path)

            if media.capture_date is None and self._config.ai.estimate_date_when_missing:
                estimate = self._vision.estimate_date(path)
                if estimate is not None:
                    media.capture_date = estimate
                    media.date_source = DateSource.AI_ESTIMATE

        exif = meta.raw or None
        self._db.upsert_media(media, exif=exif)
        return media, False

    # -- clustering + planning ------------------------------------------- #
    def _build_events(self, result: PipelineResult) -> None:
        clusters = self._clusterer.cluster(result.files)
        events: list[Event] = []
        for index, cluster in enumerate(clusters, start=1):
            name = self._namer.name(cluster, index)
            event = Event(event_id=index, name=name, files=cluster)
            event.description = self._describe(event)
            for media in cluster:
                media.event_id = index
                self._db.update_event(media.file_hash, index)
            events.append(event)
        result.events = events
        result.plan = self._planner.build(events)

    def _describe(self, event: Event) -> str | None:
        keywords: list[str] = []
        for media in event.files:
            if media.analysis:
                keywords.extend(media.analysis.keywords())
        location = None
        for media in event.files:
            if media.geo and media.geo.label():
                location = media.geo.label()
                break
        # Deduplicate keywords preserving order.
        seen: dict[str, None] = {}
        for kw in keywords:
            seen.setdefault(kw, None)
        return self._vision.describe_event(list(seen), location)

    def rebuild_plan(self, events: list[Event]) -> OrganizePlan:
        """Rebuild the placement plan after the user edited events in the GUI."""
        return self._planner.build(events)

    # -- execution ------------------------------------------------------- #
    def organize(
        self,
        plan: OrganizePlan,
        *,
        progress: Callable[[int, int, str], None] | None = None,
        dry_run: bool = False,
    ) -> object:
        """Execute *plan* (move/copy) after the preview has been confirmed."""
        executor = Executor(self._db, self._config.operation)

        def _progress(done: int, total: int, entry: object) -> None:
            if progress is not None:
                progress(done, total, "Organizing files")

        return executor.execute(
            plan, progress=_progress, dry_run=dry_run, should_stop=self._should_stop
        )

    def resume_organize(self, *, progress: Callable[[int, int, str], None] | None = None) -> object:
        """Resume a previously interrupted organisation run."""
        executor = Executor(self._db, self._config.operation)

        def _progress(done: int, total: int, entry: object) -> None:
            if progress is not None:
                progress(done, total, "Resuming")

        return executor.resume(progress=_progress, should_stop=self._should_stop)

    def close(self) -> None:
        """Release backend resources."""
        self._vision.close()
