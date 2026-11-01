"""Strands agents for triage, diagnosis and treatment.

Design (per docs/DESIGN.md and ADR-0002): each agent is a context-complete
prompt-to-JSON function. No tool loops, no model-led routing. The knowledge
base is searched in code (pipeline.py) and the candidates are handed to the
diagnosis prompt, which may only choose among them.

Every agent accepts an injected model so tests can run without AWS. With no
model injected, a Bedrock-backed Strands Agent is constructed lazily.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

from strands import Agent
from strands.models import BedrockModel

from .schemas import Treatment

REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_PRIMARY = os.environ.get("BEDROCK_MODEL_PRIMARY", "us.amazon.nova-lite-v1:0")
MODEL_ESCALATION = os.environ.get("BEDROCK_MODEL_ESCALATION", "us.amazon.nova-pro-v1:0")


class AgentOutputError(Exception):
    """The model's output could not be parsed into the required contract."""


@dataclass(frozen=True)
class TriageResult:
    usable: bool
    reason: str
    crop_hint: str


@dataclass(frozen=True)
class DiagnosisResult:
    disease_id: str
    label: str
    confidence: float
    runner_up_id: str
    runner_up_confidence: float


def _image_format(image: bytes) -> str:
    if image.startswith(b"\xff\xd8"):
        return "jpeg"
    if image.startswith(b"\x89PNG"):
        return "png"
    raise ValueError("unsupported image format, expected jpeg or png")


def _extract_json(text: str) -> dict:
    """Extract the first balanced JSON object from model output.

    Tolerates markdown fences and surrounding prose. Raises
    AgentOutputError when no parseable object exists.
    """
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise AgentOutputError("no parseable JSON object in model output")


def _bedrock_model(model_id: str) -> BedrockModel:
    return BedrockModel(model_id=model_id, region_name=REGION)


def _run_agent(agent: Agent, blocks: list[dict]) -> str:
    result = agent(blocks)
    message = getattr(result, "message", None)
    if message is None:
        raise AgentOutputError("agent returned no message")
    content = message.get("content", []) if isinstance(message, dict) else []
    parts = [block.get("text", "") for block in content if isinstance(block, dict)]
    text = "\n".join(part for part in parts if part)
    if not text.strip():
        raise AgentOutputError("agent returned empty text")
    return text


class TriageAgent:
    """Decides whether the photo is usable and hints the crop."""

    SYSTEM_PROMPT = (
        "You are the photo triage step of a crop disease assistant for Indian farmers. "
        "Decide if the attached photo can be used for disease diagnosis. "
        "It is usable only if a plant leaf is clearly visible and in focus. "
        "The system supports tomato and cotton only: crop_hint must be exactly one "
        "of: tomato, cotton, unknown. "
        "Answer with JSON only, exactly this shape: "
        '{"usable": true, "reason": "", "crop_hint": "tomato"} '
        "When unusable, write the reason in simple Hindi for the farmer."
    )

    def __init__(self, model: Agent | None = None, model_id: str = MODEL_PRIMARY) -> None:
        self._agent = model or Agent(
            model=_bedrock_model(model_id), system_prompt=self.SYSTEM_PROMPT
        )

    def run(self, image: bytes) -> TriageResult:
        blocks = [
            {"image": {"format": _image_format(image), "source": {"bytes": image}}},
            {"text": "Triage this photo. Answer with the JSON object only."},
        ]
        data = _extract_json(_run_agent(self._agent, blocks))
        return TriageResult(
            usable=bool(data.get("usable", False)),
            reason=str(data.get("reason", "")),
            crop_hint=str(data.get("crop_hint", "")).strip().lower(),
        )


