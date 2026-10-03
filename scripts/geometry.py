"""Parse TPWD KMZ/KML hunt-area and dove-lease polygons into Shapely geometries."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from shapely.geometry import MultiPolygon, Point, Polygon, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union
from shapely.validation import make_valid

NS_STRIP = re.compile(r"\{[^}]+\}")
COORD_PAIR = re.compile(r"(-?\d+\.?\d*)[,\s]+(-?\d+\.?\d*)")

HUNT_SKIP_CLASSES = {
    "Private In-holdings",
    "No Public Access",
    "Waterfowl Sanctuary",
    "No Hunt Zone",
    "No Hunt Zone (Walk-In Only)",
    "No Hunting Recreation Compartment",
    "Road Easement -  S",
    "Lake",
    "Hunting Compartment - Label",
}

PREFER_CLASSES = {
    "Property Boundary",
    "State Park Boundary",
    "Hunting Area",
    "Walk-in Hunting",
    "Archery Hunting Only",
    "Archery Hunting Only (Walk-In)",
}


def _kml_table(desc: str) -> dict[str, str]:
    pairs = re.findall(
        r"<td>([^<]+)</td>\s*(?:</tr>\s*<tr[^>]*>\s*)?<td>([^<]*)</td>",
        desc,
        flags=re.I,
    )
    out: dict[str, str] = {}
    for key, val in pairs:
        key = key.strip()
        val = val.strip()
        if key and key not in out:
            out[key] = val
    return out


def _rings_from_coords(text: str) -> list[list[tuple[float, float]]]:
    rings: list[list[tuple[float, float]]] = []
    for block in re.findall(r"<coordinates[^>]*>(.*?)</coordinates>", text, flags=re.I | re.S):
        pts: list[tuple[float, float]] = []
        for tok in re.split(r"\s+", block.strip()):
            if not tok:
                continue
            parts = tok.split(",")
            if len(parts) < 2:
                continue
            try:
                lon, lat = float(parts[0]), float(parts[1])
            except ValueError:
                continue
            pts.append((lon, lat))
        if len(pts) >= 4:
            rings.append(pts)
    return rings


def _polygon(rings: list[list[tuple[float, float]]]) -> Polygon | MultiPolygon | None:
    polys: list[Polygon] = []
    for ring in rings:
        if ring[0] != ring[-1]:
            ring = ring + [ring[0]]
        try:
            poly = Polygon(ring)
        except Exception:
            continue
        if not poly.is_valid:
            poly = make_valid(poly)
        geom = poly
        if geom.is_empty:
            continue
        if geom.geom_type == "Polygon":
            polys.append(geom)
        elif geom.geom_type == "MultiPolygon":
            polys.extend(list(geom.geoms))
        elif geom.geom_type == "GeometryCollection":
            for g in geom.geoms:
                if g.geom_type == "Polygon":
                    polys.append(g)
                elif g.geom_type == "MultiPolygon":
                    polys.extend(list(g.geoms))
    if not polys:
        return None
    if len(polys) == 1:
        return polys[0]
    return MultiPolygon(polys)


def parse_kml_polygons(path: Path, id_fields: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    """Return unitId -> {name, acres, class, geometry, pdf}."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for m in re.finditer(r"<Placemark[^>]*>(.*?)</Placemark>", text, flags=re.S | re.I):
        body = m.group(1)
        name_m = re.search(r"<name>(.*?)</name>", body, flags=re.S | re.I)
        name = re.sub(r"\s+", " ", name_m.group(1)).strip() if name_m else ""
        desc_m = re.search(r"<description><!\[CDATA\[(.*?)\]\]></description>", body, flags=re.S)
        desc = desc_m.group(1) if desc_m else ""
        fields = _kml_table(desc)
        class_name = fields.get("Class") or ""
        if class_name in HUNT_SKIP_CLASSES:
            continue
        unit_id = ""
        for field in id_fields:
            raw = fields.get(field) or ""
            raw = re.sub(r"[^0-9A-Za-z]", "", raw)
            if raw:
                unit_id = raw
                break
        if not unit_id:
            continue
        rings = _rings_from_coords(body)
        geom = _polygon(rings)
        if geom is None:
            continue
        acres = None
        for key in ("Acres", "ACRES", "CalcAcreage"):
            if fields.get(key):
                try:
                    acres = float(str(fields[key]).replace(",", ""))
                except ValueError:
                    acres = None
                break
        grouped[unit_id].append(
            {
                "name": fields.get("LocName") or fields.get("LEASE_NAME") or fields.get("Name") or name,
                "class": class_name,
                "acres": acres,
                "geometry": geom,
                "pdf": fields.get("MAPBOOK_PG") or "",
            }
        )

    out: dict[str, dict[str, Any]] = {}
    for unit_id, parts in grouped.items():
        finalized = _finalize_group(parts)
        if finalized:
            out[unit_id] = finalized
    return out


