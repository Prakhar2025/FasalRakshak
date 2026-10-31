# Build Phases

Solo build, hackathon deadline. Every phase: build, test, push. Docs change
with behavior. `main` stays green.

| Phase | Scope | Exit criteria | Status |
|---|---|---|---|
| 0 | Documentation, architecture, contracts, skeleton | all docs below committed and pushed | done |
| 1 | Knowledge base: 8 tomato, 7 cotton entries, banned list, eval manifest script | schema tests green, every entry cited | pending |
| 2 | Deterministic safety gate, pure Python | every rule triggered and passing in unit + property tests | pending |
| 3 | Strands agents and pipeline, local run with Bedrock | end-to-end diagnose works locally with a real photo, mocked-AWS tests green | pending |
| 4 | Voice loop: Transcribe in, Polly out | voice round trip under budget on a sample | pending |
| 5 | FastAPI service and premium web frontend | local end-to-end in browser, demo mode works, design approved by owner | pending |
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
