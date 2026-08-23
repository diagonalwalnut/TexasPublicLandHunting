#!/usr/bin/env python3
"""Sanity checks on compiled hunt data."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def main() -> int:
    units = json.loads((DATA / "units.json").read_text())
    opps = json.loads((DATA / "opportunities.json").read_text())
    geo = json.loads((DATA / "units.geojson").read_text())
    meta = json.loads((DATA / "meta.json").read_text())
    regions = json.loads((DATA / "regions.geojson").read_text())

    assert len(units) >= 150, len(units)
    assert len(opps) >= 500, len(opps)
    assert len(geo["features"]) == len(units)
    assert all(u.get("lon") is not None for u in units)
    assert {o["unitId"] for o in opps} <= {u["id"] for u in units}
    species = {o["species"] for o in opps}
    assert "dove" in species and "white_tailed_deer" in species
    assert meta["seasonYear"] == "2026-27"
    assert len(regions["features"]) == 8
    with_county = sum(1 for u in units if u.get("countySlugs"))
    assert with_county >= 100, with_county
    counties = json.loads((DATA / "counties.json").read_text())
    assert len(counties) >= 80, len(counties)
    assert any(o.get("dateSource") == "county" for o in opps)
    print(f"ok: {len(units)} units, {len(opps)} opportunities, {with_county} with county calendars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
