# Evaluation Report

Generated: 2026-11-01 | Model: `us.amazon.nova-pro-v1:0` | Protocol: docs/EVAL_PLAN.md | Manifest: frozen seed 20261104

## Headline

| Metric | Value |
|---|---|
| Disease images | 449 |
| Top-1 accuracy | 0.1982 |
| Top-2 accuracy | 0.3096 |
| Healthy escalation rate | 0.4894 (47 images) |
| Bedrock errors after retries | 4 |
| Diagnosis latency p50 / p95 | 2296 ms / 2672 ms |

## Per class

| Class | Correct / Total | Accuracy |
|---|---|---|
| tomato-bacterial-spot | 21 / 50 | 0.42 |
| tomato-early-blight | 17 / 50 | 0.34 |
| tomato-late-blight | 7 / 50 | 0.14 |
| tomato-leaf-mold | 3 / 50 | 0.06 |
| tomato-mosaic-virus | 5 / 50 | 0.1 |
| tomato-septoria-leaf-spot | 28 / 50 | 0.56 |
| tomato-spider-mites | 2 / 49 | 0.0408 |
| tomato-target-spot | 2 / 50 | 0.04 |
| tomato-yellow-leaf-curl-virus | 4 / 50 | 0.08 |

## Calibration (confidence vs correctness)

| Confidence band | Correct / Total | Accuracy |
|---|---|---|
| below_0.70 | 23 / 129 | 0.1783 |
| 0.70_0.85 | 63 / 314 | 0.2006 |
| above_0.85 | 3 / 6 | 0.5 |

## Honest notes

- Numbers are produced by `eval/run_eval.py` from the frozen manifest; rerun to reproduce.
- Images are PlantVillage laboratory photos (plain background); field photos are harder.
- Latency measures the diagnosis stage only, with parallel workers, not the full voice pipeline.
