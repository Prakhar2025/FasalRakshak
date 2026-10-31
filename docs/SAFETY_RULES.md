# Safety Rules: the deterministic gate

This document is the contract for `src/fasalrakshak/safety.py`. The gate is
pure Python, has no model access, and cannot be overridden by any agent. If
any rule fires, the farmer never hears the unsafe plan.

## Principles

1. **Fail closed.** Uncertainty escalates to a human, it never becomes advice.
2. **Cite everything.** Every rule carries a source: a government list, a
   label, an advisory.
3. **Never exceed the label.** The printed product label is the law.
4. **No diagnosis theater.** Low confidence means "show a person", not a
   confident guess.

## Rules

| ID | Rule | Action on trigger | Source |
|---|---|---|---|
| R1 | Product's active ingredient is on the banned or refused-registration list | Remove product, mark refusal, speak alternative from KB organic list | CIB&RC banned and refused lists, curated snapshot with citation |
| R2 | Proposed dose exceeds the label maximum for the crop | Cap to label maximum, announce the correction | Product label field in KB entry |
| R3 | Pre-harvest interval (PHI) conflicts with expected harvest window | Announce PHI prominently, block spraying within PHI days of harvest | Label and advisory |
| R4 | Any chemical treatment | Append PPE instruction, mandatory, non-strippable | Advisory standard text |
| R5 | Diagnosis confidence below threshold, or top-2 candidates too close | Refuse treatment. Speak: show this to your agriculture officer, with the photo | Eval calibration data sets threshold |
| R6 | Image is not a plant leaf, or is unusable | No diagnosis. Ask for a retake | Triage stage |
| R7 | Farmer transcript indicates acute human health exposure (pesticide ingestion, poisoning signs) | Override everything: speak poison-control guidance and local emergency numbers, no crop advice | Health ministry helpline numbers, static |
| R8 | Treatment total cost fields inconsistent or missing | Block, repair from KB data before speech | Internal consistency |

## Output contract

```python
@dataclass
class SafetyVerdict:
    status: Literal["passed", "modified", "blocked", "escalated"]
    rules_triggered: list[RuleHit]
    final_treatment: Treatment | None
    spoken_addendum: list[str]   # PPE, PHI, escalation lines, in Hindi
```

- `passed`: untouched draft.
- `modified`: R2/R3 corrections applied, addendum explains what changed.
- `blocked`: no treatment spoken. Escalation text instead.
- `escalated`: R5/R7 paths, human handoff.

## Data sources

- `kb/banned_pesticides.json`: curated subset of the CIB&RC (Central
  Insecticides Board and Registration Committee) banned, refused, and
  restricted lists, each entry with `citation` and `status`. Snapshot dated
  in-file. Update task: re-verify at submission.
- Dose caps and PHI: per-product fields in each KB entry, sourced from the
  product label or the originating advisory, recorded in `source`.

## Testing requirements

- Every rule has at least two unit tests: one trigger, one clean pass.
- Property test: no output ever contains a banned active ingredient.
- Property test: dose in output is always at or below label maximum.
- The gate runs in every integration test, including demo-mode fixtures.

## Explicitly out of scope

- The gate never invents treatments. It only verifies, rewrites from KB
  fields, or refuses.
- The gate does not handle human-medical advice beyond R7's static
  escalation text.
