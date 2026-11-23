#!/usr/bin/env python3
"""Sanity checks for the shared In Season rollup contract used by the UI."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def covers(date: str, start: str, end: str) -> bool:
    return start <= date <= end


def main() -> int:
    # Texas counties encode North/South deer differences.
    counties = json.loads((ROOT / "data" / "counties.json").read_text())
    kinney = counties["kinney"]
    deer = [animal for animal in kinney["animals"] if animal["species"] == "white_tailed_deer"]
    assert len(deer) >= 2, "Kinney should publish North and South deer seasons"
    ends = {
        window["end"]
        for animal in deer
        for season in animal["seasons"]
        for window in season["windows"]
        if "general" in season["title"].lower()
    }
    assert len(ends) >= 2, ends

    # Oregon hunts should have at least one open window somewhere in the season year.
    hunts = json.loads((ROOT / "data" / "oregon" / "hunts.json").read_text())
    assert any(covers("2026-10-15", hunt["start"], hunt["end"]) for hunt in hunts)

    # New states expose hunts or opportunities for In Season.
    for state, kind in (("nm", "hunts"), ("co", "hunts"), ("la", "opportunities"), ("ar", "opportunities"), ("ok", "opportunities")):
        rows = json.loads((ROOT / "data" / state / f"{kind}.json").read_text())
        assert len(rows) >= 5, (state, len(rows))
        assert all("start" in row and "end" in row and "methods" in row for row in rows)

    # Texas licenses guide exists for the Licenses pane.
    licenses = json.loads((ROOT / "data" / "texas" / "licenses.json").read_text())
    assert licenses["fees"] and licenses["whereToBuy"]
    assert any("tpwd.texas.gov" in source["url"] for source in licenses["sources"])

    print("in-season checks ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
