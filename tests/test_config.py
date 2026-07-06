"""Tests for the configuration loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from photo_organizer.config import AIBackend, Config, ConfigError, Operation


def test_defaults() -> None:
    cfg = Config()
    assert cfg.operation is Operation.COPY
    assert cfg.ai.backend is AIBackend.OLLAMA
    assert "jpg" in cfg.media.all_extensions()
    assert cfg.media.is_video("mp4")
    assert not cfg.media.is_video("jpg")


def test_from_dict_nested() -> None:
    cfg = Config.from_dict(
        {
            "source_dir": "/src",
            "target_dir": "/dst",
            "operation": "move",
            "ai": {"backend": "openai", "model": "gpt-4o", "ollama": {"host": "http://x:1"}},
            "clustering": {"max_time_gap_hours": 3.0, "visual_weight": 0.5},
            "unknown_key": 123,  # ignored gracefully
        }
    )
    assert cfg.source_dir == Path("/src")
    assert cfg.operation is Operation.MOVE
    assert cfg.ai.backend is AIBackend.OPENAI
    assert cfg.ai.model == "gpt-4o"
    assert cfg.ai.ollama.host == "http://x:1"
    assert cfg.clustering.max_time_gap_hours == 3.0


def test_invalid_enum() -> None:
    with pytest.raises(ConfigError):
        Config.from_dict({"operation": "teleport"})


def test_invalid_visual_weight() -> None:
    with pytest.raises(ConfigError):
        Config.from_dict({"clustering": {"visual_weight": 2.0}})


def test_load_yaml(tmp_path: Path) -> None:
    p = tmp_path / "config.yaml"
    p.write_text("operation: move\nlanguage: en\n", encoding="utf-8")
    cfg = Config.load(p)
    assert cfg.operation is Operation.MOVE
    assert cfg.language == "en"


def test_load_json_roundtrip(tmp_path: Path) -> None:
    cfg = Config.from_dict({"operation": "move", "language": "en"})
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg.to_dict()), encoding="utf-8")
    reloaded = Config.load(p)
    assert reloaded.operation is Operation.MOVE
    assert reloaded.to_dict()["language"] == "en"


def test_load_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        Config.load(tmp_path / "nope.yaml")


def test_effective_workers() -> None:
    cfg = Config.from_dict({"performance": {"workers": 4}})
    assert cfg.performance.effective_workers() == 4
    auto = Config.from_dict({"performance": {"workers": 0}})
    assert auto.performance.effective_workers() >= 1
