#!/usr/bin/env python3
"""Sanity checks on the USACE (Army Corps of Engineers) hunting dataset."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from corps import (  # noqa: E402
    ALLOWED_LINK_SUFFIXES,
    CORPS_ACCESS,
    CORPS_DIR,
    VALID_METHODS,
    build_corps,
    load_areas,
)
from county_seasons import load_counties  # noqa: E402
from species import SPECIES  # noqa: E402

CACHE = ROOT / "cache"


def _host_allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == suf.lstrip(".") or host.endswith(suf) for suf in ALLOWED_LINK_SUFFIXES)


def main() -> int:
    areas = load_areas()
    assert len(areas) >= 18, len(areas)

    ids = [a["id"] for a in areas]
    assert len(ids) == len(set(ids)), "duplicate area ids"
    by_state: dict[str, int] = {}
    for area in areas:
        assert area["id"].startswith("usace-"), area["id"]
        assert area["name"], area["id"]
        assert area["region"], area["id"]
        assert area.get("counties"), area["id"]
        assert area.get("lon") is not None and area.get("lat") is not None, area["id"]
        assert area.get("species"), area["id"]
        state = str(area.get("state") or "tx").lower()
        assert state in {"tx", "la", "ar", "ok", "nm", "co", "or"}, (area["id"], state)
        by_state[state] = by_state.get(state, 0) + 1
        for entry in area["species"]:
            assert entry["species"] in SPECIES, (area["id"], entry["species"])
            assert entry.get("methods"), (area["id"], entry["species"])
            for method in entry["methods"]:
                assert method in VALID_METHODS, (area["id"], method)
        for link in area.get("links", []):
            assert link["url"].startswith("https://"), link
            assert _host_allowed(link["url"]), link
    assert by_state.get("tx", 0) >= 18, by_state
    assert by_state.get("la", 0) >= 2, by_state
    assert by_state.get("ar", 0) >= 2, by_state
    assert by_state.get("ok", 0) >= 2, by_state

    # Lake Whitney example from the user request: deer, archery only.
    whitney = next(a for a in areas if a["id"] == "usace-whitney")
    deer = next(e for e in whitney["species"] if e["species"] == "white_tailed_deer")
    assert deer["methods"] == ["archery"], deer

    county_index = load_counties(CACHE / "counties") if (CACHE / "counties").exists() else {}
    tx_areas = [a for a in areas if str(a.get("state") or "tx").lower() == "tx"]
    units, opps, features = build_corps(county_index)
    assert len(units) == len(tx_areas), (len(units), len(tx_areas), "build_corps should emit Texas only")
    assert len(features) == len(tx_areas), (len(features), len(tx_areas))

    by_unit = {u["id"]: u for u in units}
    opp_by_unit: dict[str, list] = {}
    for opp in opps:
        assert opp["access"] == CORPS_ACCESS, opp
        assert opp["unitId"] in by_unit, opp["unitId"]
        assert opp["species"] in SPECIES, opp["species"]
        assert opp["start"] <= opp["end"], opp
        opp_by_unit.setdefault(opp["unitId"], []).append(opp)

    for unit in units:
        assert unit["source"] == "usace", unit["id"]
        assert unit["type"] == "corps_lake", unit["id"]
        assert unit["access"] == [CORPS_ACCESS], unit["id"]
        assert unit["managingAgency"], unit["id"]
        assert unit["links"], unit["id"]
        assert opp_by_unit.get(unit["id"]), f"no opportunities for {unit['id']}"

    for feat in features:
        geom = feat["geometry"]
        assert geom["type"] in {"Point", "Polygon", "MultiPolygon"}, geom["type"]
        assert geom.get("coordinates"), feat["id"]

    # The Lake Whitney unit yields a deer + archery opportunity.
    whitney_opps = opp_by_unit["usace-whitney"]
    deer_opps = [o for o in whitney_opps if o["species"] == "white_tailed_deer"]
    assert deer_opps, "no deer opportunities for Whitney"
    assert all(o["methods"] == ["archery"] for o in deer_opps), deer_opps

    species = {o["species"] for o in opps}
    assert "dove" in species and len(species) > 1, species
    aquilla_dove = [o for o in opp_by_unit["usace-aquilla"] if o["species"] == "dove"]
    assert aquilla_dove, "Aquilla should keep a dove season"
    assert all(o["methods"] == ["shotgun"] for o in aquilla_dove), aquilla_dove

    for area in tx_areas:
        path = CORPS_DIR / f"{area['id']}.geojson"
        feat = next(f for f in features if f["id"] == area["id"])
        if path.exists():
            assert feat["geometry"]["type"] in {"Polygon", "MultiPolygon"}, area["id"]
            unit = by_unit[area["id"]]
            assert "PAD-US" in unit.get("boundaryNote", ""), area["id"]

    print(
        f"ok: {len(areas)} Corps areas ({len(tx_areas)} tx), "
        f"{len(opps)} opportunities, {len(features)} features"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
