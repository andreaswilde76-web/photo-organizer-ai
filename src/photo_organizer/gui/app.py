"""GUI application bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ..config import Config, ConfigError

__all__ = ["main"]


def _load_config() -> Config:
    """Load ``config.yaml`` if present, else fall back to built-in defaults."""
    for candidate in (Path("config.yaml"), Path("config.json"), Path("config.example.yaml")):
        if candidate.is_file():
            try:
                return Config.load(candidate)
            except ConfigError:
                break
    return Config()


def main() -> int:
    """Launch the desktop GUI. Returns the Qt event-loop exit code."""
    app = QApplication(sys.argv)
    app.setApplicationName("PhotoOrganizer AI")

    # Imported lazily so the module import cost is only paid when launching.
    from .main_window import MainWindow

    window = MainWindow(_load_config())
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
