"""Fetch the frozen benchmark image pool from the public PlantVillage dataset.

Downloads a deterministic, seeded subset of the ten tomato classes (60 per
class, the manifest later freezes 50 of them) directly from the dataset
repository, so nobody has to pull the full 2 GB archive. Our three demo
sample files are excluded from the pool: they were shown to the model during
live smoke tests and must never sit inside the held-out set.

Class directories are discovered by listing the dataset root and matching
normalized names, so spelling variants in the upstream repository (spaces,
hyphens) cannot break the fetch. Already-downloaded files are skipped, so
the script is safely re-runnable.

Usage:
    python scripts/fetch_eval_images.py --out data/eval_images
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import random
from pathlib import Path

import httpx

ROOT_API = "https://api.github.com/repos/spMohanty/PlantVillage-Dataset/contents/raw/color"
SEED = 20261104
PER_CLASS = 60

CLASSES = [
    "Tomato___Bacterial_spot",
    "Tomato___Early_blight",
    "Tomato___Late_blight",
    "Tomato___Leaf_Mold",
    "Tomato___Septoria_leaf_spot",
    "Tomato___Spider_mites_Two_spotted_spider_mite",
    "Tomato___Target_Spot",
    "Tomato___Tomato_mosaic_virus",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato___healthy",
]

# Demo sample files live in app/web/assets/samples/ and were used in live
# smoke tests; they are excluded from the held-out pool by filename.
EXCLUDE_TOKENS = ("8389.JPG", "4946.JPG", "259.1.JPG")


def normalize(name: str) -> str:
    return name.lower().replace(" ", "_").replace("-", "_")


def discover_classes(client: httpx.Client) -> dict[str, str]:
    """Map each of our class names to the actual upstream directory name."""
    listing = client.get(ROOT_API)
    listing.raise_for_status()
    upstream = {item["name"]: item for item in listing.json() if item["type"] == "dir"}
    by_normalized = {normalize(name): name for name in upstream}
    resolved: dict[str, str] = {}
    for wanted in CLASSES:
        actual = by_normalized.get(normalize(wanted))
        if actual is None:
            raise RuntimeError(f"could not resolve upstream directory for {wanted}")
        resolved[wanted] = actual
    return resolved


def list_class(client: httpx.Client, actual_dir: str, wanted: str) -> list[dict]:
    response = client.get(f"{ROOT_API}/{actual_dir}")
    response.raise_for_status()
    return [
        item
        for item in response.json()
        if item["name"].lower().endswith((".jpg", ".jpeg"))
        and not any(token in item["name"] for token in EXCLUDE_TOKENS)
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data/eval_images")
    parser.add_argument("--per-class", type=int, default=PER_CLASS)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        resolved = discover_classes(client)
        jobs: list[tuple[str, str]] = []
        for wanted in CLASSES:
            items = list_class(client, resolved[wanted], wanted)
            rng = random.Random(f"{SEED}-{wanted}")
            rng.shuffle(items)
            target = out / wanted
            target.mkdir(parents=True, exist_ok=True)
            picked = 0
            for item in items:
                if picked >= args.per_class:
                    break
                destination = target / item["name"]
                if destination.exists() and destination.stat().st_size > 1000:
                    picked += 1
                    continue
                jobs.append((item["download_url"], str(destination)))
                picked += 1
            print(f"{wanted}: pool {len(items)}, need {args.per_class}, new {len([j for j in jobs if j[1].startswith(str(target))])}")

        done = 0

        def fetch(job: tuple[str, str]) -> None:
            url, path = job
            data = client.get(url).content
            Path(path).write_bytes(data)

        with futures.ThreadPoolExecutor(max_workers=12) as pool:
            for _ in pool.map(fetch, jobs):
                done += 1
                if done % 50 == 0:
                    print(f"downloaded {done}/{len(jobs)}")

    print(f"done: {done} new images under {out}")


if __name__ == "__main__":
    main()
