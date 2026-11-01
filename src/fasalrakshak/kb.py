"""Knowledge base loading.

The knowledge base is versioned JSON under ``kb/`` in the repository root.
Loading validates every file against the schemas in ``schemas.py``; an
invalid file is a hard error, never a warning.
"""

from __future__ import annotations

import json
from pathlib import Path

from .schemas import BannedList, KBEntry

def _find_kb_dir() -> Path:
    """Locate the kb/ directory by walking upward for its marker file.

    The repository (src/fasalrakshak/) and the Lambda package
    (fasalrakshak/ under the handler root) have different depths; a marker
    search works in both.
    """
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        candidate = parent / "kb"
        if (candidate / "banned_pesticides.json").is_file():
            return candidate
    raise RuntimeError("kb/ not found: run from the repository or the deploy package")


DEFAULT_KB_DIR = _find_kb_dir()


def load_entry(disease_id: str, kb_dir: Path | None = None) -> KBEntry:
    """Load and validate one knowledge base entry by id, e.g. tomato-early-blight."""
    directory = kb_dir or DEFAULT_KB_DIR
    matches = list(directory.glob(f"*/{disease_id}.json"))
    if not matches:
        raise KeyError(f"unknown knowledge base id: {disease_id}")
    if len(matches) > 1:
        raise ValueError(f"duplicate knowledge base id: {disease_id}")
    data = json.loads(matches[0].read_text(encoding="utf-8"))
    return KBEntry.model_validate(data)


def load_all_entries(kb_dir: Path | None = None) -> dict[str, KBEntry]:
    """Load and validate every entry, keyed by id. Duplicates are fatal."""
    directory = kb_dir or DEFAULT_KB_DIR
    entries: dict[str, KBEntry] = {}
    for path in sorted(directory.glob("*/*.json")):
        entry = KBEntry.model_validate(json.loads(path.read_text(encoding="utf-8")))
        if entry.id in entries:
            raise ValueError(f"duplicate knowledge base id: {entry.id}")
        entries[entry.id] = entry
    return entries


def load_entries_for_crop(crop: str, kb_dir: Path | None = None) -> dict[str, KBEntry]:
    """Load and validate every entry for one crop, keyed by id."""
    return {
        entry_id: entry
        for entry_id, entry in load_all_entries(kb_dir).items()
        if entry.crop == crop
    }


def load_banned_list(kb_dir: Path | None = None) -> BannedList:
    """Load and validate the CIB&RC banned and restricted snapshot."""
    directory = kb_dir or DEFAULT_KB_DIR
    path = directory / "banned_pesticides.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return BannedList.model_validate(data)
