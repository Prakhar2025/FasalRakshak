"""The deterministic safety gate.

This module is the contract written in docs/SAFETY_RULES.md, in code.

Properties that matter more than cleverness:

- Pure Python. No model access. No network access. No randomness.
- It verifies, rewrites from knowledge-base fields, or refuses. It never
  invents a treatment.
- Fail closed: uncertainty becomes a human escalation, never advice.
- A model cannot talk its way past this gate, because no model decides
  whether the gate runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .kb import load_banned_list
from .schemas import BannedList, Treatment

VerdictStatus = Literal["passed", "modified", "blocked", "escalated"]

# Provisional calibration for rule R5. Phase 6 benchmark data (confidence
# bands vs accuracy) is the justification exercise; adjust only with the
# report in front of you, never by feel.
CONFIDENCE_FLOOR = 0.70
TOP2_MARGIN_MIN = 0.10

# Rule R7: signs of acute human pesticide exposure. Deliberately specific
# phrases rather than single words, so "the pest ate the leaves" (कीट ने खा
# लिया) can never trigger a medical emergency path.
_POISON_SIGNALS = (
    "poison",
    "ingested",
    "swallowed",
    "drank the spray",
    "drank pesticide",
    "zeher",
    "ज़हर",
    "जहर",
    "दवा पी",
    "दवा खा",
    "कीटनाशक पी",
    "कीटनाशक खा",
    "उल्टी",
    "चक्कर आ",
    "सांस लेने में",
    "बेहोश",
    "unconscious",
    # Romanized Hinglish variants. Always medicine-or-chemical plus the verb,
    # never the bare verb: "pani pi liya" (drank water) must stay harmless.
    "dawa pi",
    "dava pi",
    "dawai pi",
    "dawa pee",
    "dava pee",
    "dawa kha",
    "dava kha",
    "pesticide pi",
    "pesticide kha",
    "spray pi",
)

_PPE_ADDENDUM = "छिड़काव करते समय दस्ताने, मास्क और पूरे कपड़े पहनें।"

_EMERGENCY_ADDENDUM = (
    "यह फसल सलाह नहीं है, यह आपातकाल है।",
    "तुरंत 112 पर कॉल करें या नज़दीकी अस्पताल जाएँ।",
    "जिस दवा का संपर्क हुआ उसका डिब्बा या लेबल डॉक्टर के साथ ले जाएँ।",
    "राष्ट्रीय पॉइज़न सूचना केंद्र (AIIMS): 1800-111-171।",
)

_RETAKE_ADDENDUM = "यह फोटो ठीक से नहीं आई। पत्ती को साफ रोशनी में, पास से दोबारा फोटो लें।"

_ESCALATE_ADDENDUM = "यह तस्वीर अपने कृषि अधिकारी को दिखाएँ। अनुमान से दवा सुझाना सुरक्षित नहीं है।"


@dataclass(frozen=True)
class RuleHit:
    """One rule that fired, why, and what the gate did about it."""

    rule_id: str
    action: str
    message: str


@dataclass
class SafetyVerdict:
    """The gate's answer. See docs/SAFETY_RULES.md for the status contract."""

    status: VerdictStatus
    rules_triggered: list[RuleHit] = field(default_factory=list)
    final_treatment: Treatment | None = None
    spoken_addendum: list[str] = field(default_factory=list)


def _hit(verdict: SafetyVerdict, rule_id: str, action: str, message: str) -> None:
    verdict.rules_triggered.append(RuleHit(rule_id=rule_id, action=action, message=message))


def _r7_poison_suspected(transcript: str) -> bool:
    text = transcript.lower()
    return any(signal in text for signal in _POISON_SIGNALS)


