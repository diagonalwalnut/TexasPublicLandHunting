#!/usr/bin/env python3
"""Contract checks mirroring web/src/shared/residency.ts helper semantics."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RESIDENT_ONLY_RE = re.compile(r"residents?\s+only", re.I)
NONRESIDENT_ONLY_RE = re.compile(r"non[-\s]?residents?\s+only", re.I)


def _blob(row: dict) -> str:
    parts: list[str] = []
    notes = row.get("notes")
    if isinstance(notes, str):
        parts.append(notes)
    restrictions = row.get("restrictions")
    if isinstance(restrictions, list):
        parts.extend(str(r) for r in restrictions)
    elif isinstance(restrictions, str):
        parts.append(restrictions)
    return " ".join(parts)


def row_eligibility(row: dict) -> str:
    raw = str(row.get("eligibility") or "").strip().lower()
    if raw in {"any", "resident_only", "nonresident_only"}:
        return raw
    blob = _blob(row)
    if NONRESIDENT_ONLY_RE.search(blob):
        return "nonresident_only"
    if RESIDENT_ONLY_RE.search(blob):
        return "resident_only"
    return "any"


def row_allowed(row: dict, hunter_residency: str) -> bool:
    if not hunter_residency:
        return True
    eligibility = row_eligibility(row)
    if eligibility == "any":
        return True
    if hunter_residency == "resident":
        return eligibility != "nonresident_only"
    if hunter_residency == "nonresident":
        return eligibility != "resident_only"
    return True


def test_helper_semantics() -> None:
    open_row = {"notes": "General season"}
    structured = {"eligibility": "resident_only"}
    text_only = {"restrictions": ["Residents only — public-land elk draw"]}
    nr_only = {"restrictions": ["Nonresidents only special hunt"]}
    override = {
        "eligibility": "any",
        "restrictions": ["Residents only — ignored when structured any"],
    }

    assert row_eligibility(open_row) == "any"
    assert row_eligibility(structured) == "resident_only"
    assert row_eligibility(text_only) == "resident_only"
    assert row_eligibility(nr_only) == "nonresident_only"
    assert row_eligibility(override) == "any"

    assert row_allowed(structured, "") is True
    assert row_allowed(structured, "resident") is True
    assert row_allowed(structured, "nonresident") is False
    assert row_allowed(text_only, "nonresident") is False
    assert row_allowed(nr_only, "resident") is False
    assert row_allowed(nr_only, "nonresident") is True
    assert row_allowed(override, "nonresident") is True


def test_ar_elk_data() -> None:
    for rel in ("data/ar/opportunities.json", "web/public/data/ar/opportunities.json"):
        opps = json.loads((ROOT / rel).read_text())
        elk = [o for o in opps if o.get("species") == "elk"]
        assert elk, rel
        assert all(o.get("eligibility") == "resident_only" for o in elk), rel
        assert all(not row_allowed(o, "nonresident") for o in elk), rel
        assert all(row_allowed(o, "resident") for o in elk), rel


def main() -> int:
    test_helper_semantics()
    print("residency helper ok")
    test_ar_elk_data()
    print("AR elk eligibility ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
