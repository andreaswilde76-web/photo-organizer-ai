"""Factory that instantiates the configured vision backend."""

from __future__ import annotations

from ..config import AIBackend, AIConfig
from ..logging_setup import get_logger
from .base import VisionModel
from .null_backend import NullVisionModel

__all__ = ["create_vision_model"]

_LOG = get_logger("ai.factory")


def create_vision_model(config: AIConfig, language: str = "de") -> VisionModel:
    """Create a :class:`VisionModel` from *config*.

    When AI is disabled, or the selected backend is unavailable, this falls back
    to the :class:`NullVisionModel` so the rest of the pipeline keeps working.
    """
    if not config.enabled or config.backend is AIBackend.NULL:
        _LOG.info("AI analysis disabled; using the null vision backend.")
        return NullVisionModel()

    model: VisionModel
    if config.backend is AIBackend.OLLAMA:
        from .ollama_backend import OllamaVisionModel

        model = OllamaVisionModel(config, language)
    elif config.backend is AIBackend.OPENAI:
        from .openai_backend import OpenAIVisionModel

        model = OpenAIVisionModel(config, language)
    else:  # pragma: no cover - exhaustive guard
        return NullVisionModel()

    if not model.is_available():
        _LOG.warning(
            "Vision backend %r is not available; falling back to metadata-only mode.",
            config.backend.value,
        )
        return NullVisionModel()
    return model
