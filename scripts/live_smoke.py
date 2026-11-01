"""Live smoke test: real photo, real Bedrock, no mocks.

Runs triage and diagnosis through the actual Strands agents on one image.
Requires AWS credentials with Bedrock access to Nova Lite. Exits 0 and
prints a JSON summary on success; exits 1 when any stage fails.

Usage:
    python scripts/live_smoke.py --image data/samples/Tomato___Early_blight__xxx.JPG
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fasalrakshak.agents import DiagnosisAgent, TriageAgent  # noqa: E402
from fasalrakshak.pipeline import search_kb_candidates  # noqa: E402
from fasalrakshak.kb import load_all_entries  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()

    image = Path(args.image).read_bytes()
    entries = load_all_entries()

    print(f"image: {args.image} ({len(image)} bytes)")
    print("running live triage on Bedrock Nova Lite ...")
    triage = TriageAgent().run(image)
    print(f"triage: usable={triage.usable} crop={triage.crop_hint} reason={triage.reason!r}")
    if not triage.usable:
        print("SMOKE RESULT: triage rejected the photo (this is a valid outcome for non-leaf images)")
        return 0

    candidates = search_kb_candidates(triage.crop_hint, "", entries=entries)
    print(f"candidates: {[c[0] for c in candidates]}")

    print("running live diagnosis on Bedrock Nova Lite ...")
    diagnosis = DiagnosisAgent().run(image, candidates)
    summary = {
        "disease_id": diagnosis.disease_id,
        "label": diagnosis.label,
        "confidence": diagnosis.confidence,
        "runner_up_id": diagnosis.runner_up_id,
        "runner_up_confidence": diagnosis.runner_up_confidence,
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
