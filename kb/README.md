# Knowledge Base: curation guide

The knowledge base is the citable brain of FasalRakshak. It lives in this
directory as versioned JSON, reviewed like code. Nothing enters an agent's
answer that does not come from here and pass the safety gate.

## Layout

```
kb/
  tomato/                 one JSON file per disease or pest
  cotton/                 one JSON file per disease
  banned_pesticides.json  CIB&RC banned and restricted snapshot, dated
```

## Rules for every entry

1. **Schema first.** Every file validates against `src/fasalrakshak/schemas.py`
   (see `docs/DATA_SCHEMA.md`). Tests run on every commit.
2. **A source or it does not exist.** `source.org` and `source.title` are
   mandatory; `url` where stable; `accessed` is the verification date.
3. **Dose discipline.** `dose` is the recommended rate, `dose_max` is the
   label ceiling. The safety gate refuses anything above `dose_max`, and
   tests fail if any entry recommends more than its own ceiling.
4. **No banned ingredients.** `active_ingredient` is checked against
   `banned_pesticides.json` at commit time and at runtime (Phase 2 gate).
5. **Chemical entries carry PPE notes.** Any entry with products must include
   a wear-PPE safety note and PHI guidance.
6. **Virus entries say so.** Viruses have no chemical cure; their entries list
   vector control and sanitation, with empty or biological product lists.
   Honesty here is a feature.

## Adding a crop

The schema is crop-agnostic. Adding a crop means adding a folder of JSON
files, nothing else. That is the point of the architecture: proven on tomato
and cotton, designed for any crop.

## Verification duties

- **PHI and doses:** values here come from state advisories and registered
  labels as cited. Before any public release, re-verify PHI and dose ceilings
  against the actual product labels for the marketed formulations.
- **Banned list:** the snapshot is dated. Re-verify against the live CIB&RC
  lists (agriwelfare.gov.in / cibrc.nic.in) before any public release, and
  update `snapshot_date`.

## Current scope

- Tomato: 9 entries (8 diseases plus two-spotted spider mite damage)
- Cotton: 7 diseases
- Banned snapshot: 19 active ingredients with citations
