"""Optional OpenAI Vision backend (opt-in cloud fallback).

This backend is only used when explicitly selected in the configuration
(``ai.backend: openai``). It is deliberately isolated so the default,
fully-local workflow never imports or requires the ``openai`` package.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

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

__all__ = ["OpenAIVisionModel"]

_LOG = get_logger("ai.openai")


class OpenAIVisionModel(VisionModel):
    """Vision backend backed by the OpenAI Chat Completions vision API."""

    name = "openai"

    def __init__(self, config: AIConfig, language: str = "de") -> None:
        self._config = config
        self._language = language
        self._api_key = config.openai.api_key or os.environ.get("OPENAI_API_KEY", "")
        self._client = None  # lazily created

    def _get_client(self) -> object | None:
        if self._client is not None:
            return self._client
        if not self._api_key:
            _LOG.warning("OpenAI backend selected but no API key configured.")
            return None
        try:
            from openai import OpenAI
        except ImportError:
            _LOG.error("The 'openai' package is not installed. Install extra: .[openai]")
            return None
        self._client = OpenAI(api_key=self._api_key, base_url=self._config.openai.base_url)
        return self._client

    def is_available(self) -> bool:
        return self._get_client() is not None

    def _chat(self, prompt: str, image_path: Path | None = None) -> str:
        client = self._get_client()
        if client is None:
            return ""
        content: list[dict[str, object]] = [{"type": "text", "text": prompt}]
        if image_path is not None:
            b64 = encode_image_base64(image_path, self._config.max_image_size)
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                }
            )
        # ``client`` is the OpenAI SDK object; call its typed API.
        completion = client.chat.completions.create(  # type: ignore[attr-defined]
            model=self._config.model,
            messages=[{"role": "user", "content": content}],
            temperature=0.1,
            timeout=self._config.timeout,
        )
        return completion.choices[0].message.content or ""

    def analyze_image(self, image_path: Path) -> ImageAnalysis:
        try:
            return parse_analysis_response(
                self._chat(build_analysis_prompt(self._language), image_path)
            )
        except Exception as exc:
            _LOG.warning("OpenAI analysis failed for %s: %s", image_path, exc)
            return ImageAnalysis()

    def estimate_date(self, image_path: Path) -> datetime | None:
        try:
            return parse_date_response(self._chat(build_date_prompt(), image_path))
        except Exception as exc:
            _LOG.debug("OpenAI date estimate failed for %s: %s", image_path, exc)
            return None

    def describe_event(self, keywords: list[str], location: str | None = None) -> str | None:
        try:
            text = self._chat(build_event_prompt(keywords, location, self._language))
            return text.strip().strip('"') or None
        except Exception as exc:
            _LOG.debug("OpenAI event description failed: %s", exc)
            return None
