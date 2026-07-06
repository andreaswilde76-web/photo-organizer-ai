"""Tests for prompt building and (defensive) response parsing."""

from __future__ import annotations

from datetime import datetime

from photo_organizer.ai.prompts import (
    build_analysis_prompt,
    parse_analysis_response,
    parse_date_response,
)


def test_parse_clean_json() -> None:
    text = (
        '{"scene": "beach", "description": "A sunny beach", '
        '"tags": ["sea", "sand"], "objects": ["umbrella"], '
        '"activities": ["swimming"], "is_indoor": false, "is_daytime": true}'
    )
    analysis = parse_analysis_response(text)
    assert analysis.scene == "beach"
    assert analysis.is_indoor is False
    assert analysis.is_daytime is True
    assert "sea" in analysis.tags
    assert "beach" in analysis.keywords()


def test_parse_json_in_markdown_fence() -> None:
    text = '```json\n{"scene": "gym", "tags": ["indoor"]}\n```'
    analysis = parse_analysis_response(text)
    assert analysis.scene == "gym"


def test_parse_garbage_returns_empty() -> None:
    analysis = parse_analysis_response("I cannot help with that.")
    assert analysis.scene is None
    assert analysis.tags == []


def test_parse_date_response() -> None:
    assert parse_date_response('{"year": 2019, "month": 8, "day": 15}') == datetime(2019, 8, 15)
    assert parse_date_response('{"year": null}') is None
    assert parse_date_response("no json here") is None
    # Out-of-range month/day are clamped, year window enforced.
    assert parse_date_response('{"year": 1800}') is None


def test_build_prompt_language() -> None:
    prompt = build_analysis_prompt("de")
    assert "'de'" in prompt
    assert "JSON" in prompt
