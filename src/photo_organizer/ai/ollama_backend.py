"""Local Ollama vision backend.

Talks to a local Ollama server (``http://localhost:11434`` by default) using its
HTTP API. Works with any multimodal model pulled into Ollama, e.g.
``qwen2.5vl:7b``, ``llava``, ``minicpm-v``. Fully local; no cloud required.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from ..config import AIConfig
from ..logging_setup import get_logger
from ..models import ImageAnalysis
from .base import VisionModel
from .image_utils import encode_image_base64
from .prompts import (
    build_analysis_prompt,
    build_date_prompt,
    build_event_prompt,
    parse_analysis_response,
    parse_date_response,
)

__all__ = ["OllamaVisionModel"]

_LOG = get_logger("ai.ollama")


class OllamaVisionModel(VisionModel):
    """Vision backend backed by a local Ollama server."""

    name = "ollama"

    def __init__(self, config: AIConfig, language: str = "de") -> None:
        self._config = config
        self._language = language
        self._host = config.ollama.host.rstrip("/")
        self._session = requests.Session()

    # -- availability ----------------------------------------------------- #
    def is_available(self) -> bool:
        try:
            resp = self._session.get(f"{self._host}/api/tags", timeout=5)
            resp.raise_for_status()
            models = {m.get("name", "") for m in resp.json().get("models", [])}
            if self._config.model not in models:
                _LOG.warning(
                    "Ollama model %r not found. Pull it with `ollama pull %s`.",
                    self._config.model,
                    self._config.model,
                )
            return True
        except requests.RequestException as exc:
            _LOG.warning("Ollama server not reachable at %s: %s", self._host, exc)
            return False

    # -- requests --------------------------------------------------------- #
    def _generate(self, prompt: str, image_b64: str | None = None) -> str:
        payload: dict[str, Any] = {
            "model": self._config.model,
            "prompt": prompt,
            "stream": False,
            "keep_alive": self._config.ollama.keep_alive,
            "options": {"temperature": 0.1},
        }
        if image_b64 is not None:
            payload["images"] = [image_b64]
        resp = self._session.post(
            f"{self._host}/api/generate", json=payload, timeout=self._config.timeout
        )
        resp.raise_for_status()
        return str(resp.json().get("response", ""))

    # -- VisionModel API -------------------------------------------------- #
    def analyze_image(self, image_path: Path) -> ImageAnalysis:
        try:
            image_b64 = encode_image_base64(image_path, self._config.max_image_size)
            text = self._generate(build_analysis_prompt(self._language), image_b64)
            return parse_analysis_response(text)
        except (requests.RequestException, OSError, ValueError) as exc:
            _LOG.warning("Ollama analysis failed for %s: %s", image_path, exc)
            return ImageAnalysis()

    def estimate_date(self, image_path: Path) -> datetime | None:
        try:
            image_b64 = encode_image_base64(image_path, self._config.max_image_size)
            text = self._generate(build_date_prompt(), image_b64)
            return parse_date_response(text)
        except (requests.RequestException, OSError, ValueError) as exc:
            _LOG.debug("Ollama date estimate failed for %s: %s", image_path, exc)
            return None

    def describe_event(self, keywords: list[str], location: str | None = None) -> str | None:
        try:
            text = self._generate(build_event_prompt(keywords, location, self._language))
            cleaned = text.strip().strip('"').splitlines()
            return cleaned[0].strip() if cleaned else None
        except requests.RequestException as exc:
            _LOG.debug("Ollama event description failed: %s", exc)
            return None

    def close(self) -> None:
        self._session.close()
