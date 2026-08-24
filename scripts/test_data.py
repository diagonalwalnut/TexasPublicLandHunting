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
    print(
        f"ok: {len(units)} units, {len(opps)} opportunities, "
        f"{with_county} with county calendars, {with_booklet} with booklet pages"
    )
    drawn_path = DATA / "drawn_hunts.json"
    if drawn_path.exists():
        drawn = json.loads(drawn_path.read_text())
        assert len(drawn) >= 300, len(drawn)
        assert len({h["id"] for h in drawn}) == len(drawn)
        assert all(h.get("lon") is not None for h in drawn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
