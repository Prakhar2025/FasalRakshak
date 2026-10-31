"""Tests for knowledge base loading and validation, using isolated fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fasalrakshak.kb import load_all_entries, load_banned_list, load_entry
from fasalrakshak.schemas import BannedList, KBEntry

VALID_ENTRY = {
    "id": "test-early-blight",
    "crop": "testcrop",
    "disease": "Early blight",
    "pathogen": "Alternaria solani",
    "symptoms": ["Brown spots", "Yellow halo"],
    "treatment": {
        "summary": "Remove leaves and spray",
        "steps": ["Remove leaves", "Spray fungicide"],
        "products": [
            {
                "name": "Mancozeb 75 WG",
                "active_ingredient": "Mancozeb",
                "dose": "2.0",
                "dose_max": "2.5",
                "unit": "g per litre",
                "phi_days": 7,
                "label_source": "CIB&RC registered label",
            }
        ],
        "organic": ["Neem oil"],
    },
    "source": {
        "org": "Test Institute",
        "title": "Test advisory",
        "url": "",
        "accessed": "2026-11-01",
    },
    "safety_notes": ["Wear gloves"],
}


def write_entry(base: Path, crop: str, entry: dict) -> Path:
    crop_dir = base / crop
    crop_dir.mkdir(parents=True, exist_ok=True)
    path = crop_dir / f"{entry['id']}.json"
    path.write_text(json.dumps(entry), encoding="utf-8")
    return path


def test_load_entry_validates_a_well_formed_file(tmp_path: Path) -> None:
    write_entry(tmp_path, "testcrop", VALID_ENTRY)

    entry = load_entry("test-early-blight", kb_dir=tmp_path)

    assert isinstance(entry, KBEntry)
    assert entry.treatment.products[0].active_ingredient == "mancozeb"


def test_load_entry_rejects_dose_above_zero_rules(tmp_path: Path) -> None:
    bad = json.loads(json.dumps(VALID_ENTRY))
    bad["treatment"]["products"][0]["dose"] = "-1"
    write_entry(tmp_path, "testcrop", bad)

    with pytest.raises(Exception):
        load_entry("test-early-blight", kb_dir=tmp_path)


def test_load_entry_missing_id_raises(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        load_entry("does-not-exist", kb_dir=tmp_path)


def test_duplicate_ids_are_fatal(tmp_path: Path) -> None:
    first = json.loads(json.dumps(VALID_ENTRY))
    second = json.loads(json.dumps(VALID_ENTRY))
    second["disease"] = "Another blight variant"
    write_entry(tmp_path, "cropa", first)
    write_entry(tmp_path, "cropb", second)

    with pytest.raises(ValueError, match="duplicate"):
        load_all_entries(kb_dir=tmp_path)


def test_source_date_must_be_iso(tmp_path: Path) -> None:
    bad = json.loads(json.dumps(VALID_ENTRY))
    bad["source"]["accessed"] = "last month"
    write_entry(tmp_path, "testcrop", bad)

    with pytest.raises(Exception):
        load_all_entries(kb_dir=tmp_path)


def write_banned_list(base: Path) -> None:
    payload = {
        "snapshot_date": "2026-11-01",
        "source": "CIB&RC lists",
        "entries": [
            {"active_ingredient": "ENDOSULFAN", "status": "banned", "citation": "SC order 2011"},
            {"active_ingredient": "chlordane", "status": "banned", "citation": "original banned list"},
            {"active_ingredient": "Monocrotophos", "status": "restricted", "citation": "banned for vegetables"},
        ]
        + [
            {"active_ingredient": f"filler{i}", "status": "banned", "citation": "filler"}
            for i in range(8)
        ],
    }
    (base / "banned_pesticides.json").write_text(json.dumps(payload), encoding="utf-8")


def test_banned_list_normalizes_case(tmp_path: Path) -> None:
    write_banned_list(tmp_path)

    banned = load_banned_list(kb_dir=tmp_path)

    assert isinstance(banned, BannedList)
    assert banned.ingredient_status("endosulfan") == "banned"
    assert banned.ingredient_status("MONOCROTOPHOS") == "restricted"
    assert banned.ingredient_status("mancozeb") is None
