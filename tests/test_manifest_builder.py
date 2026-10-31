"""Tests for the frozen eval manifest builder."""

from __future__ import annotations

from pathlib import Path

from fasalrakshak.manifest import NEGATIVES_COUNT, PER_CLASS, build_manifest, pv_class_to_kb_id


def make_image_tree(base: Path) -> tuple[Path, Path]:
    source = base / "color"
    counts = {
        "Tomato___Early_blight": 60,
        "Tomato___healthy": 40,
        "Tomato___Not_in_mapping": 10,
    }
    for directory, count in counts.items():
        class_dir = source / directory
        class_dir.mkdir(parents=True)
        for i in range(count):
            (class_dir / f"img_{i:03d}.jpg").write_bytes(b"fake")
    negatives = base / "negatives"
    negatives.mkdir()
    for i in range(40):
        (negatives / f"neg_{i:03d}.jpg").write_bytes(b"fake")
    return source, negatives


def test_unknown_classes_are_skipped(tmp_path: Path) -> None:
    assert pv_class_to_kb_id("Tomato___Early_blight") == "tomato-early-blight"
    assert pv_class_to_kb_id("Tomato___Not_in_mapping") is None


def test_manifest_is_stratified_and_bounded(tmp_path: Path) -> None:
    source, negatives = make_image_tree(tmp_path)

    manifest = build_manifest(source, negatives=negatives)

    early = manifest["classes"]["tomato-early-blight"]
    healthy = manifest["classes"]["healthy"]

    assert early["available"] == 60
    assert len(early["selected"]) == PER_CLASS
    assert healthy["available"] == 40
    assert len(healthy["selected"]) == 40, "classes with fewer images select all of them"
    assert "Not_in_mapping" not in str(manifest["classes"])
    assert len(manifest["negatives"]["selected"]) == NEGATIVES_COUNT
    assert manifest["seed"] == 20261104


def test_manifest_is_deterministic(tmp_path: Path) -> None:
    source, negatives = make_image_tree(tmp_path)

    first = build_manifest(source, negatives=negatives)
    second = build_manifest(source, negatives=negatives)

    assert first == second, "same inputs and seed must give the identical manifest"
