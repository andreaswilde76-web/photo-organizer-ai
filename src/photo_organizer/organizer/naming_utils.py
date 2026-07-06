"""Filesystem-name utilities (month folders, sanitisation)."""

from __future__ import annotations

import re

__all__ = ["MONTH_NAMES", "month_folder", "sanitize_name"]

MONTH_NAMES: dict[str, list[str]] = {
    "de": [
        "Januar",
        "Februar",
        "März",
        "April",
        "Mai",
        "Juni",
        "Juli",
        "August",
        "September",
        "Oktober",
        "November",
        "Dezember",
    ],
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
}

# Characters that are invalid in Windows file/dir names.
_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_name(name: str, *, fallback: str = "Event", max_length: int = 80) -> str:
    """Return a Windows-safe folder name derived from *name*.

    Invalid characters are replaced, surrounding dots/spaces trimmed (Windows
    disallows trailing ones), reserved device names avoided, and the result
    truncated to *max_length*.
    """
    cleaned = _INVALID.sub(" ", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if not cleaned:
        return fallback
    if cleaned.upper() in _RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned[:max_length].strip(" .") or fallback


def month_folder(month: int, language: str = "de") -> str:
    """Return a folder name like ``"07 Juli"`` for *month* (1..12)."""
    names = MONTH_NAMES.get(language, MONTH_NAMES["en"])
    index = min(max(month, 1), 12) - 1
    return f"{index + 1:02d} {names[index]}"
