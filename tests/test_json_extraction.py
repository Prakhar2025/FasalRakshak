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


class _FakeAgent:
    """Stands in for a Strands Agent: returns one fixed text blob."""

    def __init__(self, text: str) -> None:
        self._text = text

    def __call__(self, blocks: list[dict]):
        class _Result:
            message = {"content": [{"text": self._text}]}

        return _Result()


def test_diagnosis_agent_normalizes_a_none_answer_to_healthy() -> None:
    """A healthy leaf makes the model answer 'none'. That is an honest
    diagnosis, not malformed output, and must never crash the pipeline."""
    from fasalrakshak.agents import DiagnosisAgent

    agent = DiagnosisAgent(
        model=_FakeAgent(
            '{"disease_id": "none", "label": "None", "confidence": 0.9, '
            '"runner_up_id": "", "runner_up_confidence": 0.0}'
        )
    )

    result = agent.run(b"\xff\xd8fakejpegdata", [("tomato-early-blight", "Early blight", ["rings"])])

    assert result.disease_id == "healthy"
    assert result.confidence == 0.9


def test_diagnosis_agent_still_rejects_invented_diseases() -> None:
    from fasalrakshak.agents import DiagnosisAgent

    agent = DiagnosisAgent(
        model=_FakeAgent(
            '{"disease_id": "tomato-cancer", "label": "Cancer", "confidence": 0.99, '
            '"runner_up_id": "", "runner_up_confidence": 0.0}'
        )
    )

    with pytest.raises(AgentOutputError):
        agent.run(b"\xff\xd8fakejpegdata", [("tomato-early-blight", "Early blight", ["rings"])])