def verify_treatment(
    draft: Treatment,
    *,
    diagnosis_confidence: float | None = None,
    runner_up_confidence: float | None = None,
    image_usable: bool = True,
    transcript: str = "",
    days_to_harvest: int | None = None,
    banned: BannedList | None = None,
) -> SafetyVerdict:
    """Run rules R1 to R8 over a drafted treatment, in the docs order.

    Human safety (R7) is checked first and overrides everything. The rules
    then run in documents order: R6 triage re-check, R5 confidence, R8
    emptiness, R1 banned, R2 dose caps, R3 PHI, R4 PPE.
    """
    verdict = SafetyVerdict(status="passed")
    treatment = draft.model_copy(deep=True)

    # R7: acute human exposure overrides everything.
    if _r7_poison_suspected(transcript):
        _hit(verdict, "R7", "escalated", "transcript indicates possible human pesticide exposure")
        verdict.status = "escalated"
        verdict.final_treatment = None
        verdict.spoken_addendum.extend(_EMERGENCY_ADDENDUM)
        return verdict

    # R6: the gate re-checks triage, defensively.
    if not image_usable:
        _hit(verdict, "R6", "blocked", "image unusable, no diagnosis possible")
        verdict.status = "blocked"
        verdict.final_treatment = None
        verdict.spoken_addendum.append(_RETAKE_ADDENDUM)
        return verdict

    # R5: uncertainty escalates, it never becomes advice.
    if diagnosis_confidence is not None:
        if diagnosis_confidence < CONFIDENCE_FLOOR:
            _hit(
                verdict,
                "R5",
                "escalated",
                f"diagnosis confidence {diagnosis_confidence:.2f} below floor {CONFIDENCE_FLOOR:.2f}",
            )
            verdict.status = "escalated"
            verdict.final_treatment = None
            verdict.spoken_addendum.append(_ESCALATE_ADDENDUM)
            return verdict
        if (
            runner_up_confidence is not None
            and (diagnosis_confidence - runner_up_confidence) < TOP2_MARGIN_MIN
        ):
            _hit(
                verdict,
                "R5",
                "escalated",
                "top-2 candidates too close to call safely",
            )
            verdict.status = "escalated"
            verdict.final_treatment = None
            verdict.spoken_addendum.append(_ESCALATE_ADDENDUM)
            return verdict

    # R8: an empty draft is nothing to give.
    if not treatment.products and not treatment.organic:
        _hit(verdict, "R8", "blocked", "draft treatment has no products and no organic steps")
        verdict.status = "blocked"
        verdict.final_treatment = None
        verdict.spoken_addendum.append(_ESCALATE_ADDENDUM)
        return verdict

    # R1: banned active ingredients are removed, with an alternative if the
    # knowledge base provided one.
    banned_list = banned or load_banned_list()
    kept: list = []
    for product in treatment.products:
        status = banned_list.ingredient_status(product.active_ingredient)
        if status == "banned":
            _hit(
                verdict,
                "R1",
                "removed_product",
                f"{product.name}: {product.active_ingredient} is banned in India",
            )
            verdict.spoken_addendum.append(
                f"{product.name} भारत में प्रतिबंधित है। इसका उपयोग बिल्कुल न करें।"
            )
            continue
        kept.append(product)
    if len(kept) < len(treatment.products):
        verdict.status = "modified"
    treatment.products = kept

    # R2: the label is the law. Doses above the label maximum are capped, and
    # the correction is spoken, not silent.
    for product in treatment.products:
        if product.dose_value > product.dose_max_value:
            _hit(
                verdict,
                "R2",
                "capped_dose",
                f"{product.name}: {product.dose} {product.unit} exceeds label maximum "
                f"{product.dose_max} {product.unit}",
            )
            product_dose = product.model_copy(update={"dose": product.dose_max})
            treatment.products = [
                product_dose if p is product else p for p in treatment.products
            ]
            verdict.spoken_addendum.append(
                f"खुराक लेबल के अनुसार घटाकर {product.dose_max} {product.unit} कर दी गई है।"
            )
            verdict.status = "modified"

    # R3: pre-harvest interval. A spray inside the PHI window is removed, and
    # any chemical plan gets a PHI reminder.
    if days_to_harvest is not None and treatment.products:
        offending = [p for p in treatment.products if p.phi_days >= days_to_harvest]
        if offending:
            for product in offending:
                _hit(
                    verdict,
                    "R3",
                    "removed_product",
                    f"{product.name}: PHI {product.phi_days} days, harvest in "
                    f"{days_to_harvest} days, spray not safe",
                )
                verdict.spoken_addendum.append(
                    f"{product.name} का छिड़काव अब न करें: फसल तोड़ने से पहले "
                    f"{product.phi_days} दिन का इंतज़ार ज़रूरी है।"
                )
            treatment.products = [
                p for p in treatment.products if not any(p is o for o in offending)
            ]
            verdict.status = "modified"
        else:
            max_phi = max(p.phi_days for p in treatment.products)
            verdict.spoken_addendum.append(
                f"फसल तोड़ने से कम से कम {max_phi} दिन पहले तक छिड़काव न करें।"
            )

    # R4: PPE guidance is mandatory and non-strippable for chemical plans.
    if treatment.products:
        verdict.spoken_addendum.append(_PPE_ADDENDUM)

    # If the rules left nothing to give, fail closed.
    if not treatment.products and not treatment.organic:
        _hit(verdict, "R8", "blocked", "no products and no organic steps remain after gate rules")
        verdict.status = "blocked"
        verdict.final_treatment = None
        verdict.spoken_addendum.append(_ESCALATE_ADDENDUM)
        return verdict

    verdict.final_treatment = treatment
    return verdict
