#!/usr/bin/env python3
"""Cut closed areas out of Corps lakes and add entry and parking points.

Whitney and Aquilla hunting polygons come from the 2025 Corps map scans.
Other lakes keep the PAD-US project polygon, with a named state park removed
when that park sits inside the project. Parking and ramps are geocoded from
Corps-published addresses. Results are committed so the site does not call
Nominatim at runtime.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from shapely.geometry import Point, shape
from shapely.validation import make_valid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from corps_gis import splice_published  # noqa: E402
from corps_hunt_maps import extract_all  # noqa: E402
from geometry import geom_to_geojson  # noqa: E402

CORPS = ROOT / "data" / "corps"
AREAS_PATH = CORPS / "areas.json"
USER_AGENT = "TexasPublicLandHunting/1.0 (corps hunt boundaries)"

MAP_PDF = {
    "usace-whitney": "https://www.swf-wc.usace.army.mil/whitney/maps/WH_2025_Map.pdf",
    "usace-aquilla": "https://www.swf-wc.usace.army.mil/whitney/maps/AQ_2025_Map.pdf",
    "usace-georgetown": "https://www.swf-wc.usace.army.mil/georgetown/maps/NFHuntingPolicy_MapandRules.pdf",
}
PERMIT = "https://www.recreation.gov/permits/5303030"
INTERACTIVE = "https://arcg.is/0uS01W2"
DISTRICT_GUIDE = (
    "https://www.swf-wc.usace.army.mil/lake/"
    "Fort%20Worth%20District%20Hunting%20Guide%202026-2027_FINAL_11%20AUG%202026.pdf"
)
EXTRA_LINKS = {
    "usace-whitney": [("Interactive hunting map (USACE)", INTERACTIVE)],
    "usace-aquilla": [("Interactive hunting map (USACE)", INTERACTIVE)],
    "usace-wright-patman": [
        (
            "Hunting access GPS (PDF)",
            "https://www.swf-wc.usace.army.mil/wrightpatman/pdf/WP_Hunting_GPS_Coordinates.pdf",
        )
    ],
}
# Locked district viewers. Linked so hunters can open the official map.
WEB_MAP = {
    "usace-bardwell": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=60fc9b8aba5640d8a943fccaa01f47d5",
    "usace-belton": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=559413736d3449b2b4de2e545828daaf",
    "usace-benbrook": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=d8adb31954884f3ab88d743a8a593068",
    "usace-georgetown": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=b9d30fa3821e4b9fab42e0ed554e9cbe",
    "usace-grapevine": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=6e92400275314a8faa931da055dfc9e6",
    "usace-lake-o-the-pines": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=f9acd9901a6d4c16a76053bfc15b8d2c",
    "usace-lavon": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=010ac384662544b9bdb81f02d15b5a47",
    "usace-lewisville": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=b3dc9801121f418ba9aed2404308e72c",
    "usace-navarro-mills": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=c7140c90ba8a46a9844954df85d72569",
    "usace-proctor": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=35b65fce9f3341d7bf7d01bad1ae59f1",
    "usace-sam-rayburn": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=7ec5491aaaa34d6d9b287fec2e4e8b93",
    "usace-somerville": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=659e56a613f74e89bdee98af12b9914d",
    "usace-stillhouse-hollow": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=c9c0e84a4b354374aad1bb0f97275b38",
    "usace-town-bluff": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=1199c0b4a0f24ddfa19e22d7deb1fb68",
    "usace-waco": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=4160eb459622469f91e44f13f81cc86c",
    "usace-wright-patman": "https://usace-swf.maps.arcgis.com/apps/webappviewer/index.html?id=281a9edbdb434ab8a577ae3e85602ed2",
}


def _get_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as res:
        return json.loads(res.read().decode())


def _nominatim(params: dict) -> list:
    time.sleep(1.1)
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(params)
    data = _get_json(url)
    return data if isinstance(data, list) else []


def _lookup_polygon(osm_type: str, osm_id: int):
    time.sleep(1.1)
    url = "https://nominatim.openstreetmap.org/lookup?" + urllib.parse.urlencode(
        {"osm_ids": f"{osm_type}{osm_id}", "format": "jsonv2", "polygon_geojson": 1}
    )
    data = _get_json(url)
    if not isinstance(data, list) or not data:
        return None
    geom = data[0].get("geojson")
    if not geom or geom.get("type") not in {"Polygon", "MultiPolygon"}:
        return None
    parsed = make_valid(shape(geom))
    if parsed.geom_type == "GeometryCollection":
        parsed = unary_polygons(parsed)
    if parsed.is_empty or parsed.geom_type not in {"Polygon", "MultiPolygon"}:
        return None
    return parsed


def unary_polygons(geom):
    from shapely.ops import unary_union

    parts = [part for part in geom.geoms if part.geom_type in {"Polygon", "MultiPolygon"}]
    return unary_union(parts) if parts else geom


def _load_fc(area_id: str) -> dict:
    return json.loads((CORPS / f"{area_id}.geojson").read_text())


def _write_fc(area_id: str, geom, props: dict) -> None:
    feature = {
        "type": "Feature",
        "properties": props,
        "geometry": geom_to_geojson(geom),
    }
    (CORPS / f"{area_id}.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": [feature]})
    )


def _acres(geom) -> float:
    if geom is None or geom.is_empty:
        return 0.0
    lat = geom.centroid.y
    meters = geom.area * (111320 * __import__("math").cos(__import__("math").radians(lat))) * 110540
    return meters / 4046.86


def _near(point: Point, project, limit_deg: float = 0.04) -> bool:
    return project.buffer(limit_deg).covers(point)


def apply_hunt_maps() -> list[dict]:
    entries: list[dict] = []
    extracted = extract_all()
    for area_id, (hunt, points) in extracted.items():
        current = _load_fc(area_id)
        props = dict(current["features"][0].get("properties") or {})
        project = shape(current["features"][0]["geometry"])
        clipped = make_valid(hunt.intersection(project.buffer(0.008)))
        if clipped.is_empty or clipped.geom_type not in {"Polygon", "MultiPolygon"}:
            raise RuntimeError(f"{area_id} hunt trace missed the project polygon")
        props["boundarySource"] = "corps-hunt-map"
        props["source"] = "USACE Fort Worth District 2025 hunting map"
        _write_fc(area_id, clipped, props)
        print(f"  {area_id} hunt acres {_acres(clipped):.0f}")
        entries.extend(points)
    return entries


def _original_project(area_id: str):
    import subprocess

    raw = subprocess.check_output(
        ["git", "show", f"HEAD:data/corps/{area_id}.geojson"], cwd=ROOT
    )
    geom = make_valid(shape(json.loads(raw)["features"][0]["geometry"]))
    if not geom.is_valid:
        geom = geom.buffer(0)
    return geom


def _as_polygons(geom):
    geom = make_valid(geom)
    if geom.geom_type == "GeometryCollection":
        geom = unary_polygons(geom)
    if geom.is_empty:
        return geom
    if not geom.is_valid:
        geom = make_valid(geom.buffer(0))
    return geom


def _safe_intersection(left, right):
    left, right = _as_polygons(left), _as_polygons(right)
    try:
        return _as_polygons(left.intersection(right))
    except Exception:
        return _as_polygons(left.buffer(1e-5).intersection(right.buffer(1e-5)))


def _safe_difference(left, right):
    left, right = _as_polygons(left), _as_polygons(right)
    try:
        return _as_polygons(left.difference(right))
    except Exception:
        return _as_polygons(left.buffer(0).difference(right.buffer(0)))


def load_closures(projects: dict) -> list[dict]:
    raw = json.loads((CORPS / "closures.json").read_text())
    features = []
    for row in raw:
        geom = _lookup_polygon(str(row["osmType"]), int(row["osmId"]))
        project = projects.get(row["unitId"])
        if geom is None or project is None:
            print(f"  skip closure {row['name']}: no polygon")
            continue
        piece = _safe_intersection(geom, project)
        if piece.is_empty or piece.geom_type not in {"Polygon", "MultiPolygon"}:
            print(f"  skip closure {row['name']}: no overlap")
            continue
        acres = _acres(piece)
        if acres < 5 or acres > _acres(project) * 0.5:
            print(f"  skip closure {row['name']}: {acres:.0f} acres inside the project")
            continue
        label = piece.representative_point()
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "unitId": row["unitId"],
                    "name": row["name"],
                    "kind": row["kind"],
                    "labelLon": round(label.x, 5),
                    "labelLat": round(label.y, 5),
                },
                "geometry": geom_to_geojson(piece),
            }
        )
        print(f"  closure {row['name']} {acres:.0f} acres")
    return features


def cut_closures(closure_features: list[dict]) -> None:
    by_unit: dict[str, list[tuple[str, object]]] = {}
    for feat in closure_features:
        by_unit.setdefault(feat["properties"]["unitId"], []).append(
            (feat["properties"]["name"], shape(feat["geometry"]))
        )
    for area_id, parts in by_unit.items():
        current = _load_fc(area_id)
        props = dict(current["features"][0].get("properties") or {})
        cut = _as_polygons(shape(current["features"][0]["geometry"]))
        names: list[str] = []
        for name, part in parts:
            overlap = _safe_intersection(cut, part)
            if overlap.is_empty or _acres(overlap) < 5:
                continue
            cut = _safe_difference(cut, part)
            names.append(name)
        if not names or cut.is_empty or cut.geom_type not in {"Polygon", "MultiPolygon"}:
            print(f"  {area_id} closure cut skipped")
            continue
        props["closedNames"] = names
        if props.get("boundarySource") != "corps-hunt-map":
            props["boundarySource"] = "pad-us-minus-closed"
        _write_fc(area_id, cut, props)
        print(f"  cut {area_id}: {', '.join(names)}")


def _census(address: str) -> tuple[float, float] | None:
    url = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" + urllib.parse.urlencode(
        {"address": address, "benchmark": "Public_AR_Current", "format": "json"}
    )
    try:
        data = _get_json(url)
    except Exception:
        return None
    matches = (data.get("result") or {}).get("addressMatches") or []
    if not matches:
        return None
    coords = matches[0].get("coordinates") or {}
    if "x" not in coords or "y" not in coords:
        return None
    return float(coords["x"]), float(coords["y"])


def _geocode_row(row: dict) -> tuple[float, float] | None:
    if row.get("lon") is not None and row.get("lat") is not None:
        return float(row["lon"]), float(row["lat"])
    address = str(row.get("address") or "").strip()
    if address:
        found = _census(address)
        if found:
            return found
        swapped = address.replace(" FM ", " Farm Road ").replace(" HY ", " Highway ")
        if swapped != address:
            found = _census(swapped)
            if found:
                return found
    query = str(row.get("query") or row.get("name") or "")
    hits = _nominatim({"q": query, "format": "jsonv2", "limit": 1})
    if not hits:
        return None
    return float(hits[0]["lon"]), float(hits[0]["lat"])


def geocode_access(projects: dict) -> list[dict]:
    rows = json.loads((CORPS / "access.json").read_text())
    features = []
    for row in rows:
        project = projects.get(row["unitId"])
        if project is None:
            continue
        found = _geocode_row(row)
        if found is None:
            print(f"  miss {row['name']}")
            continue
        lon, lat = found
        point = Point(float(lon), float(lat))
        if not _near(point, project):
            print(f"  far {row['name']} {lon:.4f},{lat:.4f}")
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "unitId": row["unitId"],
                    "name": row["name"],
                    "kind": row["kind"],
                },
                "geometry": {"type": "Point", "coordinates": [round(float(lon), 5), round(float(lat), 5)]},
            }
        )
        print(f"  place {row['unitId']} {row['name']}")
    return features


def update_area_links() -> None:
    areas = json.loads(AREAS_PATH.read_text())
    for area in areas:
        area_id = area["id"]
        if area_id in MAP_PDF:
            area["mapPdfUrl"] = MAP_PDF[area_id]
        links = list(area.get("links") or [])
        urls = {link.get("url") for link in links}
        if area_id in {"usace-whitney", "usace-aquilla"} and PERMIT not in urls:
            links.insert(0, {"label": "Hunting permit (Recreation.gov)", "url": PERMIT})
        for label, url in EXTRA_LINKS.get(area_id, []):
            if url not in urls:
                links.append({"label": label, "url": url})
                urls.add(url)
        if DISTRICT_GUIDE not in urls:
            links.append({"label": "District hunting guide (PDF)", "url": DISTRICT_GUIDE})
            urls.add(DISTRICT_GUIDE)
        web = WEB_MAP.get(area_id)
        if web and web not in urls and area_id not in MAP_PDF:
            links.append({"label": "Hunting map (USACE)", "url": web})
        area["links"] = links
    AREAS_PATH.write_text(json.dumps(areas, indent=2) + "\n")


def _write_collection(path: Path, features: list[dict]) -> None:
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))


def _publish_side_files() -> None:
    public = ROOT / "web" / "public" / "data"
    public.mkdir(parents=True, exist_ok=True)
    mapping = {
        "access.geojson": "corps-access.geojson",
        "closures.geojson": "corps-closures.geojson",
    }
    for src_name, dest_name in mapping.items():
        text = (CORPS / src_name).read_text()
        (public / dest_name).write_text(text)
        (ROOT / "data" / dest_name).write_text(text)


def main() -> int:
    areas = json.loads(AREAS_PATH.read_text())
    projects = {area["id"]: _original_project(area["id"]) for area in areas}
    print("trace hunt maps")
    entries = apply_hunt_maps()
    print("closures")
    closure_features = load_closures(projects)
    cut_closures(closure_features)
    print("access")
    place_features = geocode_access(projects)
    # Map entry labels win when a geocoded place has the same name.
    seen = {(row["unitId"], row["name"]) for row in entries}
    for feat in place_features:
        key = (feat["properties"]["unitId"], feat["properties"]["name"])
        if key in seen:
            continue
        entries.append(
            {
                "unitId": feat["properties"]["unitId"],
                "name": feat["properties"]["name"],
                "kind": feat["properties"]["kind"],
                "lon": feat["geometry"]["coordinates"][0],
                "lat": feat["geometry"]["coordinates"][1],
            }
        )
    access_features = [
        {
            "type": "Feature",
            "properties": {"unitId": row["unitId"], "name": row["name"], "kind": row["kind"]},
            "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
        }
        for row in entries
    ]
    _write_collection(CORPS / "access.geojson", access_features)
    _write_collection(CORPS / "closures.geojson", closure_features)
    _publish_side_files()
    update_area_links()
    print("splice published json")
    splice_published()
    print(f"access {len(access_features)} closures {len(closure_features)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
