# Evaluation Report

Generated: 2026-11-01 | Protocol: docs/EVAL_PLAN.md | Manifest: frozen, seed
20261104, 500 held-out PlantVillage tomato images (50 per class, demo images
excluded). Produced by `eval/run_eval.py`; rerun to reproduce.

## Headline

| Metric | Nova Lite | Nova Pro |
|---|---|---|
| Disease images scored | 417 | 449 |
| 9-way top-1 accuracy | 0.1847 | 0.1982 |
| 9-way top-2 accuracy | 0.2446 | 0.3096 |
| **Treatment-family accuracy** | **0.6139** | 0.4788 |
| Healthy escalation rate | 0.2174 | 0.4894 |
| Bedrock errors after retries | 0 | 0 |
| Diagnosis latency p50 | 2141 ms | 2296 ms |

Decision: **Nova Lite stays the primary diagnosis model** (ADR-0001): it
wins the farmer-relevant metric (treatment-family accuracy), costs less, and
answers faster. Pro wins the healthy-escalation behavior; the R5 gate covers
that gap at the pipeline level.

## What "treatment-family accuracy" means and why it is the farmer metric

The nine confusable classes collapse into four treatment families: fungal
(early blight, late blight, Septoria, leaf mold, target spot: mancozeb or
chlorothalonil), bacterial (copper), viral (no chemical cure, vector
control), and mite (sulphur, neem). Two of the fungal classes sharing one
treatment plan means a Septoria/early-blight confusion changes the label but
not the actionable advice. The knowledge base is organized so that the
safety gate validates doses per product, and same-family confusions deliver
the same safe plan.

## The honest headline

Zero-shot multimodal diagnosis of the nine confusable tomato classes on
PlantVillage sits at roughly 20 percent top-1 for both Nova models. We
tried three prompt strategies before accepting this (names-only 0.2222,
few-shot reference images 0.1778, describe-then-classify 0.1333; see
data/eval/experiment_*.json). This is consistent with the known difficulty
of fine-grained plant-disease classification for general-purpose VLMs, and
it is the number we publish rather than the best cherry-picked subset.

The product is designed around this reality instead of hiding it:

1. **Fail closed.** Confidence below the R5 floor escalates to the
   agriculture officer. On healthy leaves, Lite escalates 21.7 percent and
   Pro 48.9 percent; a healthy leaf is the case where a confident wrong
   answer would be most damaging.
2. **Same-family confusion, same safe plan.** Treatment-family accuracy is
   61.4 percent (Lite), and every plan still passes the deterministic
   safety gate with label-capped doses and cited sources.
3. **The known next step** is a supervised classifier distilled from
   PlantVillage as a candidate ranker inside the same pipeline; the
   architecture takes it as a configuration change, not a rebuild.

## Calibration (Nova Lite, confidence vs correctness)

| Confidence band | Correct / Total | Accuracy |
|---|---|---|
| below 0.70 | 23 / 129 | 0.1783 |
| 0.70 to 0.85 | 63 / 314 | 0.2006 |
| above 0.85 | 3 / 6 | 0.5 |

The bands are flat, which is itself a finding: Lite's self-reported
confidence does not separate right from wrong on this benchmark. That is
why the pipeline treats confidence as a safety signal for escalation
thresholds, never as a promise of correctness, and why the roadmap calls
for a calibrated supervised classifier.

## Method notes

- Images: PlantVillage laboratory photos (plain background, single leaf);
  field photos are harder still.
- Latency measures the diagnosis stage only, parallel workers, not the
  voice pipeline.
- Three demo images used in live smoke tests are excluded from the pool.
- Harness correctness note: the Strands Agent is stateful and rejects
  concurrent invocations; the evaluation harness creates a fresh agent per
  image (an earlier shared-agent run produced history-contaminated results
  and was discarded entirely; see git history).
