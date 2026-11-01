"""Pipeline orchestration tests with fake agents: no AWS, no network.

The real agents and the live smoke test need Bedrock credentials; the
orchestration logic, stage ordering, escalation bounds and fail-closed
behavior are proven here.
"""

from __future__ import annotations

import pytest

from fasalrakshak.kb import load_all_entries, load_entry
from fasalrakshak.pipeline import (
    DiagnosisOutcome,
    PipelineResult,
    TriageOutcome,
    run_diagnosis_pipeline,
    search_kb_candidates,
)
from fasalrakshak.schemas import Product, Treatment

DISEASE = "tomato-early-blight"
RUNNER = "tomato-septoria-leaf-spot"


def make_triage(usable: bool = True, crop: str = "tomato"):
    def _triage(image: bytes, transcript: str) -> TriageOutcome:
        return TriageOutcome(usable=usable, reason="" if usable else "blurry", crop_hint=crop)

    return _triage


def make_diagnose(confidence: float, disease: str = DISEASE, used: bool = False):
    def _diagnose(image: bytes, candidates: list[tuple[str, str]]) -> DiagnosisOutcome:
        return DiagnosisOutcome(
            disease_id=disease,
            label="Early blight",
            confidence=confidence,
            runner_up_id=RUNNER,
            runner_up_confidence=0.05,
            escalated_model_used=used,
        )

    return _diagnose


def make_treat(dose: str | None = None, extra_product: Product | None = None):
    def _treat(entry_json: dict, transcript: str) -> Treatment:
        products = [Product(**p) for p in entry_json["treatment"]["products"]]
        if dose and products:
            products[0] = products[0].model_copy(update={"dose": dose})
        if extra_product:
            products.append(extra_product)
        return Treatment(
            summary="पत्ते हटाएँ और छिड़काव करें",
            steps=["पीले पत्ते तोड़कर नष्ट करें", "दवा लेबल अनुसार छिड़कें"],
            products=products,
            organic=list(entry_json["treatment"].get("organic", [])),
        )

    return _treat


IMG = b"\xff\xd8fakejpegdata"

HAPPY = dict(
    triage=make_triage(),
    diagnose=make_diagnose(0.9),
    treat=make_treat(),
)


def test_happy_path_reaches_a_spoken_plan() -> None:
    result = run_diagnosis_pipeline(IMG, transcript="dhabbe lag rahe hain", **HAPPY)

    assert isinstance(result, PipelineResult)
    assert result.status == "treated"
    assert result.kb_entry_id == DISEASE
    assert result.treatment_final is not None
    assert result.safety is not None
    assert any("दस्ताने" in line for line in result.spoken_addendum), "PPE must travel with chemicals"


def test_unusable_photo_returns_retake_never_advice() -> None:
    result = run_diagnosis_pipeline(
        IMG, triage=make_triage(usable=False), diagnose=make_diagnose(0.9), treat=make_treat()
    )

    assert result.status == "retake"
    assert result.treatment_final is None
    assert result.diagnosis is None, "no model cost after a failed triage"


def test_low_confidence_without_escalation_is_fail_closed() -> None:
    result = run_diagnosis_pipeline(
        IMG, triage=make_triage(), diagnose=make_diagnose(0.55), treat=make_treat()
    )

    assert result.status == "escalated"
    assert result.treatment_final is None


def test_escalation_rescue_is_bounded_to_one_recheck() -> None:
    calls: list[int] = []

    def escalating(image: bytes, candidates: list[tuple[str, str]]) -> DiagnosisOutcome:
        calls.append(1)
        return DiagnosisOutcome(DISEASE, "Early blight", 0.88, RUNNER, 0.05)

    result = run_diagnosis_pipeline(
        IMG,
        triage=make_triage(),
        diagnose=make_diagnose(0.55),
        escalate=escalating,
        treat=make_treat(),
    )

    assert result.status == "treated"
    assert result.diagnosis is not None
    assert result.diagnosis.escalated_model_used is True
    assert len(calls) == 1


