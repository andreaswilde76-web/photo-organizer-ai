"""PySide6 desktop GUI for PhotoOrganizer AI.

The GUI is optional: importing this subpackage requires ``PySide6`` (install the
``gui`` extra). The core library and CLI work without it.
"""

from __future__ import annotations

__all__ = ["main"]


def main() -> int:
    """Launch the desktop application (thin re-export of :func:`app.main`)."""
    from .app import main as _main

    return _main()
