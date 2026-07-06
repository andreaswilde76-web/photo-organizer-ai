"""Main application window."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..config import Config, Operation
from ..logging_setup import QueueLogHandler, configure_logging, get_logger
from ..models import Event
from ..pipeline import Pipeline, PipelineResult
from .event_tree import EventTree
from .worker import AnalyzeWorker, OrganizeWorker

_LOG = get_logger("gui")

_LEVEL_COLORS = {
    40: "#c0392b",  # ERROR
    30: "#d35400",  # WARNING
    20: "#2c3e50",  # INFO
    10: "#7f8c8d",  # DEBUG
}


class MainWindow(QWidget):
    """The main PhotoOrganizer AI window."""

    def __init__(self, config: Config) -> None:
        super().__init__()
        self._config = config
        self._thread: QThread | None = None
        self._worker: AnalyzeWorker | OrganizeWorker | None = None
        self._result: PipelineResult | None = None
        self._kept_pipeline: Pipeline | None = None
        self.setWindowTitle("PhotoOrganizer AI")
        self.resize(1100, 720)
        self._build_ui()
        self._attach_log_handler()

    # -- UI construction ------------------------------------------------- #
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.addWidget(self._build_folders_group())
        root.addWidget(self._build_controls())
        root.addWidget(self._build_progress())
        root.addWidget(self._build_body(), stretch=1)

    def _build_folders_group(self) -> QGroupBox:
        box = QGroupBox("Folders")
        layout = QVBoxLayout(box)

        self._source_edit = QLineEdit(str(self._config.source_dir))
        self._target_edit = QLineEdit(str(self._config.target_dir))
        layout.addLayout(self._folder_row("Source folder:", self._source_edit, self._pick_source))
        layout.addLayout(self._folder_row("Target folder:", self._target_edit, self._pick_target))

        op_row = QHBoxLayout()
        op_row.addWidget(QLabel("Operation:"))
        self._operation_combo = QComboBox()
        self._operation_combo.addItems(["copy", "move"])
        self._operation_combo.setCurrentText(self._config.operation.value)
        op_row.addWidget(self._operation_combo)
        op_row.addStretch(1)
        layout.addLayout(op_row)
        return box

    def _folder_row(self, label: str, edit: QLineEdit, handler: Callable[[], None]) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(QLabel(label))
        row.addWidget(edit, stretch=1)
        button = QPushButton("Browse…")
        button.clicked.connect(handler)
        row.addWidget(button)
        return row

    def _build_controls(self) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        self._start_btn = QPushButton("Start")
        self._pause_btn = QPushButton("Pause")
        self._resume_btn = QPushButton("Resume")
        self._stop_btn = QPushButton("Stop")
        self._organize_btn = QPushButton("Organize files…")
        self._start_btn.clicked.connect(self._on_start)
        self._pause_btn.clicked.connect(self._on_pause)
        self._resume_btn.clicked.connect(self._on_resume)
        self._stop_btn.clicked.connect(self._on_stop)
        self._organize_btn.clicked.connect(self._on_organize)
        for btn in (self._start_btn, self._pause_btn, self._resume_btn, self._stop_btn):
            row.addWidget(btn)
        row.addStretch(1)
        row.addWidget(self._organize_btn)
        self._set_running(False)
        return widget

    def _build_progress(self) -> QWidget:
        widget = QWidget()
        row = QHBoxLayout(widget)
        self._progress = QProgressBar()
        self._progress.setTextVisible(True)
        self._status = QLabel("Ready")
        row.addWidget(self._progress, stretch=1)
        row.addWidget(self._status)
        return widget

    def _build_body(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QGroupBox("Event preview (drag files to move, double-click to rename)")
        left_layout = QVBoxLayout(left)
        self._tree = EventTree()
        left_layout.addWidget(self._tree)
        merge_row = QHBoxLayout()
        self._rebuild_btn = QPushButton("Apply edits to plan")
        self._rebuild_btn.clicked.connect(self._on_rebuild)
        merge_row.addStretch(1)
        merge_row.addWidget(self._rebuild_btn)
        left_layout.addLayout(merge_row)
        splitter.addWidget(left)

        right = QGroupBox("Live log")
        right_layout = QVBoxLayout(right)
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(5000)
        right_layout.addWidget(self._log_view)
        splitter.addWidget(right)

        splitter.setSizes([650, 450])
        return splitter

    def _attach_log_handler(self) -> None:
        configure_logging(self._config.logging)
        handler = QueueLogHandler(self._append_log)
        logging.getLogger("photo_organizer").addHandler(handler)

    # -- logging --------------------------------------------------------- #
    def _append_log(self, message: str, level: int) -> None:
        color = _LEVEL_COLORS.get(level, "#2c3e50")
        self._log_view.appendHtml(f'<span style="color:{color}">{message}</span>')

    # -- folder pickers -------------------------------------------------- #
    def _pick_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select source folder")
        if path:
            self._source_edit.setText(path)

    def _pick_target(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select target folder")
        if path:
            self._target_edit.setText(path)

    # -- config sync ----------------------------------------------------- #
    def _sync_config(self) -> None:
        self._config.source_dir = Path(self._source_edit.text())
        self._config.target_dir = Path(self._target_edit.text())
        self._config.operation = Operation(self._operation_combo.currentText())

    # -- analysis lifecycle ---------------------------------------------- #
    def _on_start(self) -> None:
        self._sync_config()
        if not self._config.source_dir.is_dir():
            QMessageBox.warning(self, "Invalid source", "Please choose a valid source folder.")
            return
        self._set_running(True)
        self._progress.setValue(0)
        self._status.setText("Analysing…")

        self._thread = QThread(self)
        worker = AnalyzeWorker(self._config)
        worker.moveToThread(self._thread)
        self._thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_analysis_done)
        worker.failed.connect(self._on_failed)
        self._worker = worker
        self._thread.start()

    def _on_pause(self) -> None:
        if isinstance(self._worker, AnalyzeWorker):
            self._worker.pause()
            self._status.setText("Paused")

    def _on_resume(self) -> None:
        if isinstance(self._worker, AnalyzeWorker):
            self._worker.resume()
            self._status.setText("Analysing…")

    def _on_stop(self) -> None:
        if isinstance(self._worker, AnalyzeWorker):
            self._worker.stop()
            self._status.setText("Stopping…")

    def _on_progress(self, done: int, total: int, message: str) -> None:
        self._progress.setMaximum(max(total, 1))
        self._progress.setValue(done)
        self._status.setText(f"{done}/{total}  {message}")

    def _on_analysis_done(self, result: PipelineResult) -> None:
        self._result = result
        self._tree.set_events(result.events)
        self._status.setText(f"Done: {len(result.events)} events, {len(result.files)} files.")
        self._finish_thread()
        self._set_running(False)
        self._organize_btn.setEnabled(bool(result.plan and len(result.plan)))

    def _on_failed(self, message: str) -> None:
        QMessageBox.critical(self, "Error", message)
        self._finish_thread()
        self._set_running(False)

    # -- editing / organise ---------------------------------------------- #
    def _on_rebuild(self) -> None:
        pipeline = self._worker_pipeline()
        if not self._result or pipeline is None:
            return
        events: list[Event] = self._tree.to_events()
        self._result.events = events
        self._result.plan = pipeline.rebuild_plan(events)
        self._tree.set_events(events)
        self._status.setText("Plan updated from your edits.")

    def _on_organize(self) -> None:
        pipeline = self._worker_pipeline()
        if not self._result or not self._result.plan or not pipeline:
            return
        verb = self._config.operation.value
        confirm = QMessageBox.question(
            self,
            "Confirm",
            f"{verb.capitalize()} {len(self._result.plan)} files into\n{self._config.target_dir}?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        self._set_running(True)
        self._status.setText("Organising…")
        self._thread = QThread(self)
        worker = OrganizeWorker(pipeline, self._result.plan)
        worker.moveToThread(self._thread)
        self._thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_organize_done)
        worker.failed.connect(self._on_failed)
        self._worker = worker
        self._thread.start()

    def _on_organize_done(self, result: object) -> None:
        self._status.setText("Organisation complete.")
        self._finish_thread()
        self._set_running(False)
        QMessageBox.information(self, "Done", "Files were organised successfully.")

    # -- helpers --------------------------------------------------------- #
    def _worker_pipeline(self) -> Pipeline | None:
        # The analysis worker owns the live Pipeline (with its database handle).
        if isinstance(self._worker, AnalyzeWorker) and self._worker.pipeline is not None:
            return self._worker.pipeline
        return self._kept_pipeline

    def _finish_thread(self) -> None:
        if isinstance(self._worker, AnalyzeWorker) and self._worker.pipeline:
            # Keep the pipeline alive for the organise step.
            self._kept_pipeline = self._worker.pipeline
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait()
            self._thread = None

    def _set_running(self, running: bool) -> None:
        self._start_btn.setEnabled(not running)
        self._pause_btn.setEnabled(running)
        self._resume_btn.setEnabled(running)
        self._stop_btn.setEnabled(running)
        self._organize_btn.setEnabled(not running and self._result is not None)
