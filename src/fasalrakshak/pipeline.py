"""The code-owned diagnosis pipeline.

Orchestration lives here, in Python, per ADR-0002: triage, candidate search,
diagnosis, optional escalation, treatment draft, and the deterministic safety
gate, in that order, with fail-closed behavior at every stage.

Every agent is an injected callable so tests run without AWS. With no agents
injected, the real Strands agents (agents.py) are constructed lazily.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from .agents import AgentOutputError
from .kb import load_all_entries, load_entry
from .safety import CONFIDENCE_FLOOR, SafetyVerdict, verify_treatment
from .schemas import Treatment


@dataclass(frozen=True)
class TriageOutcome:
    usable: bool
    reason: str
    crop_hint: str


@dataclass(frozen=True)
class DiagnosisOutcome:
    disease_id: str
    label: str
    confidence: float
    runner_up_id: str = ""
    runner_up_confidence: float = 0.0
    escalated_model_used: bool = False


@dataclass
class PipelineResult:
    """Mirrors the API response contract in docs/API_CONTRACT.md."""

    status: str  # treated | retake | escalated | blocked
    triage: TriageOutcome | None = None
    diagnosis: DiagnosisOutcome | None = None
    treatment_final: Treatment | None = None
    safety: SafetyVerdict | None = None
    spoken_addendum: list[str] = field(default_factory=list)
    kb_entry_id: str = ""


class TriageFn(Protocol):
    def __call__(self, image: bytes, transcript: str) -> TriageOutcome: ...


class DiagnoseFn(Protocol):
    def __call__(self, image: bytes, candidates: list[tuple[str, str]]) -> DiagnosisOutcome: ...


class TreatFn(Protocol):
    def __call__(self, entry_json: dict, transcript: str, lang: str = "hi") -> Treatment: ...


def search_kb_candidates(
    crop_hint: str,
    transcript: str,
    entries: dict | None = None,
) -> list[tuple[str, str, list[str]]]:
    """Rank the knowledge base for one request. Never hides a candidate.

    The model must be able to choose among ALL entries of the crop: a
    transcript only reorders candidates, it never cuts the list, because an
    alphabetically-buried disease would otherwise be undiagnosable. With no
    crop hint, every entry in the catalog is ranked.
    """
    catalog = entries or load_all_entries()
    if crop_hint:
        pool = {k: v for k, v in catalog.items() if v.crop == crop_hint}
        pool = pool or catalog
    else:
        pool = catalog

    tokens = {
        token.strip(".,!?;:()\"'")
        for token in transcript.lower().split()
        if len(token.strip(".,!?;:()\"'")) >= 3
    }

    def score(kb_id: str, entry) -> int:
        if not tokens:
            return 0
        haystack_parts = [entry.disease.lower(), *entry.aliases]
        for symptom in entry.symptoms:
            haystack_parts.append(symptom.lower())
        haystack = " ".join(haystack_parts)
        return sum(1 for token in tokens if token in haystack)

    ranked = sorted(pool.items(), key=lambda item: (-score(*item), item[0]))
    return [(kb_id, entry.disease, list(entry.symptoms)) for kb_id, entry in ranked]


def _default_triage() -> TriageFn:
    from .agents import TriageAgent

    agent = TriageAgent()
    return lambda image, transcript: _triage_outcome(agent.run(image))


def _triage_outcome(result) -> TriageOutcome:
    return TriageOutcome(usable=result.usable, reason=result.reason, crop_hint=result.crop_hint)


def _default_diagnose() -> DiagnoseFn:
    from .agents import DiagnosisAgent

    agent = DiagnosisAgent()
    return lambda image, candidates: _diagnosis_outcome(agent.run(image, candidates))


def _diagnosis_outcome(result) -> DiagnosisOutcome:
    return DiagnosisOutcome(
        disease_id=result.disease_id,
        label=result.label,
        confidence=result.confidence,
        runner_up_id=result.runner_up_id,
        runner_up_confidence=result.runner_up_confidence,
    )


def _default_treat() -> TreatFn:
    from .agents import TreatmentAgent

    agent = TreatmentAgent()
    return lambda entry_json, transcript, lang="hi": agent.run(entry_json, lang)


def run_diagnosis_pipeline(
    image: bytes,
    *,
    transcript: str = "",
    days_to_harvest: int | None = None,
    lang: str = "hi",
    triage: TriageFn | None = None,
    diagnose: DiagnoseFn | None = None,
    escalate: DiagnoseFn | None = None,
    treat: TreatFn | None = None,
    gate: Callable[..., SafetyVerdict] = verify_treatment,
    entries: dict | None = None,
) -> PipelineResult:
    """One farmer request, end to end, with fail-closed stages."""
    triage_fn = triage or _default_triage()
    diagnose_fn = diagnose or _default_diagnose()
    treat_fn = treat or _default_treat()

    triage_outcome = triage_fn(image, transcript)
    if not triage_outcome.usable:
        return PipelineResult(
            status="retake",
            triage=triage_outcome,
            spoken_addendum=[
                "यह फोटो ठीक से नहीं आई। पत्ती को साफ रोशनी में, पास से दोबारा फोटो लें।"
            ],
        )

    candidates = search_kb_candidates(triage_outcome.crop_hint, transcript, entries=entries)
    if not candidates:
        return PipelineResult(
            status="escalated",
            triage=triage_outcome,
            spoken_addendum=["यह तस्वीर अपने कृषि अधिकारी को दिखाएँ। अनुमान से दवा सुझाना सुरक्षित नहीं है।"],
        )

    diagnosis = diagnose_fn(image, candidates)

    # ADR-0001: one bounded Nova Pro re-check when the primary model is unsure.
    if (
        diagnosis.confidence < CONFIDENCE_FLOOR
        and escalate is not None
        and not diagnosis.escalated_model_used
    ):
        recheck = escalate(image, candidates)
        if recheck.confidence > diagnosis.confidence:
            diagnosis = DiagnosisOutcome(
                disease_id=recheck.disease_id,
                label=recheck.label,
                confidence=recheck.confidence,
                runner_up_id=recheck.runner_up_id,
                runner_up_confidence=recheck.runner_up_confidence,
                escalated_model_used=True,
            )

    if diagnosis.confidence < CONFIDENCE_FLOOR:
        return PipelineResult(
            status="escalated",
            triage=triage_outcome,
            diagnosis=diagnosis,
            spoken_addendum=["यह तस्वीर अपने कृषि अधिकारी को दिखाएँ। अनुमान से दवा सुझाना सुरक्षित नहीं है।"],
        )

    kb_entry = load_entry(diagnosis.disease_id)
    entry_json = kb_entry.model_dump()

    try:
        draft = treat_fn(entry_json, transcript, lang)
    except (AgentOutputError, ValueError):
        return PipelineResult(
            status="blocked",
            triage=triage_outcome,
            diagnosis=diagnosis,
            spoken_addendum=["यह तस्वीर अपने कृषि अधिकारी को दिखाएँ। अनुमान से दवा सुझाना सुरक्षित नहीं है।"],
        )

    # Code decides: the draft may only restate KB products, matched by active
    # ingredient. A model that translates a product name into Hindi is
    # repaired from the KB; a model that invents an ingredient is blocked.
    kb_products = entry_json["treatment"]["products"]
    kb_by_ingredient = {p["active_ingredient"]: p for p in kb_products}
    draft_ingredients = {p.active_ingredient for p in draft.products}
    if not draft_ingredients <= set(kb_by_ingredient):
        return PipelineResult(
            status="blocked",
            triage=triage_outcome,
            diagnosis=diagnosis,
            kb_entry_id=diagnosis.disease_id,
            spoken_addendum=["यह तस्वीर अपने कृषि अधिकारी को दिखाएँ। अनुमान से दवा सुझाना सुरक्षित नहीं है।"],
        )

    from .schemas import Product

    rebuilt = [Product(**kb_by_ingredient[p.active_ingredient]) for p in draft.products]
    draft = draft.model_copy(update={"products": rebuilt})

    verdict = gate(
        draft,
        diagnosis_confidence=diagnosis.confidence,
        runner_up_confidence=diagnosis.runner_up_confidence,
        image_usable=True,
        transcript=transcript,
        days_to_harvest=days_to_harvest,
    )

    status = "treated" if verdict.status in {"passed", "modified"} else verdict.status
    return PipelineResult(
        status=status,
        triage=triage_outcome,
        diagnosis=diagnosis,
        treatment_final=verdict.final_treatment,
        safety=verdict,
        spoken_addendum=verdict.spoken_addendum,
        kb_entry_id=diagnosis.disease_id,
    )
