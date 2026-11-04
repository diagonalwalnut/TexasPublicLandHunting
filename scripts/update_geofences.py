#!/usr/bin/env python3
"""Replace APH hunt geofences with the live TPWD Public Hunt Locator polygons.

The locator is the map drawn by the public-hunting Experience and web viewer.
KMZ polygons stay in place only when that map has no boundary for the unit.
Opportunities, dates, and Corps lake units are left unchanged.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from shapely.geometry import shape

from geometry import centroid_point, clean_polygonal, dissolve, geojson_polygon, parse_arcgis_polygons

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PUBLIC = ROOT / "web" / "public" / "data"
CACHE = ROOT / "cache"


def locator_polygons() -> dict[str, dict]:
    hunt_path = CACHE / "hunt_polys_arcgis.geojson"
    dove_path = CACHE / "dove_polys_arcgis.geojson"
    if not hunt_path.exists() or not dove_path.exists():
        raise SystemExit("missing locator cache; run scripts/fetch.py --gis first")
    polygons = parse_arcgis_polygons(
        json.loads(hunt_path.read_text()),
        ("Unit_Num", "PH_UnitNum"),
    )
    dove = parse_arcgis_polygons(
        json.loads(dove_path.read_text()),
        ("Unit_Num", "LEASE_NUM", "PH_UnitNum"),
    )
    for unit_id, record in dove.items():
        polygons.setdefault(unit_id, record)
    return polygons


def whole_acres(value: float | None) -> int | float | None:
    if not value:
        return None
    rounded = round(float(value))
    if abs(float(value) - rounded) < 0.05:
        return int(rounded)
    return round(float(value), 1)


def main() -> None:
    polygons = locator_polygons()
    units = json.loads((DATA / "units.json").read_text())
    geo = json.loads((DATA / "units.geojson").read_text())
    features = {feat["properties"]["id"]: feat for feat in geo["features"]}
    changed = []
    still_points = []

    for unit in units:
        feat = features[unit["id"]]
        if feat["properties"].get("source") == "usace" or str(unit["id"]).startswith("usace"):
            continue
        ids = [str(item) for item in (unit.get("unitIds") or [unit["id"]])]
        parts = [polygons[uid]["geometry"] for uid in ids if uid in polygons]
        if not parts:
            if feat["geometry"]["type"] == "Point":
                still_points.append(unit["id"])
            continue
        geom = clean_polygonal(dissolve(parts, simplify=0.0008))
        if geom is None or geom.is_empty:
            continue
        old = shape(feat["geometry"])
        acres = whole_acres(sum(polygons[uid]["acres"] or 0 for uid in ids if uid in polygons))
        previous = unit.get("acres")
        center = centroid_point(geom)
        unit["lon"] = center.x
        unit["lat"] = center.y
        if acres and (previous is None or abs(float(previous) - float(acres)) >= 1):
            unit["acres"] = acres
            feat["properties"]["acres"] = acres
        feat["geometry"] = geojson_polygon(geom)
        feat["properties"]["lon"] = center.x
        feat["properties"]["lat"] = center.y
        same = old.equals(geom) if old.geom_type != "Point" else False
        if not same:
            changed.append(unit["id"])

    text_units = json.dumps(units, ensure_ascii=False, separators=(",", ":"))
    text_geo = json.dumps(geo, ensure_ascii=False, separators=(",", ":"))
    for directory in (DATA, PUBLIC):
        (directory / "units.json").write_text(text_units)
        (directory / "units.geojson").write_text(text_geo)

    meta_path = DATA / "meta.json"
    meta = json.loads(meta_path.read_text())
    meta["polygonCount"] = sum(1 for feat in geo["features"] if feat["geometry"]["type"] != "Point")
    meta_text = json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
    meta_path.write_text(meta_text)
    shutil.copyfile(meta_path, PUBLIC / "meta.json")

    print(f"updated {len(changed)} units")
    print("changed:", ", ".join(changed))
    print("still points:", ", ".join(still_points))
    print("polygonCount", meta["polygonCount"])


if __name__ == "__main__":
    main()
