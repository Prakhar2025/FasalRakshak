# Agent Design

The Strands multi-agent design for FasalRakshak. Four specialists, one
deterministic pipeline, zero model-led routing.

## Agent roster

| Agent | Model | Input | Output | Job in one line |
|---|---|---|---|---|
| Triage | Nova Lite | Image bytes, optional transcript | `{usable, reason, crop_hint}` | Reject bad photos early, cheap and fast |
| Diagnosis | Nova Lite, Nova Pro on low confidence | Image, crop hint, KB candidate list | `{disease_id, label, confidence, alternatives[]}` | Match the photo to a KB disease |
| Treatment | Nova Lite | Matched KB entry, language setting | `{summary, steps[], products[], citations[]}` | Turn the official advisory into plain speech |
| Safety gate | None. Pure Python | Drafted treatment | `{status, rules_triggered[], final_treatment}` | Enforce every hard rule. See SAFETY_RULES.md |

The safety gate is deliberately **not** an agent. It is a pure function with
unit tests. A model can be persuaded. A lookup table cannot.

## Orchestration sequence

Code owns the flow (`src/fasalrakshak/pipeline.py`):

1. Intake: image required, audio optional. If audio exists, Transcribe first.
2. Triage agent. Unusable photo means a polite spoken retake request, pipeline
   stops, zero further model cost.
3. KB pre-filter: symptom keywords from the transcript and crop hint select
   candidate KB entries. This bounds the diagnosis task.
4. Diagnosis agent over candidates. Confidence below threshold triggers one
   Nova Pro re-check, then fusion.
5. No candidate above threshold: escalation path, no treatment is spoken.
6. Treatment agent drafts steps from the matched KB entry only. It may not
   invent products. Products come from the KB entry, verbatim identifiers.
7. Safety gate verifies the draft. Triggered rules rewrite or refuse.
8. Polly speaks the final text. Session persisted. Follow-up scheduled.

## Tool contracts

Tools are plain Python functions registered with Strands. Signatures fixed
here, implemented in later phases:

```python
def check_image_quality(image: bytes) -> TriageResult
def search_kb_candidates(crop: str, symptoms: str) -> list[str]   # disease ids
def load_kb_entry(disease_id: str) -> KBEntry
def verify_treatment(products: list[Product]) -> SafetyVerdict     # the gate
def transcribe_voice_note(audio: bytes) -> str                     # hi-IN
def synthesize_speech(text: str, voice: str = "Kajal") -> AudioRef # hi-IN
def save_session(record: SessionRecord) -> None
def get_session(session_id: str) -> SessionRecord
def save_outcome(session_id: str, outcome: str) -> None
```

Rules for all tools:

- Tools never call the model. Models call tools.
- Tools validate inputs, return typed results, and raise typed errors.
- Every tool is unit-testable without AWS (local fakes in `tests/fakes/`).

## Prompt design principles

1. **Role sentences, not essays.** Each agent gets a short role definition,
   its output contract, and its refusal behavior.
2. **Grounded output only.** Diagnosis may only choose among supplied KB
   candidates. Treatment may only use products present in the KB entry.
3. **Language discipline.** Farmer-facing text is generated in simple Hindi,
   short sentences, no compound words, numbers spoken digit-friendly.
4. **Honesty instructions.** If unsure, say unsure and escalate. Confidence
   values are never inflated by prompt wording.
5. **Deterministic where it matters.** JSON output enforced via structured
   output; malformed output triggers one retry, then fail-closed escalation.

## Memory design

- **Session memory:** one diagnosis conversation, DynamoDB item, expires.
- **Field memory:** per farmer, crop history, prior diagnoses, treatments
  given, outcomes. Powers the follow-up question and lets the diagnosis agent
  see "this field had early blight last month" as context.
- **No PII in demo mode.** Demo sessions use fixed anonymous farmer ids.

## Degraded modes

| Component down | Behavior |
|---|---|
| Voice input | Text box remains |
| Bedrock primary model | Nova Pro, then Claude fallback (ADR-0001) |
| KB mismatch | Escalation message, no treatment |
| Safety gate error | Fail closed, human-handoff message |
| DynamoDB | In-memory session for the request, retry persistence |
