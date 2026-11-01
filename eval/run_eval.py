"""Run the frozen diagnosis benchmark against real Bedrock.

Reads the manifest built by eval/build_manifest.py, sends every held-out
image through the real DiagnosisAgent with the full candidate list, and
writes results plus the report. Healthy images are scored separately and
honestly: a healthy leaf should NOT match any disease candidate confidently,
so the metric is the escalation rate (confidence below the R5 floor).

Usage:
    python eval/run_eval.py --manifest data/eval/manifest.json --model lite
    python eval/run_eval.py --manifest data/eval/manifest.json --model pro --subset 100
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import random
import statistics
import time
from datetime import date
from pathlib import Path

from fasalrakshak.agents import AgentOutputError, DiagnosisAgent
from fasalrakshak.kb import load_all_entries
from fasalrakshak.safety import CONFIDENCE_FLOOR

MODELS = {
    "lite": "us.amazon.nova-lite-v1:0",
    "pro": "us.amazon.nova-pro-v1:0",
}
WORKERS = 3
RETRIES = 4
RETRY_SLEEP = 3.0


def load_cases(manifest_path: Path, subset: int | None) -> list[dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = Path(manifest["source_root"])
    cases: list[dict] = []
    for kb_id, info in manifest["classes"].items():
        selected = info["selected"]
        if subset is not None:
            per_class = max(1, subset // max(1, len(manifest["classes"])))
            rng = random.Random(f"{manifest['seed']}-subset{subset}-{kb_id}")
            rng.shuffle(selected)
            selected = selected[:per_class]
        for name in selected:
            cases.append(
                {
                    "path": source / info["dir"] / name,
                    "expected": kb_id,
                }
            )
    return cases


def is_retryable(error_text: str) -> bool:
    signals = ("Throttling", "throttl", "429", "5xx", "ServiceUnavailable", "timeout", "Rate")
    return any(signal in error_text for signal in signals)


def evaluate_one(case: dict, candidates: list, model_id: str) -> dict:
    """Fresh agent per image: the Strands Agent is stateful and accumulates
    conversation history, so a shared instance would answer from history
    instead of the new image (and blow the context limits)."""
    image = case["path"].read_bytes()
    agent = DiagnosisAgent(model_id=model_id)
    start = time.monotonic()
    last_error: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            result = agent.run(image, candidates)
            latency_ms = int((time.monotonic() - start) * 1000)
            return {
                "file": str(case["path"]),
                "expected": case["expected"],
                "predicted": result.disease_id,
                "label": result.label,
                "confidence": result.confidence,
                "runner_up": result.runner_up_id,
                "latency_ms": latency_ms,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001 - transient AWS errors retry with backoff
            last_error = exc
            text = f"{type(exc).__name__}: {exc}"
            if attempt < RETRIES and is_retryable(text):
                backoff = min(30.0, RETRY_SLEEP * (2**attempt)) + random.uniform(0, 2.0)
                time.sleep(backoff)
                continue
            if attempt < RETRIES:
                time.sleep(RETRY_SLEEP)
                continue
    return {
        "file": str(case["path"]),
        "expected": case["expected"],
        "predicted": None,
        "label": None,
        "confidence": None,
        "runner_up": None,
        "latency_ms": None,
        "error": f"{type(last_error).__name__}: {last_error}",
    }


def aggregate(rows: list[dict]) -> dict:
    scored = [row for row in rows if row["error"] is None and row["expected"] != "healthy"]
    healthy = [row for row in rows if row["error"] is None and row["expected"] == "healthy"]
    errors = [row for row in rows if row["error"] is not None]

    top1 = sum(1 for row in scored if row["predicted"] == row["expected"])
    top2 = sum(
        1 for row in scored if row["predicted"] == row["expected"] or row["runner_up"] == row["expected"]
    )
    escalations = sum(1 for row in healthy if (row["confidence"] or 0.0) < CONFIDENCE_FLOOR)

    per_class: dict[str, dict] = {}
    for row in scored:
        bucket = per_class.setdefault(row["expected"], {"total": 0, "correct": 0})
        bucket["total"] += 1
        bucket["correct"] += 1 if row["predicted"] == row["expected"] else 0

    latencies = [row["latency_ms"] for row in scored if row["latency_ms"] is not None]
    latencies.sort()

    bands = {"below_0.70": [0, 0], "0.70_0.85": [0, 0], "above_0.85": [0, 0]}
    for row in scored:
        confidence = row["confidence"] or 0.0
        band = "below_0.70" if confidence < 0.70 else ("0.70_0.85" if confidence <= 0.85 else "above_0.85")
        bands[band][0] += 1 if row["predicted"] == row["expected"] else 0
        bands[band][1] += 1

    def percentile(values: list[int], pct: float) -> int:
        if not values:
            return 0
        index = min(len(values) - 1, max(0, int(round(pct / 100 * (len(values) - 1)))))
        return values[index]

    return {
        "disease_images": len(scored),
        "top1": top1,
        "top1_accuracy": round(top1 / len(scored), 4) if scored else None,
        "top2_accuracy": round(top2 / len(scored), 4) if scored else None,
        "healthy_images": len(healthy),
        "healthy_escalation_rate": round(escalations / len(healthy), 4) if healthy else None,
        "errors": len(errors),
        "per_class": {
            kb_id: {
                "total": bucket["total"],
                "correct": bucket["correct"],
                "accuracy": round(bucket["correct"] / bucket["total"], 4) if bucket["total"] else None,
            }
            for kb_id, bucket in sorted(per_class.items())
        },
        "calibration": {
            band: {"correct": value[0], "total": value[1],
                   "accuracy": round(value[0] / value[1], 4) if value[1] else None}
            for band, value in bands.items()
        },
        "latency_ms": {
            "mean": int(statistics.mean(latencies)) if latencies else None,
            "p50": percentile(latencies, 50),
            "p95": percentile(latencies, 95),
        },
    }


def write_report(path: Path, model_key: str, model_id: str, summary: dict) -> None:
    lines = [
        "# Evaluation Report",
        "",
        f"Generated: {date.today().isoformat()} | Model: `{model_id}` | "
        f"Protocol: docs/EVAL_PLAN.md | Manifest: frozen seed 20261104",
        "",
        "## Headline",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Disease images | {summary['disease_images']} |",
        f"| Top-1 accuracy | {summary['top1_accuracy']} |",
        f"| Top-2 accuracy | {summary['top2_accuracy']} |",
        f"| Healthy escalation rate | {summary['healthy_escalation_rate']} ({summary['healthy_images']} images) |",
        f"| Bedrock errors after retries | {summary['errors']} |",
        f"| Diagnosis latency p50 / p95 | {summary['latency_ms']['p50']} ms / {summary['latency_ms']['p95']} ms |",
        "",
        "## Per class",
        "",
        "| Class | Correct / Total | Accuracy |",
        "|---|---|---|",
    ]
    for kb_id, bucket in summary["per_class"].items():
        lines.append(f"| {kb_id} | {bucket['correct']} / {bucket['total']} | {bucket['accuracy']} |")
    lines += [
        "",
        "## Calibration (confidence vs correctness)",
        "",
        "| Confidence band | Correct / Total | Accuracy |",
        "|---|---|---|",
    ]
    for band, bucket in summary["calibration"].items():
        lines.append(f"| {band} | {bucket['correct']} / {bucket['total']} | {bucket['accuracy']} |")
    lines += [
        "",
        "## Honest notes",
        "",
        "- Numbers are produced by `eval/run_eval.py` from the frozen manifest; rerun to reproduce.",
        "- Images are PlantVillage laboratory photos (plain background); field photos are harder.",
        "- Latency measures the diagnosis stage only, with parallel workers, not the full voice pipeline.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="data/eval/manifest.json")
    parser.add_argument("--model", choices=sorted(MODELS), default="lite")
    parser.add_argument("--subset", type=int, default=None, help="stratified per-class subset size")
    parser.add_argument("--workers", type=int, default=WORKERS)
    parser.add_argument("--resume", default=None, help="results file to merge into: rerun only errored rows")
    parser.add_argument("--out", default=None)
    parser.add_argument("--report", default=None)
    args = parser.parse_args()

    model_id = MODELS[args.model]
    cases = load_cases(Path(args.manifest), args.subset)
    cases_by_path = {str(case["path"]): case for case in cases}

    keep_rows: list[dict] = []
    if args.resume and Path(args.resume).exists():
        previous = json.loads(Path(args.resume).read_text(encoding="utf-8"))
        keep_rows = [row for row in previous["rows"] if row["error"] is None]
        kept_paths = {row["file"] for row in keep_rows}
        cases = [case for case in cases if str(case["path"]) not in kept_paths]
        print(f"resume: keeping {len(keep_rows)} scored rows, rerunning {len(cases)} errored rows")

    entries = load_all_entries()
    candidates = [
        (entry.id, entry.disease, list(entry.symptoms))
        for entry in entries.values()
        if entry.crop == "tomato"
    ]
    print(f"model={args.model} cases={len(cases)} candidates={len(candidates)}")

    rows: list[dict] = []
    done = 0
    with futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures_map = {
            pool.submit(evaluate_one, case, candidates, model_id): case for case in cases
        }
        for future in futures.as_completed(futures_map):
            rows.append(future.result())
            done += 1
            if done % 25 == 0:
                print(f"evaluated {done}/{len(cases)}", flush=True)

    rows = keep_rows + rows

    out = Path(args.out or f"data/eval/results_{args.model}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"model": model_id, "rows": rows}, indent=2), encoding="utf-8")

    summary = aggregate(rows)
    report = Path(args.report or f"docs/EVAL_REPORT_{args.model}.md")
    write_report(report, args.model, model_id, summary)

    print(json.dumps({k: v for k, v in summary.items() if k != "per_class"}, indent=2))
    print(f"results: {out}")
    print(f"report: {report}")


if __name__ == "__main__":
    main()
