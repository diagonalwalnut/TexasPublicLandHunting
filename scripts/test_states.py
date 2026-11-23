#!/usr/bin/env python3
"""Sanity checks for NM/CO/LA/AR/OK state data packages and multi-state Corps."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WEB = ROOT / "web" / "public" / "data"

BUY_CHANNEL_MIN = {"internet", "agent"}


def _load(state: str, name: str):
    path = DATA / state / name
    assert path.exists(), f"missing {path}"
    web_path = WEB / state / name
    assert web_path.exists(), f"missing mirror {web_path}"
    return json.loads(path.read_text())


def _assert_licenses(state: str, licenses: dict) -> None:
    assert licenses.get("title"), state
    assert licenses.get("seasonYear"), state
    assert licenses.get("intro"), state
    channels = {item["id"] for item in licenses.get("whereToBuy", [])}
    assert BUY_CHANNEL_MIN <= channels, (state, channels)
    assert any(
        (s.get("url") or "").startswith("https://") for s in licenses.get("sources", [])
    ), state
    fees = licenses.get("fees") or []
    assert fees, state
    assert any(f.get("resident") and f.get("nonresident") for f in fees), state


def _assert_dates(rows: list[dict], *, start_key="start", end_key="end") -> None:
    assert rows, "no dated rows"
    for row in rows:
        assert row[start_key] <= row[end_key], row.get("id")


def test_unit_grid(state: str) -> None:
    meta = _load(state, "meta.json")
    licenses = _load(state, "licenses.json")
    regs = _load(state, "regulations.json")
    units = _load(state, "units.json")
    hunts = _load(state, "hunts.json")
    primary = _load(state, "primary.geojson")
    assert meta.get("profile") == "unitGrid", state
    assert meta.get("seasonYear"), state
    assert meta.get("disclaimer"), state
    assert meta.get("sources"), state
    assert meta.get("species") and meta.get("methods") and meta.get("access"), state
    _assert_licenses(state, licenses)
    assert regs.get("methods") and regs.get("prohibited") and regs.get("unitRules"), state
    assert len(units) >= 1, state
    assert len(primary.get("features") or []) >= 1, state
    assert len(hunts) >= 1, state
    _assert_dates(hunts)
    ids = {u["id"] for u in units}
    for hunt in hunts:
        assert hunt.get("species") and hunt.get("speciesLabel"), hunt.get("id")
        assert hunt.get("methods") and hunt.get("access"), hunt.get("id")
        for uid in hunt.get("unitIds") or []:
            assert uid in ids, (state, hunt.get("id"), uid)
    # Optional counties / public-land
    counties = DATA / state / "counties.geojson"
    if counties.exists():
        fc = json.loads(counties.read_text())
        assert len(fc.get("features") or []) >= 1, state


def test_public_land(state: str) -> None:
    meta = _load(state, "meta.json")
    licenses = _load(state, "licenses.json")
    regs = _load(state, "regulations.json")
    units = _load(state, "units.json")
    opps = _load(state, "opportunities.json")
    geo = _load(state, "units.geojson")
    assert meta.get("profile") == "publicLand", state
    assert meta.get("seasonYear") and meta.get("disclaimer") and meta.get("sources"), state
    _assert_licenses(state, licenses)
    assert regs.get("methods") and regs.get("prohibited") and regs.get("unitRules"), state
    assert len(units) >= 1, state
    assert len(geo.get("features") or []) >= 1, state
    assert len(opps) >= 1, state
    _assert_dates(opps)
    ids = {u["id"] for u in units}
    zone_ids: set[str] = set()
    if state == "ar":
        zones = _load(state, "zones.json")
        assert len(zones) >= 1, state
        zone_ids = {z["id"] for z in zones}
    for opp in opps:
        assert opp["unitId"] in ids or opp["unitId"] in zone_ids, (
            state,
            opp.get("id"),
            opp.get("unitId"),
        )
        assert opp.get("species") and opp.get("methods") and opp.get("access"), opp.get("id")
    corps = [u for u in units if u.get("source") == "usace" or u.get("type") == "corps_lake"]
    assert len(corps) >= 1, f"{state} expected Corps rows"


def test_corps_multi() -> None:
    sys.path.insert(0, str(ROOT / "scripts"))
    from corps_multi import areas_for_state, build_corps_for_state

    for code, minimum in [("la", 2), ("ar", 2), ("ok", 2), ("nm", 1), ("co", 1)]:
        areas = areas_for_state(code)
        assert len(areas) >= minimum, (code, len(areas))
        units, opps, feats = build_corps_for_state(code)
        assert len(units) >= minimum, (code, len(units))
        assert len(opps) >= 1, code
        assert len(feats) == len(units), code
        for area in areas:
            assert area.get("permitInfo"), area["id"]
            assert area.get("means"), area["id"]
            assert area.get("links"), area["id"]
            assert area.get("lon") is not None and area.get("lat") is not None, area["id"]


def main() -> int:
    for state in ("nm", "co"):
        test_unit_grid(state)
        print(f"{state} unitGrid ok")
    for state in ("la", "ar", "ok"):
        test_public_land(state)
        print(f"{state} publicLand ok")
    test_corps_multi()
    print("corps multi ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
