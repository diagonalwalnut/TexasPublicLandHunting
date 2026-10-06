#!/usr/bin/env python3
"""Download USGS PAD-US project polygons for Texas Corps hunting lakes.

Each lake is matched to a USACE-managed feature on the PAD-US 4.1 fee layer.
The polygon is the Corps project land, not the hunt compartments in the lake
PDF. A candidate whose centroid is far from the curated lake coordinate is
rejected, and that lake stays a point.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import requests
from shapely.geometry import shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from corps import build_corps, load_areas  # noqa: E402
from geometry import centroid_point, geom_to_geojson  # noqa: E402

CORPS_DIR = ROOT / "data" / "corps"
AREAS_PATH = CORPS_DIR / "areas.json"
QUERY_URL = (
    "https://edits.nationalmap.gov/arcgis/rest/services/PAD-US/"
    "PAD_US_Landforms/MapServer/0/query"
)
# Curated point must fall near the polygon. 0.75 degrees is about 50 miles.
MAX_OFFSET_DEG = 0.75

# Exact PAD-US Unit_Nm values, tried in order. Fee recreation areas are the
# project land. Steinhagen has no single fee polygon, so the named easement
# parcels are unioned. Whitney's fee polygon is labeled "Whitney Point".
CANDIDATES: dict[str, list[tuple[str, str]]] = {
    "usace-aquilla": [("Aquilla Recreation Area", "Fee")],
    "usace-bardwell": [("Bardwell Recreation Area", "Fee")],
    "usace-belton": [("Belton Recreation Area", "Fee")],
    "usace-benbrook": [("Benbrook Recreation Area", "Fee")],
    "usace-georgetown": [("Georgetown Recreation Area", "Fee")],
    "usace-grapevine": [("Grapevine Recreation Area", "Fee")],
    "usace-lake-o-the-pines": [("Lake O' The Pines Recreation Area", "Fee")],
    "usace-lavon": [("Lavon Recreation Area", "Fee")],
    "usace-lewisville": [("Lewisville Recreation Area", "Fee")],
    "usace-navarro-mills": [("Navarro Mills Recreation Area", "Fee")],
    "usace-proctor": [("Proctor Recreation Area", "Fee")],
    "usace-sam-rayburn": [("Sam Rayburn Recreation Area", "Fee")],
    "usace-somerville": [("Somerville Recreation Area", "Fee")],
    "usace-stillhouse-hollow": [("Stillhouse Recreation Area", "Fee")],
    "usace-town-bluff": [
        ("B.A. Steinhagen", "Easement"),
        ("Steinhagen Lake", "Designation"),
    ],
    "usace-waco": [("Waco Recreation Area", "Fee")],
    "usace-whitney": [
        ("Whitney Point Recreation Area", "Fee"),
        ("Whitney Lake", "Designation"),
    ],
    "usace-wright-patman": [("Wright Patman Recreation Area", "Fee")],
}


def _where(unit_name: str, feat_class: str) -> str:
    escaped = unit_name.replace("'", "''")
    return (
        "State_Nm='TX' AND Mang_Name='USACE' "
        f"AND Unit_Nm='{escaped}' AND FeatClass='{feat_class}'"
    )


def _fetch(unit_name: str, feat_class: str) -> list:
    res = requests.get(
        QUERY_URL,
        params={
            "where": _where(unit_name, feat_class),
            "outFields": "Unit_Nm,FeatClass",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
            "geometryPrecision": "5",
            "maxAllowableOffset": "0.001",
        },
        timeout=180,
    )
    res.raise_for_status()
    payload = res.json()
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    geoms = []
    for feat in payload.get("features") or []:
        geom = feat.get("geometry")
        if not geom:
            continue
        try:
            parsed = shape(geom)
        except Exception:
            continue
        if parsed.is_empty:
            continue
        if not parsed.is_valid:
            from shapely.validation import make_valid

            parsed = make_valid(parsed)
        if parsed.geom_type == "GeometryCollection":
            parts = [part for part in parsed.geoms if part.geom_type in {"Polygon", "MultiPolygon"}]
            if not parts:
                continue
            parsed = unary_union(parts)
        if parsed.geom_type not in {"Polygon", "MultiPolygon"} or parsed.is_empty:
            continue
        geoms.append(parsed)
    return geoms


def _near(geom, lon: float, lat: float) -> bool:
    center = centroid_point(geom)
    if center is None:
        return False
    return abs(center.x - lon) <= MAX_OFFSET_DEG and abs(center.y - lat) <= MAX_OFFSET_DEG


def fetch_area(area: dict) -> tuple[object | None, str]:
    lon = float(area["lon"])
    lat = float(area["lat"])
    tried = []
    for unit_name, feat_class in CANDIDATES.get(area["id"], []):
        tried.append(f"{unit_name} ({feat_class})")
        geoms = _fetch(unit_name, feat_class)
        if not geoms:
            continue
        merged = unary_union(geoms)
        if merged.geom_type not in {"Polygon", "MultiPolygon"}:
            continue
        if not _near(merged, lon, lat):
            center = centroid_point(merged)
            print(
                f"  skip {area['id']}: {unit_name} centroid "
                f"{center.x if center else '?'},{center.y if center else '?'} "
                f"is far from {lon},{lat}"
            )
            continue
        simplified = merged.simplify(0.0008, preserve_topology=True)
        if simplified.is_empty or simplified.geom_type not in {"Polygon", "MultiPolygon"}:
            simplified = merged
        return simplified, unit_name
    return None, "; ".join(tried)


def write_polygon(area_id: str, name: str, geom, padus_name: str) -> None:
    feature = {
        "type": "Feature",
        "properties": {
            "id": area_id,
            "name": name,
            "source": "USGS PAD-US 4.1",
            "padusUnit": padus_name,
        },
        "geometry": geom_to_geojson(geom),
    }
    path = CORPS_DIR / f"{area_id}.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [feature]}))


def county_index_from_published() -> dict:
    path = ROOT / "web" / "public" / "data" / "counties.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    index: dict = {}
    pages = raw.values() if isinstance(raw, dict) else raw
    for page in pages:
        if not isinstance(page, dict) or not page.get("county"):
            continue
        index[str(page["county"]).lower()] = page
        slug = str(page.get("slug") or "")
        if slug:
            index[slug.replace("-", " ")] = page
    return index


def splice_published() -> None:
    """Replace Corps features in the published JSON without rebuilding TPWD data."""
    county_index = county_index_from_published()
    units, opps, features = build_corps(county_index)
    for folder in (ROOT / "data", ROOT / "web" / "public" / "data"):
        units_path = folder / "units.json"
        opps_path = folder / "opportunities.json"
        geo_path = folder / "units.geojson"
        meta_path = folder / "meta.json"
        if not units_path.exists():
            continue
        published_units = [u for u in json.loads(units_path.read_text()) if u.get("source") != "usace"]
        published_units.extend(units)
        published_opps = [
            o for o in json.loads(opps_path.read_text()) if not str(o.get("unitId", "")).startswith("usace-")
        ]
        published_opps.extend(opps)
        collection = json.loads(geo_path.read_text())
        kept = [
            f
            for f in collection.get("features", [])
            if (f.get("properties") or {}).get("source") != "usace"
        ]
        kept.extend(features)
        collection["features"] = kept
        meta = json.loads(meta_path.read_text())
        meta["unitCount"] = len(published_units)
        meta["opportunityCount"] = len(published_opps)
        meta["polygonCount"] = sum(1 for f in kept if f.get("geometry", {}).get("type") != "Point")
        meta["countiesWithCalendars"] = sum(1 for u in published_units if u.get("countySlugs"))
        for path, obj in (
            (units_path, published_units),
            (opps_path, published_opps),
            (geo_path, collection),
            (meta_path, meta),
        ):
            path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
        print(f"updated {folder} ({meta['polygonCount']} polygons)")


def main() -> int:
    areas = load_areas()
    matched = []
    unmatched = []
    for area in areas:
        print(f"fetch {area['id']}")
        geom, label = fetch_area(area)
        if geom is None:
            area["geometry"] = "point"
            area["tier"] = 0
            unmatched.append(area["id"])
            print(f"  point ({label or 'no candidate'})")
            continue
        write_polygon(area["id"], area["name"], geom, label)
        area["geometry"] = f"{area['id']}.geojson"
        area["tier"] = 1
        matched.append(area["id"])
        print(f"  polygon {label}")
    AREAS_PATH.write_text(json.dumps(areas, indent=2) + "\n")
    print(f"matched {len(matched)} unmatched {len(unmatched)}: {', '.join(unmatched) or 'none'}")
    splice_published()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
