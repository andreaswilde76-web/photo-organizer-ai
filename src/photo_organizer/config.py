"""Configuration model and loader for PhotoOrganizer AI.

The configuration is expressed as a set of nested, frozen-ish dataclasses. It
can be loaded from a YAML or JSON file (auto-detected by extension/content) and
validated. Unknown keys are ignored gracefully, and every field has a sensible
default so a minimal config file is enough to get started.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any, cast

import yaml

__all__ = [
    "AIBackend",
    "AIConfig",
    "ClusteringConfig",
    "Config",
    "ConfigError",
    "FacesConfig",
    "GeoConfig",
    "LoggingConfig",
    "MediaConfig",
    "Operation",
    "PerformanceConfig",
]


class ConfigError(ValueError):
    """Raised when a configuration file is malformed or invalid."""


class Operation(StrEnum):
    """How files are placed into the target structure."""

    MOVE = "move"
    COPY = "copy"


class AIBackend(StrEnum):
    """Supported vision-model backends."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    NULL = "null"


@dataclass
class LoggingConfig:
    """Logging behaviour."""

    level: str = "INFO"
    file: str | None = "photo_organizer.log"
    console: bool = True


@dataclass
class MediaConfig:
    """Which files are considered and how the source tree is walked."""

    photo_extensions: list[str] = field(
        default_factory=lambda: [
            "jpg",
            "jpeg",
            "png",
            "heic",
            "webp",
            "tif",
            "tiff",
            "raw",
            "cr2",
            "nef",
            "arw",
            "dng",
        ]
    )
    video_extensions: list[str] = field(default_factory=lambda: ["mp4", "mov", "avi", "mkv"])
    recursive: bool = True
    min_file_size: int = 1024

    def all_extensions(self) -> set[str]:
        """Return the union of photo and video extensions (lower-case)."""
        return {e.lower().lstrip(".") for e in (*self.photo_extensions, *self.video_extensions)}

    def is_video(self, extension: str) -> bool:
        """Return ``True`` if *extension* (with or without dot) is a video."""
        return extension.lower().lstrip(".") in {e.lower() for e in self.video_extensions}


@dataclass
class OllamaConfig:
    """Connection settings for a local Ollama server."""

    host: str = "http://localhost:11434"
    keep_alive: str = "5m"


@dataclass
class OpenAIConfig:
    """Settings for the optional OpenAI Vision backend."""

    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"


@dataclass
class AIConfig:
    """Vision-model configuration."""

    backend: AIBackend = AIBackend.OLLAMA
    model: str = "qwen2.5vl:7b"
    enabled: bool = True
    max_image_size: int = 1024
    timeout: int = 120
    estimate_date_when_missing: bool = True
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    openai: OpenAIConfig = field(default_factory=OpenAIConfig)


@dataclass
class GeoConfig:
    """Reverse-geocoding configuration."""

    enabled: bool = True


@dataclass
class FacesConfig:
    """Face-detection configuration."""

    enabled: bool = False


@dataclass
class ClusteringConfig:
    """Parameters controlling event clustering."""

    max_time_gap_hours: float = 6.0
    max_distance_km: float = 25.0
    visual_weight: float = 0.4
    min_cluster_size: int = 1


@dataclass
class PerformanceConfig:
    """Threading / hardware options."""

    workers: int = 0
    use_gpu: bool = True

    def effective_workers(self) -> int:
        """Return the concrete worker count (resolving ``0`` to cpu_count)."""
        if self.workers > 0:
            return self.workers
        import os

        return max(1, (os.cpu_count() or 1))


