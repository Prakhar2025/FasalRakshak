"""Consistency between the knowledge base and the banned-pesticide snapshot.

This is the data-level half of the safety story: no knowledge base entry may
recommend a banned active ingredient, ever. The Phase 2 gate enforces this at
runtime; these tests enforce it at commit time.
"""

from __future__ import annotations

from fasalrakshak.kb import load_all_entries, load_banned_list

BANNED_DIR_SNAPSHOT_MIN_ENTRIES = 15


def test_banned_snapshot_is_large_enough_to_be_real() -> None:
    banned = load_banned_list()
    assert len(banned.entries) >= BANNED_DIR_SNAPSHOT_MIN_ENTRIES
    assert banned.snapshot_date == "2026-11-01"


def test_no_banned_ingredient_appears_in_any_treatment() -> None:
    banned = load_banned_list()
    entries = load_all_entries()
    for entry in entries.values():
        for product in entry.treatment.products:
            status = banned.ingredient_status(product.active_ingredient)
            assert status != "banned", (
                f"{entry.id}: product {product.name} uses banned ingredient "
                f"{product.active_ingredient}"
            )


def test_restricted_ingredients_require_an_explicit_note() -> None:
    entries = load_all_entries()
    banned = load_banned_list()
    for entry in entries.values():
        for product in entry.treatment.products:
            status = banned.ingredient_status(product.active_ingredient)
            if status == "restricted":
                assert product.label_source, (
                    f"{entry.id}: restricted ingredient {product.active_ingredient} "
                    "without label source"
                )


def test_the_monocrotophos_nuance_is_encoded() -> None:
    """Monocrotophos is restricted (banned on vegetables), not fully banned.

    A gate that treats it as fully banned would say something false; one that
    ignores it would allow a vegetable use. The snapshot must say 'restricted'
    and the knowledge base must not use it at all.
    """
    banned = load_banned_list()
    assert banned.ingredient_status("monocrotophos") == "restricted"
    for entry in load_all_entries().values():
        for product in entry.treatment.products:
            assert "monocrotophos" not in product.active_ingredient, (
                f"{entry.id}: monocrotophos must not appear in any treatment"
            )