class DiagnosisAgent:
    """Chooses among knowledge-base candidates by looking at the leaf photo."""

    SYSTEM_PROMPT = (
        "You are the diagnosis step of a crop disease assistant for Indian farmers. "
        "You will see a leaf photo and a numbered list of candidate diseases from a "
        "curated knowledge base, each with its known symptoms. You must choose among "
        "these candidates only; you may not invent another disease. Compare the photo "
        "against each candidate's symptoms: spot color and shape, concentric rings, "
        "yellow halos, white fungal growth, wilting, curling, mosaic patterns, webbing. "
        "Answer with JSON only, exactly this shape: "
        '{"disease_id": "tomato-early-blight", "label": "Early blight", '
        '"confidence": 0.85, "runner_up_id": "tomato-septoria-leaf-spot", '
        '"runner_up_confidence": 0.10} '
        "Confidence must be an honest number between 0 and 1. If the photo does not "
        "match any candidate well, say so with a low confidence for both."
    )

    def __init__(self, model: Agent | None = None, model_id: str = MODEL_PRIMARY) -> None:
        self._agent = model or Agent(
            model=_bedrock_model(model_id), system_prompt=self.SYSTEM_PROMPT
        )

    def run(
        self, image: bytes, candidates: list[tuple[str, str, list[str]]]
    ) -> DiagnosisResult:
        listing = "\n\n".join(
            f"{i + 1}. {kb_id} ({label})\n   Known symptoms: "
            + "; ".join(symptoms[:3])
            for i, (kb_id, label, symptoms) in enumerate(candidates)
        )
        blocks = [
            {"image": {"format": _image_format(image), "source": {"bytes": image}}},
            {
                "text": (
                    "Candidate diseases from the knowledge base:\n"
                    f"{listing}\n\n"
                    "Diagnose the photo against these symptom lists and answer with "
                    "the JSON object only."
                )
            },
        ]
        data = _extract_json(_run_agent(self._agent, blocks))
        allowed = {kb_id for kb_id, _, _ in candidates}
        disease_id = str(data.get("disease_id", "")).strip().lower()
        if disease_id in {"none", "healthy"}:
            # The model may honestly report that no candidate matches. That is
            # a valid diagnosis, not a malformed answer: normalize the wording
            # and let the pipeline decide what a healthy call means.
            return DiagnosisResult(
                disease_id="healthy",
                label="Healthy leaf",
                confidence=float(data.get("confidence", 0.0)),
                runner_up_id="",
                runner_up_confidence=0.0,
            )
        if disease_id not in allowed:
            raise AgentOutputError(f"model chose a disease outside the candidates: {disease_id}")
        return DiagnosisResult(
            disease_id=disease_id,
            label=str(data.get("label", "")),
            confidence=float(data.get("confidence", 0.0)),
            runner_up_id=str(data.get("runner_up_id", "")),
            runner_up_confidence=float(data.get("runner_up_confidence", 0.0)),
        )


class TreatmentAgent:
    """Turns one knowledge-base entry into a farmer-ready treatment draft.

    The draft may only use products that exist verbatim in the KB entry. The
    pipeline enforces this after the call; the safety gate then re-verifies
    every dose and ingredient.
    """

    SYSTEM_PROMPT = (
        "You are the treatment step of a crop disease assistant for Indian farmers. "
        "You will be given one curated knowledge base entry with a verified treatment. "
        "Restate it for a farmer with low literacy: very simple Hindi sentences, one "
        "instruction per step, no jargon, numbers with units spelled out. "
        "Copy the products section EXACTLY as given, do not change doses, units, or "
        "product names, and do not add any product. If the entry has no products, "
        "return an empty products list and restate the organic steps. "
        "Answer with JSON only, exactly this shape: "
        '{"summary": "...", "steps": ["..."], "products": [...as given...], '
        '"organic": [...as given...]}'
    )

    def __init__(self, model: Agent | None = None, model_id: str = MODEL_PRIMARY) -> None:
        self._agent = model or Agent(
            model=_bedrock_model(model_id), system_prompt=self.SYSTEM_PROMPT
        )

    LANGUAGE_NAMES = {
        "hi": "simple Hindi (Devanagari script)",
        "en": "simple English",
        "mr": "simple Marathi (Devanagari script)",
        "ta": "simple Tamil",
        "te": "simple Telugu",
        "bn": "simple Bengali",
        "gu": "simple Gujarati",
        "kn": "simple Kannada",
        "ml": "simple Malayalam",
        "pa": "simple Punjabi",
    }

    def run(self, entry_json: dict, lang: str = "hi") -> Treatment:
        language = self.LANGUAGE_NAMES.get(lang, self.LANGUAGE_NAMES["hi"])
        blocks = [
            {
                "text": (
                    "Knowledge base entry:\n"
                    f"{json.dumps(entry_json, ensure_ascii=False)}\n\n"
                    f"Write the farmer treatment draft in {language}: short sentences, "
                    "one instruction per step, numbers with units spelled out. "
                    "Copy the products section EXACTLY as given, do not change doses, "
                    "units, or product names, and do not add any product. "
                    "Answer with the JSON object only."
                )
            }
        ]
        data = _extract_json(_run_agent(self._agent, blocks))
        return Treatment.model_validate(data)
