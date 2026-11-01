# Evaluation Report

Generated: 2026-11-01 | Model: `us.amazon.nova-lite-v1:0` | Protocol: docs/EVAL_PLAN.md | Manifest: frozen seed 20261104

## Headline

| Metric | Value |
|---|---|
| Disease images | 417 |
| Top-1 accuracy | 0.1847 |
| Top-2 accuracy | 0.2446 |
| Healthy escalation rate | 0.2174 (23 images) |
| Bedrock errors after retries | 60 |
| Diagnosis latency p50 / p95 | 2141 ms / 2578 ms |

## Per class

| Class | Correct / Total | Accuracy |
|---|---|---|
| tomato-bacterial-spot | 0 / 48 | 0.0 |
| tomato-early-blight | 47 / 50 | 0.94 |
| tomato-late-blight | 2 / 50 | 0.04 |
| tomato-leaf-mold | 1 / 50 | 0.02 |
| tomato-mosaic-virus | 0 / 44 | 0.0 |
| tomato-septoria-leaf-spot | 15 / 50 | 0.3 |
| tomato-spider-mites | 0 / 42 | 0.0 |
| tomato-target-spot | 0 / 44 | 0.0 |
| tomato-yellow-leaf-curl-virus | 12 / 39 | 0.3077 |

## Calibration (confidence vs correctness)

| Confidence band | Correct / Total | Accuracy |
|---|---|---|
| below_0.70 | 3 / 31 | 0.0968 |
| 0.70_0.85 | 51 / 335 | 0.1522 |
| above_0.85 | 23 / 51 | 0.451 |

## Honest notes

- Numbers are produced by `eval/run_eval.py` from the frozen manifest; rerun to reproduce.
- Images are PlantVillage laboratory photos (plain background); field photos are harder.
- Latency measures the diagnosis stage only, with parallel workers, not the full voice pipeline.