def test_gate_blocks_when_treatment_invents_an_ingredient() -> None:
    intruder = Product(
        name="Mystery 100 EC",
        active_ingredient="mystery",
        dose="1.0",
        dose_max="1.0",
        unit="ml per litre",
        phi_days=7,
        label_source="nowhere",
    )
    result = run_diagnosis_pipeline(
        IMG,
        triage=make_triage(),
        diagnose=make_diagnose(0.9),
        treat=make_treat(extra_product=intruder),
    )

    assert result.status == "blocked"
    assert result.treatment_final is None
    assert result.kb_entry_id == DISEASE, "blocked results still name the KB entry"


def test_translated_product_names_are_repaired_from_the_kb() -> None:
    """A model that restates 'Mancozeb 75 WG' as 'मंकोज़ेब 75 WG' is repaired,
    not blocked: the KB stays the single source of truth."""

    def translated_treat(entry_json: dict, transcript: str) -> Treatment:
        draft = make_treat()(entry_json, transcript)
        first = draft.products[0].model_copy(update={"name": "मंकोज़ेब 75 डब्ल्यूजी"})
        return draft.model_copy(update={"products": [first, *draft.products[1:]]})

    result = run_diagnosis_pipeline(
        IMG,
        triage=make_triage(),
        diagnose=make_diagnose(0.9),
        treat=translated_treat,
    )

    assert result.status == "treated"
    assert result.treatment_final is not None
    names = [p.name for p in result.treatment_final.products]
    assert names[0] == "Mancozeb 75 WG", "shipped product names are KB-verbatim"


def test_pipeline_ships_kb_verbatim_doses_even_when_model_overstates() -> None:
    """Products are rebuilt verbatim from the KB before the gate, so an
    overlabel dose drafted by a model never reaches the farmer. The gate's
    own R2 test proves the second line of defense."""

    result = run_diagnosis_pipeline(
        IMG,
        triage=make_triage(),
        diagnose=make_diagnose(0.9),
        treat=make_treat(dose="3.5"),
    )

    assert result.status == "treated"
    assert result.treatment_final is not None
    assert result.treatment_final.products[0].dose == "2.0", "KB dose wins over the model draft"
    assert result.treatment_final.products[0].dose_max_value >= result.treatment_final.products[0].dose_value


def test_poison_transcript_overrides_everything() -> None:
    result = run_diagnosis_pipeline(
        IMG, transcript="papa ne dawa pi li", triage=make_triage(), diagnose=make_diagnose(0.9), treat=make_treat()
    )

    assert result.status == "escalated"
    assert result.treatment_final is None
    assert any("112" in line for line in result.spoken_addendum)


def test_search_prefilters_by_symptom_keywords() -> None:
    entries = load_all_entries()

    candidates = search_kb_candidates("tomato", "concentric rings wale dhabbe, yellow halo", entries=entries)

    assert candidates, "must always return candidates"
    assert candidates[0][0] == DISEASE, "ringed spots with yellow halo must rank early blight first"
    assert all(len(candidate) == 3 and candidate[2] for candidate in candidates), (
        "candidates must carry symptom lists for the diagnosis prompt"
    )


def test_search_with_empty_transcript_returns_stable_crop_entries() -> None:
    entries = load_all_entries()

    candidates = search_kb_candidates("tomato", "", entries=entries)

    ids = [candidate[0] for candidate in candidates]
    assert len(ids) == 3
    assert ids == sorted(ids), "stable order with no signal"
    assert all(kb_id.startswith("tomato") for kb_id in ids)


def test_search_unknown_crop_falls_back_to_catalog() -> None:
    entries = load_all_entries()

    candidates = search_kb_candidates("mango", "rings on leaves", entries=entries)

    assert candidates
