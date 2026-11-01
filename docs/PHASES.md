# Build Phases

Solo build, hackathon deadline. Every phase: build, test, push. Docs change
with behavior. `main` stays green.

| Phase | Scope | Exit criteria | Status |
|---|---|---|---|
| 0 | Documentation, architecture, contracts, skeleton | all docs below committed and pushed | done |
| 1 | Knowledge base: 9 tomato entries, 7 cotton entries, banned list, eval manifest builder | schema tests green, every entry cited, banned consistency proven | done |
| 2 | Deterministic safety gate, pure Python | every rule triggered and passing in unit + property tests | done |
| 3 | Strands agents and pipeline, local run with Bedrock | end-to-end diagnose works locally with a real photo, mocked-AWS tests green | done |
| 4 | Voice loop: Transcribe in, Polly out | voice round trip under budget on a sample | done |
| 5 | FastAPI service and premium web frontend | local end-to-end in browser, demo mode works, design approved by owner | done |
| 6 | Benchmark run and report | EVAL_REPORT.md generated, numbers in README | pending |
| 7 | Deploy to AWS, last | live public URL, smoke tests green, demo mode verified | pending |
| 8 | Article draft, video script, submission package | checklist fully ticked, submitted early | pending |

Workflow: the owner approves the repo state after each phase push before the
next phase starts.

## Phase 0 deliverables (this phase)

README, ARCHITECTURE (5 diagrams), CONTRIBUTING, LICENSE, .gitignore,
requirements.txt, docs: DESIGN, SAFETY_RULES, DATA_SCHEMA, EVAL_PLAN,
API_CONTRACT, VOICE, DEPLOYMENT, SUBMISSION_CHECKLIST, PHASES, and two
decision records.

## Phase 1 deliverables

Typed schemas (pydantic) and a validating loader, 9 tomato entries (8
diseases plus spider mite damage), 7 cotton entries, a 19-ingredient CIB&RC
banned and restricted snapshot with citations, commit-time consistency tests
(no banned ingredient in any treatment, dose never exceeds label maximum,
PPE notes on every chemical entry), and the seeded stratified eval manifest
builder with its CLI. 34 tests green.

## Phase 2 deliverables

`src/fasalrakshak/safety.py`: the deterministic gate, pure Python, no model
access, no randomness. Rules R1 to R8 from docs/SAFETY_RULES.md implemented
in document order with human-exposure override (R7) first. 20 gate tests:
every rule has trigger and clean-pass coverage, plus property tests over the
whole knowledge base: no banned ingredient ever survives the gate, no dose
ever ships above the label maximum, the gate never invents products, and the
gate is deterministic. Full suite: 70 tests green.

## Phase 3 deliverables

`src/fasalrakshak/agents.py`: three Strands agents (triage, diagnosis,
treatment) on Bedrock Nova Lite, context-complete prompt-to-JSON functions
with a tolerant JSON extractor, candidate-bounded diagnosis (the model may
only choose among knowledge-base candidates), and model injection for tests.
`src/fasalrakshak/pipeline.py`: the code-owned orchestration from ADR-0002:
deterministic keyword-overlap candidate search, bounded single Nova Pro
escalation when confidence is low, product-name enforcement against the KB,
and the safety gate as the last hard stage. 18 orchestration and extraction
tests with fake agents (no AWS needed). Suite: 88 tests green. Live smoke
test with a real photo runs as soon as the owner's AWS account has Bedrock
Nova access enabled; a live fire with real credentials is deliberately not
attempted from this repository without them.

## Phase 4 deliverables

`src/fasalrakshak/voice.py`: Amazon Transcribe (hi-IN) voice-note-to-text
through S3 with authenticated transcript fetch, and Amazon Polly (Kajal
neural, hi-IN) text-to-speech, both with injected clients for tests. 6 voice
tests, suite at 94 green.

## Live smoke results (Nov 1, real AWS)

- Bedrock Nova Lite diagnosis on real PlantVillage photos: early blight
  correctly identified at 0.90 to 0.92 confidence; one late blight lab photo
  was called early blight at 0.75, the known confusable pair. The Phase 6
  benchmark will compare Lite and Pro on all 500 images and the result
  decides the model choice, not single photos.
- Voice round trip: Polly spoke "मेरी टमाटर की फसल के पत्तों पर भूरे धब्बे
  हैं, क्या करूँ?" and Transcribe heard it back character for character.
- Diagnosis prompts now carry each candidate's curated symptom list, and the
  triage prompt is constrained to the supported crops (tomato, cotton,
  unknown).

## Phase 5 deliverables

`app/web/`: the farmer frontend. Mobile-first design system (Inter plus Noto
Sans Devanagari, one green accent, high contrast for outdoor use), voice
capture with pulsing record state and typed fallback, photo upload with
preview, demo strip with three PlantVillage samples, skeleton and spinner
states, an audio player for the spoken answer, and fail-closed UX where
every error ends in a clear Hindi message. `src/fasalrakshak/api/`: the
FastAPI service per docs/API_CONTRACT.md with injected pipeline for tests,
demo mode with no personal data, spoken-text assembly, and Polly audio as a
data URI. One pipeline hardening found by live testing: treatment products
are now rebuilt verbatim from the knowledge base by active ingredient, so a
model that translates a product name into Hindi is repaired, and an
invented ingredient is still blocked. Live end-to-end through the real
server: early blight diagnosed at 0.85, KB-verbatim products with PHI,
citation chip, 443-character Hindi spoken script and real Polly audio.
Suite: 105 tests green.
