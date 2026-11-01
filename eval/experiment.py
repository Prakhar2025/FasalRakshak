"""Quick diagnosis experiments on a stratified subset.

Experiment A: Pro, nine candidates, names only (no symptom text): does the
long symptom text pull the model away from the image?
Experiment B: Pro, nine candidates plus one reference image per candidate
(few-shot visual grounding): does a visual anchor fix the confusable family?

Usage:
    python eval/experiment.py --experiment a --subset 90
    python eval/experiment.py --experiment b --subset 90
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import json
import random
import time
from pathlib import Path

from fasalrakshak.agents import DiagnosisAgent
from fasalrakshak.kb import load_all_entries

SEED = 20261104
MODELS = {"lite": "us.amazon.nova-lite-v1:0", "pro": "us.amazon.nova-pro-v1:0"}

REFERENCED_CLASSES = {
    "tomato-bacterial-spot": "data/eval_images/Tomato___Bacterial_spot",
    "tomato-early-blight": "data/eval_images/Tomato___Early_blight",
    "tomato-late-blight": "data/eval_images/Tomato___Late_blight",
    "tomato-leaf-mold": "data/eval_images/Tomato___Leaf_Mold",
    "tomato-septoria-leaf-spot": "data/eval_images/Tomato___Septoria_leaf_spot",
    "tomato-spider-mites": "data/eval_images/Tomato___Spider_mites_Two_spotted_spider_mite",
    "tomato-target-spot": "data/eval_images/Tomato___Target_Spot",
    "tomato-mosaic-virus": "data/eval_images/Tomato___Tomato_mosaic_virus",
    "tomato-yellow-leaf-curl-virus": "data/eval_images/Tomato___Tomato_Yellow_Leaf_Curl_Virus",
}


def build_cases(subset: int) -> list[dict]:
    from fasalrakshak.manifest import PV_CLASS_TO_KB_ID

    cases: list[dict] = []
    source = Path("data/eval_images")
    for directory, kb_id in PV_CLASS_TO_KB_ID.items():
        files = sorted(p.name for p in (source / directory).iterdir() if p.suffix.lower() in {".jpg", ".jpeg"})
        rng = random.Random(f"{SEED}-exp-{kb_id}")
        rng.shuffle(files)
        per_class = max(1, subset // 10)
        for name in files[:per_class]:
            cases.append({"path": source / directory / name, "expected": kb_id})
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", choices=["a", "b", "c"], required=True)
    parser.add_argument("--subset", type=int, default=90)
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()

    entries = load_all_entries()
    candidates = [
        (entry.id, entry.disease, list(entry.symptoms))
        for entry in entries.values()
        if entry.crop == "tomato"
    ]
    cases = build_cases(args.subset)
    print(f"experiment {args.experiment}: {len(cases)} images")

    def one(case: dict) -> dict:
        image = case["path"].read_bytes()
        agent = DiagnosisAgent(model_id=MODELS["pro"])  # fresh per image: Strands agents are stateful
        try:
            if args.experiment == "c":
                # describe first, then classify
                from fasalrakshak.agents import _extract_json, _run_agent
                blocks = [
                    {"image": {"format": "jpeg", "source": {"bytes": image}}},
                    {"text": (
                        "Look at this leaf carefully. Step 1: describe in two sentences "
                        "exactly what you see: spot colors and shapes, rings, halos, fungal "
                        "growth, curling, mosaic patterns, webbing. Step 2: choose the single "
                        "best matching candidate. Answer with JSON only: "
                        '{"description": "...", "disease_id": "...", "confidence": ...}'
                    )},
                ]
                data = _extract_json(_run_agent(agent._agent, blocks))  # noqa: SLF001
            elif args.experiment == "a":
                # names only, no symptom text
                slim = [(kb_id, label) for kb_id, label, _ in candidates]
                listing = "\n".join(f"{i + 1}. {kb_id} ({label})" for i, (kb_id, label) in enumerate(slim))
                blocks = [
                    {"image": {"format": "jpeg", "source": {"bytes": image}}},
                    {"text": "Candidate diseases:\n" + listing + "\n\nDiagnose the photo. JSON only: {\"disease_id\": ..., \"confidence\": ...}"},
                ]
                from fasalrakshak.agents import _extract_json, _run_agent
                data = _extract_json(_run_agent(agent._agent, blocks))  # noqa: SLF001
            else:
                # few-shot: one reference image per candidate
                from fasalrakshak.agents import _extract_json, _run_agent
                blocks = [{"image": {"format": "jpeg", "source": {"bytes": image}}}]
                listing = []
                for i, (kb_id, label, _) in enumerate(candidates):
                    reference_dir = REFERENCED_CLASSES[kb_id]
                    reference = sorted(Path(reference_dir).glob("*.JPG"))[0]
                    blocks.append({"image": {"format": "jpeg", "source": {"bytes": reference.read_bytes()}}})
                    listing.append(f"Reference image {i + 2}: {kb_id} ({label})")
                blocks.append({
                    "text": (
                        "The FIRST image is the farmer's leaf. The following images are "
                        "labelled reference examples, one per candidate disease:\n"
                        + "\n".join(listing)
                        + "\n\nWhich candidate does the FIRST image match? JSON only: "
                        '{"disease_id": "...", "confidence": ...}'
                    )
                })
                data = _extract_json(_run_agent(agent._agent, blocks))  # noqa: SLF001
            predicted = str(data.get("disease_id", ""))
            return {"expected": case["expected"], "predicted": predicted,
                    "confidence": data.get("confidence"), "file": str(case["path"]), "error": None}
        except Exception as exc:  # noqa: BLE001
            return {"expected": case["expected"], "predicted": None, "confidence": None,
                    "file": str(case["path"]), "error": str(exc)[:150]}

    rows = []
    with futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for row in pool.map(one, cases):
            rows.append(row)

    scored = [r for r in rows if r["error"] is None]
    correct = sum(1 for r in scored if r["predicted"] == r["expected"])
    print(json.dumps({
        "experiment": args.experiment,
        "scored": len(scored),
        "errors": len(rows) - len(scored),
        "top1": correct,
        "top1_accuracy": round(correct / len(scored), 4) if scored else None,
    }, indent=2))
    out = Path(f"data/eval/experiment_{args.experiment}.json")
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
