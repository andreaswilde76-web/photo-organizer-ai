"""PyInstaller entry point for the PhotoOrganizer AI desktop GUI.

PyInstaller freezes a *script*, not a module, so this thin wrapper simply
delegates to :func:`photo_organizer.gui.app.main`. Keeping it separate from the
package avoids importing PySide6 at package-import time for non-GUI use.
"""

from __future__ import annotations

import multiprocessing
import sys

from photo_organizer.gui.app import main

if __name__ == "__main__":
    # Required so a frozen (PyInstaller) build does not re-launch the whole GUI
    # in worker sub-processes on Windows.
    multiprocessing.freeze_support()
    sys.exit(main())
