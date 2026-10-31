"""Validation across the real knowledge base files committed in the repo."""

from __future__ import annotations

from pathlib import Path

import pytest

from fasalrakshak.kb import DEFAULT_KB_DIR, load_all_entries, load_entry
from fasalrakshak.schemas import KBEntry

KB_DIR = DEFAULT_KB_DIR


def discover(crop: str) -> list[Path]:
    return sorted((KB_DIR / crop).glob("*.json"))


@pytest.mark.parametrize("path", discover("tomato"), ids=lambda p: p.stem)
def test_every_tomato_entry_validates(path: Path) -> None:
    import json

    entry = KBEntry.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert entry.crop == "tomato"
    assert entry.id == path.stem


@pytest.mark.parametrize("path", discover("cotton"), ids=lambda p: p.stem)
def test_every_cotton_entry_validates(path: Path) -> None:
    import json

    entry = KBEntry.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert entry.crop == "cotton"
    assert entry.id == path.stem


def test_knowledge_base_scope_is_complete() -> None:
    entries = load_all_entries(kb_dir=KB_DIR)
    tomato = [e for e in entries.values() if e.crop == "tomato"]
    assert len(tomato) >= 9, "tomato KB must cover the 8 hackathon diseases plus mites"


def test_every_entry_has_a_source_with_org_and_title() -> None:
    for entry in load_all_entries(kb_dir=KB_DIR).values():
        assert entry.source.org, f"{entry.id}: missing source org"
        assert entry.source.title, f"{entry.id}: missing source title"


def test_chemical_products_carry_ppe_and_phi_guidance() -> None:
    for entry in load_all_entries(kb_dir=KB_DIR).values():
        has_chemicals = bool(entry.treatment.products)
        if has_chemicals:
            notes = " ".join(entry.safety_notes).lower()
            assert "wear" in notes or "ppe" in notes, f"{entry.id}: chemical entry without PPE note"
            for product in entry.treatment.products:
                assert product.phi_days >= 0
                assert product.dose_value <= product.dose_max_value, (
                    f"{entry.id}: recommended dose exceeds label maximum for {product.name}"
                )


def test_dose_max_is_the_ceiling_not_the_floor() -> None:
    for entry in load_all_entries(kb_dir=KB_DIR).values():
        for product in entry.treatment.products:
            assert product.dose_max_value >= product.dose_value


def test_spot_check_early_blight_loads_directly() -> None:
    entry = load_entry("tomato-early-blight", kb_dir=KB_DIR)
    assert entry.pathogen == "Alternaria solani"
    assert entry.treatment.products[0].active_ingredient == "mancozeb"
