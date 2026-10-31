# Evaluation Plan

Every number this project publishes comes from this plan, run by one script,
with a fixed seed, on data that never changed after tuning. No exceptions.

## Goal

Measure, honestly, how well the diagnosis stage works on images it has never
seen, and how honestly it refuses when it should.

## Dataset

- Source: PlantVillage, tomato leaf classes (public research dataset).
- Classes: the 9 tomato disease classes plus healthy, 10 total.
- Selection: 500 images, stratified 50 per class, drawn with a fixed seed
  (`seed = 20261104`), from a split performed once and frozen.
- The held-out set is written once to `data/eval/manifest.json` (local only,
  gitignored). After that, no image is added, removed, or re-weighted.
- Negatives: 30 non-leaf and non-plant images (random objects, screenshots)
  for refusal testing, fixed and versioned as a manifest alongside.

Cotton note: the cotton knowledge base is curated and citable, but no
large open cotton image benchmark is claimed. Cotton evaluation is
qualitative and labeled as such. The headline benchmark number is tomato
only. Honesty over coverage.

## Metrics

| Metric | Definition | Why |
|---|---|---|
| Top-1 accuracy | predicted KB disease id equals label | headline number |
| Top-2 accuracy | label in top-2 predictions | clinical usefulness margin |
| Calibration | accuracy within confidence bands | supports the R5 threshold choice |
| Refusal correctness | share of negatives correctly refused | fail-closed proof |
| Latency | p50 and p95 end-to-end, voice path separate | user experience claim |

## Procedure

1. `eval/run_eval.py --manifest data/eval/manifest.json --out docs/EVAL_REPORT.md`
2. For each image: run triage and diagnosis exactly as production does.
3. Record: prediction, confidence, latency, gate status.
4. Aggregate into the report tables. The script writes the report; humans do
   not hand-edit numbers. Ever.

## Honesty policy

- The script and the manifest are committed. Anyone can rerun the benchmark.
- If a number looks bad, it is published anyway with analysis. The article
  says what the system cannot do, in its own section.
- If the pipeline changes in a way that affects diagnosis, the benchmark is
  rerun and the report regenerated before any public claim is updated.

## Report

`docs/EVAL_REPORT.md` is generated in Phase 6. Until then this document is
the promise; the report is the proof.