def _finalize_group(parts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Prefer hunt/boundary classes, dissolve, and simplify a unit's polygons."""
    preferred = [p for p in parts if p["class"] in PREFER_CLASSES]
    use = preferred or parts
    geoms = [p["geometry"] for p in use]
    try:
        merged = unary_union(geoms)
    except Exception:
        merged = geoms[0]
    if merged.is_empty:
        return None
    if merged.geom_type == "GeometryCollection":
        polys = [g for g in merged.geoms if g.geom_type in {"Polygon", "MultiPolygon"}]
        if not polys:
            return None
        merged = unary_union(polys)
    if merged.geom_type not in {"Polygon", "MultiPolygon"}:
        return None
    simplified = merged.simplify(0.001, preserve_topology=True)
    if simplified.is_empty:
        simplified = merged
    acres = next((p["acres"] for p in use if p["acres"]), None)
    return {
        "name": use[0].get("name"),
        "acres": acres,
        "geometry": simplified,
        "pdf": use[0].get("pdf", ""),
    }


def parse_arcgis_polygons(fc: dict[str, Any], id_fields: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    """Parse an Esri/ArcGIS GeoJSON polygon FeatureCollection into unitId -> record.

    Mirrors ``parse_kml_polygons`` (same class skip/prefer logic) so TPWD KMZ and
    ArcGIS boundary layers resolve identically. Coordinates are assumed WGS84
    (request with ``outSR=4326``).
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for feat in fc.get("features", []):
        props = feat.get("properties") or {}
        class_name = str(props.get("Class") or "")
        if class_name in HUNT_SKIP_CLASSES:
            continue
        geom_json = feat.get("geometry") or {}
        if geom_json.get("type") not in {"Polygon", "MultiPolygon"}:
            continue
        unit_id = ""
        for field in id_fields:
            raw = re.sub(r"[^0-9A-Za-z]", "", str(props.get(field) or ""))
            if raw:
                unit_id = raw
                break
        if not unit_id:
            continue
        try:
            geom: BaseGeometry = shape(geom_json)
        except Exception:
            continue
        if geom.is_empty:
            continue
        if not geom.is_valid:
            geom = make_valid(geom)
        if geom.geom_type not in {"Polygon", "MultiPolygon"}:
            continue
        acres = None
        for key in ("Acres", "CalcAcreage", "ACRES"):
            if props.get(key):
                try:
                    acres = float(str(props[key]).replace(",", ""))
                except ValueError:
                    acres = None
                break
        grouped[unit_id].append(
            {
                "name": props.get("LocName") or props.get("Name") or "",
                "class": class_name,
                "acres": acres,
                "geometry": geom,
                "pdf": props.get("MAPBOOK_PG") or "",
            }
        )

    out: dict[str, dict[str, Any]] = {}
    for unit_id, parts in grouped.items():
        finalized = _finalize_group(parts)
        if finalized:
            out[unit_id] = finalized
    return out


def parse_gpx_points(path: Path) -> dict[str, tuple[float, float]]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    pts: dict[str, tuple[float, float]] = {}
    for m in re.finditer(
        r'<wpt lat="([^"]+)" lon="([^"]+)">\s*<name>(.*?)</name>',
        text,
        flags=re.S,
    ):
        lat, lon, name = float(m.group(1)), float(m.group(2)), m.group(3).strip()
        pts[name] = (lon, lat)
    return pts


def round_coords(obj: Any, ndigits: int = 5) -> Any:
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], (int, float)):
            return [round(float(x), ndigits) for x in obj]
        return [round_coords(x, ndigits) for x in obj]
    return obj


def geom_to_geojson(geom, ndigits: int = 5) -> dict[str, Any]:
    gj = mapping(geom)
    gj["coordinates"] = round_coords(gj["coordinates"], ndigits)
    return gj


def dissolve(geoms: list, simplify: float = 0.008):
    valid = []
    for g in geoms:
        if g is None or g.is_empty:
            continue
        if not g.is_valid:
            g = make_valid(g)
        valid.append(g)
    if not valid:
        return None
    merged = unary_union(valid)
    if merged.is_empty:
        return None
    simple = merged.simplify(simplify, preserve_topology=True)
    return simple if not simple.is_empty else merged


def centroid_point(geom) -> Point | None:
    if geom is None or geom.is_empty:
        return None
    c = geom.centroid
    return Point(round(c.x, 5), round(c.y, 5))
