#!/usr/bin/env python3
"""Sanity checks for the Oregon admin beta dataset."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "oregon"


def main() -> int:
    units = json.loads((DATA / "units.json").read_text())
    hunts = json.loads((DATA / "hunts.json").read_text())
    meta = json.loads((DATA / "meta.json").read_text())
    licenses = json.loads((DATA / "licenses.json").read_text())
    wmu = json.loads((DATA / "wmu.geojson").read_text())
    deer = json.loads((DATA / "deer-areas.geojson").read_text())
    ids = {unit["id"] for unit in units}
    assert len(units) >= 100, len(units)
    assert len(wmu["features"]) == sum(1 for unit in units if unit["kind"] == "wmu")
    assert len(deer["features"]) == sum(1 for unit in units if unit["kind"] == "deer_hunt_area")
    assert meta["seasonYear"] == "2026"
    wilson = next(hunt for hunt in hunts if hunt["huntNumber"] == "112")
    assert wilson["name"] == "Wilson Unit"
    assert wilson["start"] == "2026-11-01" and wilson["end"] == "2026-11-30"
    assert wilson["unitIds"] == ["wmu:12"]
    assert wilson["methods"] == ["any_legal"]
    aldrich = next(hunt for hunt in hunts if hunt["huntNumber"] == "AD101")
    assert aldrich["unitIds"] == ["dha:AD-01"]
    assert aldrich["start"] == "2026-10-03"
    west = next(hunt for hunt in hunts if hunt["id"] == "gen-deer-alw-west")
    assert west["tagSaleDeadline"] == "2026-10-02"
    assert "wmu:10" in west["unitIds"] and "wmu:30" in west["unitIds"]
    bow = next(hunt for hunt in hunts if hunt["huntNumber"] == "DE101R")
    assert bow["methods"] == ["archery"]
    for hunt in hunts:
        assert hunt["start"] <= hunt["end"], hunt["id"]
        for unit_id in hunt["unitIds"]:
            assert unit_id in ids, (hunt["id"], unit_id)
    channels = {item["id"] for item in licenses["whereToBuy"]}
    assert {"internet", "agent", "mail", "otc", "draw"} <= channels
    assert any("preference" in line.lower() for line in licenses["preferencePoints"])
    assert any(series["id"] == "100" and series["points"] for series in licenses["huntSeries"])
    assert any(series["id"] == "500" and not series["points"] for series in licenses["huntSeries"])
    print(f"oregon ok: {len(units)} areas, {len(hunts)} hunts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
