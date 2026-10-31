"""Stratified eval manifest builder for the PlantVillage tomato benchmark.

The manifest is built once, frozen, and then never edited. It selects a fixed
seeded sample per class so every published number is reproducible. See
docs/EVAL_PLAN.md for the methodology contract.
"""

from __future__ import annotations

import random
from datetime import date
from pathlib import Path

SEED = 20261104
PER_CLASS = 50
NEGATIVES_COUNT = 30

# PlantVillage directory name -> knowledge base id (or "healthy").
PV_CLASS_TO_KB_ID = {
    "Tomato___Bacterial_spot": "tomato-bacterial-spot",
    "Tomato___Early_blight": "tomato-early-blight",
    "Tomato___Late_blight": "tomato-late-blight",
    "Tomato___Leaf_Mold": "tomato-leaf-mold",
    "Tomato___Septoria_leaf_spot": "tomato-septoria-leaf-spot",
    "Tomato___Spider_mites_Two_spotted_spider_mite": "tomato-spider-mites",
    "Tomato___Target_Spot": "tomato-target-spot",
    "Tomato___Tomato_mosaic_virus": "tomato-mosaic-virus",
    "Tomato___Tomato_Yellow_Leaf_Curl_Virus": "tomato-yellow-leaf-curl-virus",
    "Tomato___healthy": "healthy",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def pv_class_to_kb_id(directory_name: str) -> str | None:
    """Map a PlantVillage class directory to a KB id, None if unknown."""
    return PV_CLASS_TO_KB_ID.get(directory_name)


def _image_files(directory: Path) -> list[str]:
    if not directory.is_dir():
        return []
    return sorted(
        p.name for p in directory.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
    )


def build_manifest(
    source: Path,
    negatives: Path | None = None,
    per_class: int = PER_CLASS,
    seed: int = SEED,
    negatives_count: int = NEGATIVES_COUNT,
) -> dict:
    """Build the frozen benchmark manifest from a PlantVillage image tree.

    ``source`` is the directory that contains PlantVillage class folders
    (for example ``PlantVillage/color/``). Unknown class folders are skipped
    so the script can run over the full dataset without failing.
    """
    rng = random.Random(seed)
    classes: dict[str, dict] = {}

    for directory_name in sorted(PV_CLASS_TO_KB_ID):
        kb_id = PV_CLASS_TO_KB_ID[directory_name]
        files = _image_files(source / directory_name)
        rng.shuffle(files)
        classes[kb_id] = {
            "dir": directory_name,
            "available": len(files),
            "selected": files[:per_class],
        }

    negative_payload = {"dir": "", "available": 0, "selected": []}
    if negatives is not None:
        negative_files = _image_files(negatives)
        rng.shuffle(negative_files)
        negative_payload = {
            "dir": str(negatives),
            "available": len(negative_files),
            "selected": negative_files[:negatives_count],
        }

    return {
        "seed": seed,
        "per_class": per_class,
        "built_at": date.today().isoformat(),
        "source_root": str(source),
        "classes": classes,
        "negatives": negative_payload,
    }
