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

    # USACE (Army Corps of Engineers) areas are merged into the same dataset.
    corps_units = [u for u in units if u.get("source") == "usace"]
    assert len(corps_units) >= 18, len(corps_units)
    assert {a["id"] for a in meta["access"]} >= {"corps_permit"}, meta["access"]
    corps_opps = [o for o in opps if o["access"] == "corps_permit"]
    assert corps_opps, "no corps opportunities"
    by_id_all = {u["id"]: u for u in units}
    whitney = by_id_all["usace-whitney"]
    assert whitney["type"] == "corps_lake", whitney["type"]
    assert "white_tailed_deer" in whitney["species"], whitney["species"]
    whitney_deer = [
        o for o in corps_opps if o["unitId"] == "usace-whitney" and o["species"] == "white_tailed_deer"
    ]
    assert whitney_deer and all(o["methods"] == ["archery"] for o in whitney_deer), whitney_deer
    # GIS gap-fill raised the TPWD polygon count above the prior 154 baseline.
    tpwd_polys = sum(
        1
        for f in geo["features"]
        if f["geometry"]["type"] != "Point" and f["properties"].get("source") != "usace"
    )
    assert tpwd_polys >= 154, tpwd_polys
    with_county = sum(1 for u in units if u.get("countySlugs"))
    assert with_county >= 100, with_county
    counties = json.loads((DATA / "counties.json").read_text())
    assert len(counties) >= 80, len(counties)
    assert any(o.get("dateSource") == "county" for o in opps)
    with_booklet = sum(1 for u in units if u.get("bookletPage"))
    assert with_booklet >= 150, with_booklet
    by_id = {u["id"]: u for u in units}
    assert by_id["702"]["bookletPage"] == "5", by_id["702"].get("bookletPage")
    assert by_id["904"]["bookletPage"] == "85", by_id["904"].get("bookletPage")
    assert by_id["736"]["bookletPage"] in {"xxiv", "xxv"}, by_id["736"].get("bookletPage")
    url_fields = ("pdfUrl", "aerialPdfUrl", "bookletUrl", "epostcardUrl")
    for unit in units:
        for field in url_fields:
            val = unit.get(field) or ""
            if val:
                assert val.startswith("https://tpwd.texas.gov/"), (unit["id"], field, val)
    for page in counties.values():
        url = page.get("url") or ""
        if url:
            assert url.startswith("https://tpwd.texas.gov/"), url

    from safe import is_tpwd_url, resource_stem, safe_extract

    assert not is_tpwd_url("javascript:alert(1)")
    assert not is_tpwd_url("https://evil.example/https://tpwd.texas.gov/")
    assert not resource_stem("../secret")
    import tempfile
    import zipfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        zpath = root / "t.zip"
        dest = root / "out"
        dest.mkdir()
        with zipfile.ZipFile(zpath, "w") as zf:
            zf.writestr("../evil.txt", "nope")
            zf.writestr("ok.txt", "yes")
        safe_extract(zpath, dest)
        assert (dest / "ok.txt").read_text() == "yes"
        assert not (root / "evil.txt").exists()
    # Marlin Lake Park is deer archery only. Twin Buttes allows archery,
    # shotgun slugs, and muzzleloaders — never centerfire rifle.
    for uid, allowed in (
        ("2547", {"archery"}),
        ("502", {"archery", "shotgun", "muzzleloader"}),
    ):
        deer = [o for o in opps if o["unitId"] == uid and o["species"] == "white_tailed_deer"]
        assert deer, uid
        methods = {m for o in deer for m in o["methods"]}
        assert methods <= allowed, (uid, methods)
        assert "firearm" not in methods and "any_legal" not in methods, (uid, methods)

    def matches_whitetail_rifle(opp: dict) -> bool:
        if opp["species"] != "white_tailed_deer":
            return False
        return "firearm" in opp["methods"] or "any_legal" in opp["methods"]

    assert not any(matches_whitetail_rifle(o) and o["unitId"] == "2547" for o in opps)
    assert not any(matches_whitetail_rifle(o) and o["unitId"] == "733" for o in opps)
    for species in ("white_tailed_deer", "feral_hog", "coyote", "furbearers"):
        rows = [o for o in opps if o["unitId"] == "2547" and o["species"] == species]
        assert rows, species
        assert all("firearm" not in o["methods"] and "any_legal" not in o["methods"] for o in rows), rows
    bottom_deer = [o for o in opps if o["unitId"] == "733" and o["species"] == "white_tailed_deer"]
    assert bottom_deer and all(o["methods"] == ["archery"] for o in bottom_deer), bottom_deer
    assert "rifle" in by_id["2547"].get("correctionNote", "").lower()
    assert by_id["733"].get("methodCorrection", {}).get("speciesMethods", {}).get("white_tailed_deer") == ["archery"]

    print(
        f"ok: {len(units)} units, {len(opps)} opportunities, "
        f"{with_county} with county calendars, {with_booklet} with booklet pages"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