@dataclass
class Config:
    """Top-level application configuration."""

    source_dir: Path = Path(".")
    target_dir: Path = Path("./Fotos")
    operation: Operation = Operation.COPY
    database_path: Path = Path("photo_organizer.sqlite")
    language: str = "de"
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    media: MediaConfig = field(default_factory=MediaConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    geo: GeoConfig = field(default_factory=GeoConfig)
    faces: FacesConfig = field(default_factory=FacesConfig)
    clustering: ClusteringConfig = field(default_factory=ClusteringConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)

    # -- loading ---------------------------------------------------------- #
    @classmethod
    def load(cls, path: str | Path) -> Config:
        """Load and validate a config file (YAML or JSON) from *path*."""
        p = Path(path)
        if not p.is_file():
            raise ConfigError(f"Configuration file not found: {p}")
        raw = p.read_text(encoding="utf-8")
        try:
            data = json.loads(raw) if p.suffix.lower() == ".json" else yaml.safe_load(raw)
        except (yaml.YAMLError, json.JSONDecodeError) as exc:  # pragma: no cover
            raise ConfigError(f"Could not parse configuration {p}: {exc}") from exc
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ConfigError("Top-level configuration must be a mapping/object.")
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        """Build a :class:`Config` from a plain dictionary."""
        cfg = cls(
            source_dir=Path(data.get("source_dir", ".")),
            target_dir=Path(data.get("target_dir", "./Fotos")),
            operation=_enum(Operation, data.get("operation"), Operation.COPY),
            database_path=Path(data.get("database_path", "photo_organizer.sqlite")),
            language=str(data.get("language", "de")),
            logging=_section(LoggingConfig, data.get("logging")),
            media=_section(MediaConfig, data.get("media")),
            ai=_ai_section(data.get("ai")),
            geo=_section(GeoConfig, data.get("geo")),
            faces=_section(FacesConfig, data.get("faces")),
            clustering=_section(ClusteringConfig, data.get("clustering")),
            performance=_section(PerformanceConfig, data.get("performance")),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        """Validate cross-field constraints, raising :class:`ConfigError`."""
        if not 0.0 <= self.clustering.visual_weight <= 1.0:
            raise ConfigError("clustering.visual_weight must be within [0, 1].")
        if self.clustering.max_time_gap_hours <= 0:
            raise ConfigError("clustering.max_time_gap_hours must be positive.")
        if self.ai.max_image_size < 64:
            raise ConfigError("ai.max_image_size must be >= 64.")
        if self.performance.workers < 0:
            raise ConfigError("performance.workers must be >= 0.")

    def to_dict(self) -> dict[str, Any]:
        """Serialise the configuration back to a plain dictionary."""
        return cast(dict[str, Any], _to_plain(self))


# --------------------------------------------------------------------------- #
# (De)serialisation helpers.
# --------------------------------------------------------------------------- #
def _enum(enum_cls: type[Enum], value: Any, default: Any) -> Any:
    """Return ``enum_cls(value)`` or *default* when *value* is missing."""
    if value is None:
        return default
    try:
        return enum_cls(value)
    except ValueError as exc:
        allowed = ", ".join(e.value for e in enum_cls)
        raise ConfigError(
            f"Invalid value {value!r} for {enum_cls.__name__}; expected one of: {allowed}"
        ) from exc


def _section[T](section_cls: type[T], data: Any) -> T:
    """Build a flat dataclass *section_cls* from a mapping, ignoring extras."""
    if data is None:
        return section_cls()
    if not isinstance(data, dict):
        raise ConfigError(f"Section '{section_cls.__name__}' must be a mapping.")
    valid = {f.name for f in fields(section_cls)}  # type: ignore[arg-type]
    kwargs = {k: v for k, v in data.items() if k in valid}
    return section_cls(**kwargs)


def _ai_section(data: Any) -> AIConfig:
    """Build the nested :class:`AIConfig`, including its sub-sections."""
    if data is None:
        return AIConfig()
    if not isinstance(data, dict):
        raise ConfigError("Section 'ai' must be a mapping.")
    return AIConfig(
        backend=_enum(AIBackend, data.get("backend"), AIBackend.OLLAMA),
        model=str(data.get("model", AIConfig.model)),
        enabled=bool(data.get("enabled", True)),
        max_image_size=int(data.get("max_image_size", 1024)),
        timeout=int(data.get("timeout", 120)),
        estimate_date_when_missing=bool(data.get("estimate_date_when_missing", True)),
        ollama=_section(OllamaConfig, data.get("ollama")),
        openai=_section(OpenAIConfig, data.get("openai")),
    )


def _to_plain(obj: Any) -> Any:
    """Recursively convert dataclasses/enums/paths into JSON-friendly values."""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _to_plain(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, list):
        return [_to_plain(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    return obj
