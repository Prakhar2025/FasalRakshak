"""Tests for the model-output JSON extractor used by every agent."""

from __future__ import annotations

import pytest

from fasalrakshak.agents import AgentOutputError, _extract_json


def test_plain_json_object_parses() -> None:
    text = '{"usable": true, "reason": "", "crop_hint": "tomato"}'

    data = _extract_json(text)

    assert data["usable"] is True


def test_markdown_fenced_json_parses() -> None:
    text = '```json\n{"usable": false, "reason": "धब्बा साफ नहीं है", "crop_hint": ""}\n```'

    data = _extract_json(text)

    assert data["usable"] is False


def test_prose_around_json_parses() -> None:
    text = 'Here is the diagnosis you asked for:\n{"disease_id": "tomato-early-blight", "confidence": 0.9}\nHope this helps.'

    data = _extract_json(text)

    assert data["disease_id"] == "tomato-early-blight"


def test_nested_object_parses() -> None:
    text = '{"treatment": {"products": [{"name": "Mancozeb 75 WG"}]}, "ok": true}'

    data = _extract_json(text)

    assert data["treatment"]["products"][0]["name"] == "Mancozeb 75 WG"


def test_no_json_raises() -> None:
    with pytest.raises(AgentOutputError):
        _extract_json("I am very sorry, I cannot answer that.")


def test_broken_json_raises() -> None:
    with pytest.raises(AgentOutputError):
        _extract_json('{"usable": true, "reason": "oops')
