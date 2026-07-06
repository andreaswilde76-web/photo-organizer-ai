"""Prompt templates and response parsing for vision models.

Keeping prompts and the (defensive) JSON parser in one place makes the concrete
backends thin and keeps behaviour consistent when switching models.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from ..models import ImageAnalysis

__all__ = [
    "ANALYSIS_SCHEMA_HINT",
    "build_analysis_prompt",
    "build_date_prompt",
    "build_event_prompt",
    "parse_analysis_response",
    "parse_date_response",
]

# The categories the model should actively look for (from the specification).
_CATEGORIES = [
    "places",
    "buildings",
    "beach",
    "mountains",
    "snow",
    "forest",
    "restaurant",
    "gym",
    "concert",
    "sport",
    "wedding",
    "birthday",
    "christmas",
    "new_year",
    "pets",
    "vehicles",
    "landmarks",
    "food",
    "sunset",
    "indoor_outdoor",
    "day_night",
]

ANALYSIS_SCHEMA_HINT = (
    '{"scene": str, "description": str, "tags": [str], "objects": [str], '
    '"activities": [str], "is_indoor": bool, "is_daytime": bool}'
)


def build_analysis_prompt(language: str = "de") -> str:
    """Return the instruction prompt for single-image analysis."""
    return (
        "You are an expert photo analyst. Look at the image and return ONLY a "
        "compact JSON object (no markdown, no prose) with this exact schema:\n"
        f"{ANALYSIS_SCHEMA_HINT}\n"
        "Guidance:\n"
        "- 'scene' is a short label such as beach, mountains, restaurant, gym, "
        "concert, wedding, birthday, christmas, home, city, forest, snow.\n"
        f"- Consider these aspects when tagging: {', '.join(_CATEGORIES)}.\n"
        "- 'objects' lists prominent objects (people, pets, vehicles, food, "
        "landmarks, buildings).\n"
        "- 'activities' lists what people are doing (hiking, dining, dancing).\n"
        f"- Write 'description' as one natural sentence in language '{language}'.\n"
        "- 'is_indoor' true if the photo was taken indoors; 'is_daytime' true if "
        "it looks like daytime.\n"
        "Return strictly valid JSON."
    )


def build_date_prompt() -> str:
    """Return the prompt used to estimate a capture date from an image."""
    return (
        "Estimate when this photo was most likely taken. Consider seasonal cues, "
        "clothing, decorations, technology and lighting. Return ONLY JSON: "
        '{"year": int|null, "month": int|null, "day": int|null, '
        '"confidence": 0..1}. Use null for anything you cannot infer.'
    )


def build_event_prompt(keywords: list[str], location: str | None, language: str = "de") -> str:
    """Return the prompt used to summarise an event into a short description."""
    kw = ", ".join(keywords[:30]) if keywords else "various photos"
    loc = f" Location: {location}." if location else ""
    return (
        "Write a concise, friendly one-sentence description for a photo album "
        f"event in language '{language}'. Keywords: {kw}.{loc} "
        "Return ONLY the sentence, no quotes."
    )


# --------------------------------------------------------------------------- #
# Response parsing
# --------------------------------------------------------------------------- #
def _extract_json(text: str) -> dict[str, Any] | None:
    """Best-effort extraction of the first JSON object embedded in *text*."""
    text = text.strip()
    # Strip common markdown code fences.
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip():
        return [part.strip() for part in re.split(r"[;,]", value) if part.strip()]
    return []


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        low = value.strip().lower()
        if low in {"true", "yes", "indoor", "day"}:
            return True
        if low in {"false", "no", "outdoor", "night"}:
            return False
    return None


def parse_analysis_response(text: str) -> ImageAnalysis:
    """Parse a model response into an :class:`ImageAnalysis` (never raises)."""
    data = _extract_json(text) or {}
    return ImageAnalysis(
        scene=(str(data["scene"]).strip() if data.get("scene") else None),
        description=(str(data["description"]).strip() if data.get("description") else None),
        tags=_as_str_list(data.get("tags")),
        objects=_as_str_list(data.get("objects")),
        activities=_as_str_list(data.get("activities")),
        is_indoor=_as_bool(data.get("is_indoor")),
        is_daytime=_as_bool(data.get("is_daytime")),
        raw_response=text,
    )


def parse_date_response(text: str) -> datetime | None:
    """Parse a date-estimation response into a :class:`datetime` or ``None``."""
    data = _extract_json(text)
    if not data:
        return None
    year = data.get("year")
    if not year:
        return None
    try:
        y = int(year)
        m = int(data.get("month") or 1)
        d = int(data.get("day") or 1)
        m = min(max(m, 1), 12)
        d = min(max(d, 1), 28)
        if 1970 <= y <= 2100:
            return datetime(y, m, d)
    except (TypeError, ValueError):
        return None
    return None
