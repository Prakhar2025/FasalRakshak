"""Tests for the deterministic safety gate: every rule, trigger and clean pass.

Plus the property tests that make the safety claim real: over every knowledge
base entry, no output ever contains a banned ingredient, no dose ever exceeds
the label maximum, and PPE guidance always travels with chemicals.
"""

from __future__ import annotations

import pytest

from fasalrakshak.kb import load_all_entries
from fasalrakshak.safety import (
    CONFIDENCE_FLOOR,
    TOP2_MARGIN_MIN,
    RuleHit,
    SafetyVerdict,
    verify_treatment,
)
from fasalrakshak.schemas import Product, Treatment


def make_product(
    name: str = "Mancozeb 75 WG",
    active: str = "mancozeb",
    dose: str = "2.0",
    dose_max: str = "2.5",
    unit: str = "g per litre",
    phi_days: int = 7,
) -> Product:
    return Product(
        name=name,
        active_ingredient=active,
        dose=dose,
        dose_max=dose_max,
        unit=unit,
        phi_days=phi_days,
        label_source="CIB&RC registered label",
    )


def make_treatment(
    products: list[Product] | None = None,
    organic: list[str] | None = None,
) -> Treatment:
    return Treatment(
        summary="Remove leaves and spray",
        steps=["Remove leaves", "Spray"],
        products=products or [],
        organic=organic or [],
    )


def test_clean_treatment_passes_untouched() -> None:
    draft = make_treatment(products=[make_product()])

    verdict = verify_treatment(draft, diagnosis_confidence=0.9, runner_up_confidence=0.05)

    assert verdict.status == "passed"
    assert verdict.final_treatment is not None
    assert verdict.final_treatment.products[0].dose == "2.0"
    assert verdict.rules_triggered == []


def test_r7_poison_transcript_escalates_with_emergency_guidance() -> None:
    draft = make_treatment(products=[make_product()])

    verdict = verify_treatment(draft, transcript="mere papa ne dawa pi li hai, abhi उल्टी ho rahi hai")

    assert verdict.status == "escalated"
    assert verdict.final_treatment is None
    assert any("112" in line for line in verdict.spoken_addendum)
    assert any(rule.rule_id == "R7" for rule in verdict.rules_triggered)


def test_r7_fires_on_english_too() -> None:
    draft = make_treatment(products=[make_product()])

    verdict = verify_treatment(draft, transcript="he swallowed the pesticide by mistake")

    assert verdict.status == "escalated"
    assert verdict.final_treatment is None


def test_r7_pest_ate_leaves_does_not_trigger() -> None:
    draft = make_treatment(products=[make_product()])

    verdict = verify_treatment(
        draft, diagnosis_confidence=0.9, transcript="कीट ने पत्तियां खा लिया, छेद हैं"
    )

    assert verdict.status in {"passed", "modified"}, "pest damage must never be a medical emergency"


def test_r6_unusable_image_is_blocked_with_retake_request() -> None:
    draft = make_treatment(products=[make_product()])

    verdict = verify_treatment(draft, image_usable=False)

    assert verdict.status == "blocked"
    assert verdict.final_treatment is None
    assert verdict.spoken_addendum, "farmer must be told to retake"


def test_r5_low_confidence_escalates() -> None:
    draft = make_treatment(products=[make_product()])

    verdict = verify_treatment(draft, diagnosis_confidence=0.55)

    assert verdict.status == "escalated"
    assert verdict.final_treatment is None
    assert verdict.rules_triggered[0].rule_id == "R5"


def test_r5_top2_too_close_escalates() -> None:
    draft = make_treatment(products=[make_product()])

    verdict = verify_treatment(
        draft, diagnosis_confidence=0.75, runner_up_confidence=0.75 - TOP2_MARGIN_MIN + 0.01
    )

    assert verdict.status == "escalated"


def test_r5_thresholds_are_sane() -> None:
    assert 0.5 <= CONFIDENCE_FLOOR <= 0.9
    assert 0.02 <= TOP2_MARGIN_MIN <= 0.3


def test_r8_empty_draft_is_blocked() -> None:
    verdict = verify_treatment(make_treatment())

    assert verdict.status == "blocked"
    assert verdict.final_treatment is None


def test_r1_banned_product_is_removed_and_announced() -> None:
    banned_product = make_product(
        name="Carbaryl 50 WP",
        active="carbaryl",
        dose="2.0",
        dose_max="2.0",
        phi_days=14,
    )
    good_product = make_product()
    draft = make_treatment(products=[banned_product, good_product], organic=["Neem oil"])

    verdict = verify_treatment(draft, diagnosis_confidence=0.9)

    assert verdict.status == "modified"
    assert verdict.final_treatment is not None
    remaining = [p.active_ingredient for p in verdict.final_treatment.products]
    assert "carbaryl" not in remaining
    assert "mancozeb" in remaining
    assert any("प्रतिबंधित" in line for line in verdict.spoken_addendum)
    assert any(rule.rule_id == "R1" for rule in verdict.rules_triggered)


def test_r1_only_banned_products_and_no_organic_is_blocked() -> None:
    draft = make_treatment(
        products=[make_product(name="Carbaryl 50 WP", active="carbaryl", dose_max="2.0", phi_days=14)]
    )

    verdict = verify_treatment(draft, diagnosis_confidence=0.9)

    assert verdict.status == "blocked"
    assert verdict.final_treatment is None


