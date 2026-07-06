"""Central logging configuration.

Provides a single :func:`configure_logging` entry point plus a lightweight
:class:`QueueLogHandler` that can forward records to arbitrary callbacks (used by
the GUI to display a live log).
"""

from __future__ import annotations

import logging
import logging.handlers
from collections.abc import Callable
from pathlib import Path

from .config import LoggingConfig

__all__ = ["QueueLogHandler", "configure_logging", "get_logger"]

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def configure_logging(
    config: LoggingConfig, *, root_name: str = "photo_organizer"
) -> logging.Logger:
    """Configure and return the package root logger from *config*.

    Repeated calls reconfigure handlers idempotently so that reloading the
    configuration in the GUI does not create duplicate log lines.
    """
    global _configured
    logger = logging.getLogger(root_name)
    level = getattr(logging, config.level.upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    # Remove existing handlers to avoid duplicates on reconfiguration.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    if config.console:
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        logger.addHandler(stream)

    if config.file:
        path = Path(config.file)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    _configured = True
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``photo_organizer`` namespace."""
    return logging.getLogger(f"photo_organizer.{name}")


class QueueLogHandler(logging.Handler):
    """A logging handler that forwards formatted records to a callback.

    The GUI uses this to stream log lines into its live-log widget without
    coupling the core library to any UI framework.
    """

    def __init__(self, callback: Callable[[str, int], None]) -> None:
        super().__init__()
        self._callback = callback
        self.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            self._callback(message, record.levelno)
        except Exception:  # pragma: no cover - never let logging crash the app
            self.handleError(record)
