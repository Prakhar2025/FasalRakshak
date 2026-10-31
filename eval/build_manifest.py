"""CLI: build the frozen eval manifest from a local PlantVillage download.

Usage:
    python eval/build_manifest.py --source path/to/PlantVillage/color \
        --negatives path/to/negatives --out data/eval/manifest.json

The PlantVillage dataset is a public research dataset; download it once
(github.com/spMohanty/PlantVillage-Dataset, color images) and keep it under
data/, which is gitignored. The manifest records file names and counts; the
images themselves never enter the repository.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fasalrakshak.manifest import NEGATIVES_COUNT, PER_CLASS, SEED, build_manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="PlantVillage color image root")
    parser.add_argument("--negatives", default=None, help="directory of non-leaf images")
    parser.add_argument("--out", default="data/eval/manifest.json")
    parser.add_argument("--per-class", type=int, default=PER_CLASS)
    parser.add_argument("--negatives-count", type=int, default=NEGATIVES_COUNT)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    manifest = build_manifest(
        source=Path(args.source),
        negatives=Path(args.negatives) if args.negatives else None,
        per_class=args.per_class,
        seed=args.seed,
        negatives_count=args.negatives_count,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    total_selected = sum(len(c["selected"]) for c in manifest["classes"].values())
    print(f"manifest written to {out_path}")
    print(f"classes: {len(manifest['classes'])}, selected images: {total_selected}")
    print(f"negatives: {len(manifest['negatives']['selected'])}")


if __name__ == "__main__":
    main()
