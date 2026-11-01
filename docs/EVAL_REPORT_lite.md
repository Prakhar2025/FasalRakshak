# Evaluation Report

Generated: 2026-11-01 | Model: `us.amazon.nova-lite-v1:0` | Protocol: docs/EVAL_PLAN.md | Manifest: frozen seed 20261104

## Headline

| Metric | Value |
|---|---|
| Disease images | 423 |
| Top-1 accuracy | 0.2009 |
| Top-2 accuracy | 0.26 |
| Healthy escalation rate | 0.0 (43 images) |
| Bedrock errors after retries | 34 |
| Diagnosis latency p50 / p95 | 3125 ms / 3936 ms |

## Per class

| Class | Correct / Total | Accuracy |
|---|---|---|
| tomato-bacterial-spot | 1 / 48 | 0.0208 |
| tomato-early-blight | 30 / 48 | 0.625 |
| tomato-late-blight | 2 / 48 | 0.0417 |
| tomato-leaf-mold | 0 / 47 | 0.0 |
| tomato-mosaic-virus | 0 / 47 | 0.0 |
| tomato-septoria-leaf-spot | 43 / 47 | 0.9149 |
| tomato-spider-mites | 0 / 46 | 0.0 |
| tomato-target-spot | 0 / 46 | 0.0 |
| tomato-yellow-leaf-curl-virus | 9 / 46 | 0.1957 |

## Calibration (confidence vs correctness)

| Confidence band | Correct / Total | Accuracy |
|---|---|---|
| below_0.70 | 0 / 0 | None |
| 0.70_0.85 | 74 / 395 | 0.1873 |
| above_0.85 | 11 / 28 | 0.3929 |

## Honest notes

- Numbers are produced by `eval/run_eval.py` from the frozen manifest; rerun to reproduce.
- Images are PlantVillage laboratory photos (plain background); field photos are harder.
- Latency measures the diagnosis stage only, with parallel workers, not the full voice pipeline.
