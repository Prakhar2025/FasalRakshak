# Evaluation Report

Generated: 2026-11-01 | Model: `us.amazon.nova-pro-v1:0` | Protocol: docs/EVAL_PLAN.md | Manifest: frozen seed 20261104

## Headline

| Metric | Value |
|---|---|
| Disease images | 262 |
| Top-1 accuracy | 0.1985 |
| Top-2 accuracy | 0.3092 |
| Healthy escalation rate | 1.0 (26 images) |
| Bedrock errors after retries | 212 |
| Diagnosis latency p50 / p95 | 4375 ms / 4797 ms |

## Per class

| Class | Correct / Total | Accuracy |
|---|---|---|
| tomato-bacterial-spot | 0 / 32 | 0.0 |
| tomato-early-blight | 0 / 29 | 0.0 |
| tomato-late-blight | 0 / 29 | 0.0 |
| tomato-leaf-mold | 0 / 29 | 0.0 |
| tomato-mosaic-virus | 0 / 29 | 0.0 |
| tomato-septoria-leaf-spot | 29 / 29 | 1.0 |
| tomato-spider-mites | 23 / 28 | 0.8214 |
| tomato-target-spot | 0 / 28 | 0.0 |
| tomato-yellow-leaf-curl-virus | 0 / 29 | 0.0 |

## Calibration (confidence vs correctness)

| Confidence band | Correct / Total | Accuracy |
|---|---|---|
| below_0.70 | 0 / 59 | 0.0 |
| 0.70_0.85 | 52 / 203 | 0.2562 |
| above_0.85 | 0 / 0 | None |

## Honest notes

- Numbers are produced by `eval/run_eval.py` from the frozen manifest; rerun to reproduce.
- Images are PlantVillage laboratory photos (plain background); field photos are harder.
- Latency measures the diagnosis stage only, with parallel workers, not the full voice pipeline.
