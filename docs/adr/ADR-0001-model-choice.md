# ADR-0001: Model choice for diagnosis

Status: accepted, 2026-10-31

## Context

Diagnosis is multimodal: leaf photo in, disease class out. Constraints:

- Low latency, voice target under 12 s end to end.
- Low cost: a 500-image benchmark plus demo traffic on a budget.
- Availability in `us-east-1` for the whole stack.
- Hindi voice services must exist in the same region.

## Decision

- Primary: **Amazon Nova Lite** on Bedrock. Multimodal, fast, cheap.
- Escalation: **Amazon Nova Pro**, invoked only when Nova Lite confidence is
  below the R5 threshold, one re-check, then fused verdict.
- Fallback: Claude on Bedrock if the Nova family is unavailable.

## Alternatives considered

- Nova Pro as primary: better borderline accuracy, roughly double the cost
  and latency on every request. Rejected as default, kept as escalation.
- A fine-tuned CNN classifier: strongest raw accuracy on PlantVillage-style
  images, but adds training infra and weakens the KB-grounded, citable
  pipeline that the safety story depends on. Rejected for this scope.

## Consequences

- Calibration data from the benchmark justifies the escalation threshold.
- If Nova Lite proves weak on field photos, the escalation path already
  exists and is one config change.