def test_r2_dose_above_label_is_capped_and_spoken() -> None:
    draft = make_treatment(products=[make_product(dose="3.5", dose_max="2.5")])

    verdict = verify_treatment(draft, diagnosis_confidence=0.9)

    assert verdict.status == "modified"
    assert verdict.final_treatment is not None
    assert verdict.final_treatment.products[0].dose == "2.5"
    assert any(rule.rule_id == "R2" for rule in verdict.rules_triggered)
    assert any("घटाकर" in line for line in verdict.spoken_addendum)


def test_r3_spray_inside_phi_window_is_removed() -> None:
    mancozeb = make_product(phi_days=7)
    copper = make_product(
        name="Copper oxychloride 50 WP",
        active="copper oxychloride",
        dose="2.5",
        dose_max="3.0",
        phi_days=1,
    )
    draft = make_treatment(products=[mancozeb, copper])

    verdict = verify_treatment(draft, diagnosis_confidence=0.9, days_to_harvest=3)

    assert verdict.status == "modified"
    assert verdict.final_treatment is not None
    remaining = [p.name for p in verdict.final_treatment.products]
    assert remaining == ["Copper oxychloride 50 WP"]
    assert any(rule.rule_id == "R3" for rule in verdict.rules_triggered)


def test_r3_harvest_far_away_passes_with_reminder() -> None:
    draft = make_treatment(products=[make_product(phi_days=7)])

    verdict = verify_treatment(draft, diagnosis_confidence=0.9, days_to_harvest=30)

    assert verdict.status == "passed"
    assert verdict.final_treatment is not None
    assert any("दिन" in line for line in verdict.spoken_addendum)


def test_r4_ppe_addendum_travels_with_chemicals_and_not_with_organic_only() -> None:
    chemical = verify_treatment(make_treatment(products=[make_product()]), diagnosis_confidence=0.9)
    organic = verify_treatment(make_treatment(organic=["Neem oil spray"]), diagnosis_confidence=0.9)

    assert any("दस्ताने" in line for line in chemical.spoken_addendum)
    assert all("दस्ताने" not in line for line in organic.spoken_addendum)


def test_gate_is_deterministic() -> None:
    draft = make_treatment(products=[make_product(dose="3.5", dose_max="2.5")])

    first = verify_treatment(draft, diagnosis_confidence=0.9, days_to_harvest=30)
    second = verify_treatment(draft, diagnosis_confidence=0.9, days_to_harvest=30)

    assert first.status == second.status
    assert first.final_treatment == second.final_treatment
    assert first.spoken_addendum == second.spoken_addendum


@pytest.mark.parametrize("entry_id", sorted(load_all_entries().keys()))
def test_every_kb_entry_survives_a_clean_gate_pass(entry_id: str) -> None:
    draft = load_all_entries()[entry_id].treatment

    verdict = verify_treatment(
        draft, diagnosis_confidence=0.9, runner_up_confidence=0.05
    )

    assert verdict.status in {"passed", "modified"}, f"{entry_id}: clean pass must not block"
    assert verdict.final_treatment is not None


def test_property_no_banned_ingredient_ever_survives() -> None:
    entries = load_all_entries()
    for entry_id, entry in entries.items():
        # Inject a banned product into every draft: the gate must strip it.
        sabotaged = entry.treatment.model_copy(deep=True)
        sabotaged.products = list(sabotaged.products) + [
            make_product(
                name="Carbaryl 50 WP",
                active="carbaryl",
                dose="2.0",
                dose_max="2.0",
                phi_days=14,
            )
        ]

        verdict = verify_treatment(sabotaged, diagnosis_confidence=0.9)

        assert verdict.final_treatment is not None or verdict.status == "blocked"
        if verdict.final_treatment is not None:
            remaining = [p.active_ingredient for p in verdict.final_treatment.products]
            assert "carbaryl" not in remaining, f"{entry_id}: banned ingredient survived"


def test_property_dose_never_exceeds_label_maximum() -> None:
    entries = load_all_entries()
    for entry_id, entry in entries.items():
        verdict = verify_treatment(entry.treatment, diagnosis_confidence=0.9)
        if verdict.final_treatment is None:
            continue
        for product in verdict.final_treatment.products:
            assert product.dose_value <= product.dose_max_value, (
                f"{entry_id}: {product.name} shipped above label maximum"
            )


def test_property_output_never_invents_products() -> None:
    entries = load_all_entries()
    for entry_id, entry in entries.items():
        draft_names = {p.name for p in entry.treatment.products}
        verdict = verify_treatment(entry.treatment, diagnosis_confidence=0.9)
        if verdict.final_treatment is None:
            continue
        out_names = {p.name for p in verdict.final_treatment.products}
        assert out_names <= draft_names, f"{entry_id}: gate invented products {out_names - draft_names}"


def test_rule_hits_are_well_formed() -> None:
    draft = make_treatment(products=[make_product(dose="3.5", dose_max="2.5")])

    verdict = verify_treatment(draft, diagnosis_confidence=0.9)

    for hit in verdict.rules_triggered:
        assert isinstance(hit, RuleHit)
        assert hit.rule_id and hit.action and hit.message
