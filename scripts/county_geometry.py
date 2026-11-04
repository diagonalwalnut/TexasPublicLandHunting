"""Texas county polygons and the Outdoor Annual North/South split lines.

County outlines come from the Census 2023 cartographic boundary file.
Split lines are TIGER roads clipped to the counties the South Zone
boundary cuts: U.S. 90, IH 10, Spur 239, and the Bexar Loop 1604 jog.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import shapefile
from shapely.geometry import LineString, MultiLineString, Point, mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import linemerge, nearest_points, substring, unary_union
from shapely.validation import make_valid

from county_seasons import load_counties as load_county_pages

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "tiger"
DATA = ROOT / "data"
WEB_DATA = ROOT / "web" / "public" / "data"

COUNTY_ZIP = "cb_2023_us_county_500k.zip"
PRIMARY_ZIP = "tl_2023_us_primaryroads.zip"
SECONDARY_ZIP = "tl_2023_48_prisecroads.zip"
COUNTY_URL = "https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip"
PRIMARY_URL = "https://www2.census.gov/geo/tiger/TIGER2023/PRIMARYROADS/tl_2023_us_primaryroads.zip"
SECONDARY_URL = "https://www2.census.gov/geo/tiger/TIGER2023/PRISECROADS/tl_2023_48_prisecroads.zip"

# Exact TIGER FULLNAME values. Directional aliases are used only when the
# exact name does not cross the county.
ROAD_NAMES: dict[str, set[str]] = {
    "us90": {"US Hwy 90"},
    "us90_extra": {
        "E US Hwy 90",
        "W US Hwy 90",
        "US Hwy 90 E",
        "US Hwy 90 W",
        "US Hwy 90E",
        "US Hwy 90W",
    },
    "ih10": {"I- 10"},
    "ih10_extra": {"E I- 10", "I- 10 W"},
    "loop1604": {"State Loop 1604"},
    "spur239": {"Spr 239", "State Loop 239"},
}

SIMPLE_SPLITS: dict[str, str] = {
    "austin": "ih10",
    "caldwell": "ih10",
    "chambers": "ih10",
    "colorado": "ih10",
    "fayette": "ih10",
    "gonzales": "ih10",
    "guadalupe": "ih10",
    "harris": "ih10",
    "jefferson": "ih10",
    "kinney": "us90",
    "medina": "us90",
    "orange": "ih10",
    "uvalde": "us90",
    "waller": "ih10",
}

ROAD_LABEL = {
    "us90": "U.S. Highway 90",
    "ih10": "IH 10",
    "loop1604": "Loop 1604",
    "spur239": "Spur 239",
}

TX_BBOX = (-106.9, 25.5, -93.2, 36.7)


def _download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return
    import requests

    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, timeout=180, stream=True) as response:
        response.raise_for_status()
        tmp = dest.with_suffix(".part")
        with tmp.open("wb") as handle:
            for chunk in response.iter_content(1 << 20):
                if chunk:
                    handle.write(chunk)
        tmp.replace(dest)


def ensure_tiger() -> dict[str, Path]:
    """Unzip Census county and TIGER road shapefiles into cache/tiger."""
    CACHE.mkdir(parents=True, exist_ok=True)
    zips = {
        "counties": (COUNTY_ZIP, COUNTY_URL),
        "primary": (PRIMARY_ZIP, PRIMARY_URL),
        "secondary": (SECONDARY_ZIP, SECONDARY_URL),
    }
    paths: dict[str, Path] = {}
    for key, (name, url) in zips.items():
        zpath = CACHE / name
        _download(url, zpath)
        folder = CACHE / name.replace(".zip", "")
        if not folder.exists():
            with zipfile.ZipFile(zpath) as archive:
                archive.extractall(folder)
        paths[key] = folder / name.replace(".zip", ".shp")
    return paths


def _polygonal(geom: BaseGeometry) -> BaseGeometry | None:
    geom = make_valid(geom)
    if geom.is_empty:
        return None
    if geom.geom_type in {"Polygon", "MultiPolygon"}:
        return geom
    if geom.geom_type == "GeometryCollection":
        parts = [g for g in geom.geoms if g.geom_type in {"Polygon", "MultiPolygon"}]
        if not parts:
            return None
        return unary_union(parts)
    return None


def _lines(geom: BaseGeometry) -> list[LineString]:
    if geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [geom] if geom.length > 0 else []
    if geom.geom_type == "MultiLineString":
        return [g for g in geom.geoms if g.length > 0]
    if geom.geom_type == "GeometryCollection":
        out: list[LineString] = []
        for part in geom.geoms:
            out.extend(_lines(part))
        return out
    return []


def _points(geom: BaseGeometry) -> list[Point]:
    if geom.is_empty:
        return []
    if geom.geom_type == "Point":
        return [geom]
    if geom.geom_type == "MultiPoint":
        return list(geom.geoms)
    if geom.geom_type == "GeometryCollection":
        out: list[Point] = []
        for part in geom.geoms:
            out.extend(_points(part))
        return out
    return []


def _merge_lines(geom: BaseGeometry) -> BaseGeometry:
    lines = _lines(geom)
    if not lines:
        return LineString()
    if len(lines) == 1:
        return lines[0]
    return linemerge(MultiLineString(lines))


def _longest(geom: BaseGeometry) -> LineString | None:
    lines = _lines(_merge_lines(geom))
    if not lines:
        return None
    return max(lines, key=lambda line: line.length)


def _in_texas(bbox: list[float] | tuple[float, ...]) -> bool:
    xmin, ymin, xmax, ymax = bbox
    return not (xmax < TX_BBOX[0] or xmin > TX_BBOX[2] or ymax < TX_BBOX[1] or ymin > TX_BBOX[3])


def _load_named_lines(shp_path: Path, names: set[str]) -> dict[str, list[LineString]]:
    found: dict[str, list[LineString]] = {name: [] for name in names}
    reader = shapefile.Reader(str(shp_path))
    for item in reader.iterShapeRecords():
        full = item.record["FULLNAME"] or ""
        if full not in found:
            continue
        if not _in_texas(item.shape.bbox):
            continue
        geom = shape(item.shape.__geo_interface__)
        found[full].extend(_lines(geom))
    return found


def load_roads(paths: dict[str, Path]) -> dict[str, BaseGeometry]:
    wanted = set().union(*ROAD_NAMES.values())
    by_name: dict[str, list[LineString]] = {name: [] for name in wanted}
    for shp in (paths["primary"], paths["secondary"]):
        loaded = _load_named_lines(shp, wanted)
        for name, lines in loaded.items():
            by_name[name].extend(lines)
    grouped: dict[str, BaseGeometry] = {}
    for key, names in ROAD_NAMES.items():
        parts: list[LineString] = []
        for name in names:
            parts.extend(by_name.get(name, []))
        grouped[key] = unary_union(parts) if parts else LineString()
    return grouped


def load_county_shapes(paths: dict[str, Path]) -> list[tuple[str, BaseGeometry]]:
    reader = shapefile.Reader(str(paths["counties"]))
    counties: list[tuple[str, BaseGeometry]] = []
    for item in reader.iterShapeRecords():
        if item.record["STATEFP"] != "48":
            continue
        geom = _polygonal(shape(item.shape.__geo_interface__))
        if geom is None:
            continue
        counties.append((str(item.record["NAME"]), geom))
    return counties


def _clip(roads: BaseGeometry, county: BaseGeometry, widen: bool = False) -> BaseGeometry:
    """Roads inside the county. widen keeps a highway that follows the county line.

    TIGER splits a highway into short pieces. Those pieces are joined before
    short ramps are dropped, so the main road is not thrown away.
    """
    if roads.is_empty:
        return LineString()
    zone = county.buffer(0.004) if widen else county
    clipped = roads.intersection(zone)
    pieces = _lines(clipped)
    if not pieces:
        return LineString()
    merged = _merge_lines(unary_union(pieces))
    kept = []
    for line in _lines(merged):
        if line.length < 0.02:
            continue
        if widen:
            midpoint = line.interpolate(0.5, normalized=True)
            if county.distance(midpoint) > 0.004:
                continue
        kept.append(line)
    if not kept:
        return LineString()
    return unary_union(kept)


def _spans(line: BaseGeometry, county: BaseGeometry) -> bool:
    """True when the road reaches opposite sides of the county, not a short fragment."""
    if line.is_empty:
        return False
    width = county.bounds[2] - county.bounds[0]
    height = county.bounds[3] - county.bounds[1]
    if line.length < 0.35 * max(width, height):
        return False
    boundary = county.boundary
    near: list[Point] = []
    for part in _lines(line):
        for coord in (part.coords[0], part.coords[-1]):
            point = Point(coord)
            if boundary.distance(point) < 0.03:
                near.append(point)
    if len(near) < 2:
        return False
    return unary_union(near).convex_hull.length > 0.45 * max(width, height)


def _road_in_county(
    roads: dict[str, BaseGeometry],
    key: str,
    county: BaseGeometry,
    widen: bool = False,
) -> BaseGeometry:
    exact = _clip(roads[key], county, widen=widen)
    if _spans(exact, county) or key not in {"us90", "ih10"}:
        return exact
    extra = roads.get(f"{key}_extra", LineString())
    combined = _clip(unary_union([roads[key], extra]), county, widen=widen)
    return combined if combined.length > exact.length else exact


def _snap(line: LineString, point: Point) -> Point:
    return line.interpolate(line.project(point))


def _between(line: LineString, start: Point, end: Point) -> LineString:
    a = line.project(_snap(line, start))
    b = line.project(_snap(line, end))
    if a > b:
        a, b = b, a
    return substring(line, a, b)


def _close_ring(line: LineString) -> LineString:
    if line.is_empty:
        return line
    if Point(line.coords[0]).distance(Point(line.coords[-1])) < 0.002:
        if line.coords[0] != line.coords[-1]:
            return LineString(list(line.coords) + [line.coords[0]])
    return line


def _other_arc(line: LineString, start: Point, end: Point) -> LineString | None:
    ring = _close_ring(line)
    if Point(ring.coords[0]).distance(Point(ring.coords[-1])) > 0.002:
        return None
    a = ring.project(_snap(ring, start))
    b = ring.project(_snap(ring, end))
    if a > b:
        a, b = b, a
    first = substring(ring, 0, a)
    second = substring(ring, b, ring.length)
    parts = [part for part in (first, second) if not part.is_empty]
    if not parts:
        return None
    merged = linemerge(unary_union(parts))
    longest = _longest(merged)
    return longest


def _boundary_points(line: BaseGeometry, county: BaseGeometry) -> list[Point]:
    hits = _points(line.intersection(county.boundary))
    if hits:
        return hits
    near: list[Point] = []
    for part in _lines(line):
        for coord in (part.coords[0], part.coords[-1]):
            point = Point(coord)
            if county.boundary.distance(point) < 0.03:
                near.append(point)
    return near


def _as_line(geom: BaseGeometry) -> LineString | None:
    merged = _merge_lines(geom)
    return _longest(merged)


def _bridge_endpoints(lines: list[LineString], tol: float) -> list[LineString]:
    """Join road pieces whose endpoints sit across an interchange."""
    bridges: list[LineString] = []
    for index, left in enumerate(lines):
        for right in lines[index + 1 :]:
            best: tuple[float, Point, Point] | None = None
            for start in (Point(left.coords[0]), Point(left.coords[-1])):
                for end in (Point(right.coords[0]), Point(right.coords[-1])):
                    gap = start.distance(end)
                    if 1e-8 < gap <= tol and (best is None or gap < best[0]):
                        best = (gap, start, end)
            if best is not None:
                bridges.append(LineString([best[1], best[2]]))
    return lines + bridges


def _nearest_line(geom: BaseGeometry, point: Point) -> LineString:
    lines = _lines(geom)
    if not lines:
        raise RuntimeError("no road line near the split")
    return min(lines, key=lambda line: line.distance(point))


def bexar_line(roads: dict[str, BaseGeometry], county: BaseGeometry) -> BaseGeometry:
    """U.S. 90 from the west line, south along Loop 1604, then IH 10 east.

    Loop 1604, U.S. 90, and IH 10 meet at interchanges, so the TIGER lines
    stop a few hundred meters apart. Endpoints that close are bridged.
    """
    us90 = _road_in_county(roads, "us90", county)
    ih10 = _road_in_county(roads, "ih10", county)
    loop_parts = [line for line in _lines(_clip(roads["loop1604"], county)) if line.length >= 0.02]
    if us90.is_empty or ih10.is_empty or not loop_parts:
        raise RuntimeError("Bexar split is missing U.S. 90, IH 10, or Loop 1604")
    loop = _merge_lines(unary_union(_bridge_endpoints(loop_parts, 0.014)))
    ring = _longest(loop)
    if ring is None:
        raise RuntimeError("Loop 1604 did not form a line in Bexar")
    us_point = nearest_points(ring, us90)[0]
    ih_point = nearest_points(ring, ih10)[0]
    if us_point.distance(us90) > 0.015 or ih_point.distance(ih10) > 0.015:
        raise RuntimeError("Bexar Loop 1604 does not meet U.S. 90 and IH 10")

    us_line = _nearest_line(us90, us_point)
    ih_line = _nearest_line(ih10, ih_point)
    west_hits = _boundary_points(us_line, county) or _boundary_points(us90, county)
    east_hits = _boundary_points(ih_line, county) or _boundary_points(ih10, county)
    if not west_hits or not east_hits:
        raise RuntimeError("Bexar highways do not reach the county line")
    west = min(west_hits, key=lambda point: point.x)
    east = max(east_hits, key=lambda point: point.x)
    us_piece = _between(us_line, west, us_point)
    arc = _between(ring, us_point, ih_point)
    # The open loop trace can run the long way around. Keep the southern arc.
    other = _other_arc(ring, us_point, ih_point)
    if other is not None and other.centroid.y < arc.centroid.y:
        arc = other
    ih_piece = _between(ih_line, ih_point, east)
    return _merge_lines(unary_union([us_piece, arc, ih_piece]))


def _extend_to_boundary(line: LineString, county: BaseGeometry, anchor: Point) -> LineString:
    start = Point(line.coords[0])
    end = Point(line.coords[-1])
    target = start if start.distance(anchor) >= end.distance(anchor) else end
    boundary_point = nearest_points(target, county.boundary)[1]
    gap = target.distance(boundary_point)
    if gap < 1e-5 or gap > 0.06:
        return line
    if target.distance(start) <= target.distance(end):
        return LineString([boundary_point.coords[0], *list(line.coords)])
    return LineString([*list(line.coords), boundary_point.coords[0]])


def _route_between(lines: list[LineString], start_point: Point, end_point: Point) -> LineString:
    """Shortest path along road pieces. Endpoints within a meter are the same junction."""
    import heapq
    from collections import defaultdict

    adj: dict[tuple[float, float], list[tuple[tuple[float, float], list[tuple[float, float]]]]] = defaultdict(list)

    def node(coord: tuple[float, float]) -> tuple[float, float]:
        return (round(coord[0], 5), round(coord[1], 5))

    for line in lines:
        coords = [node((x, y)) for x, y in line.coords]
        cleaned = [coords[0]]
        for coord in coords[1:]:
            if coord != cleaned[-1]:
                cleaned.append(coord)
        if len(cleaned) < 2:
            continue
        adj[cleaned[0]].append((cleaned[-1], cleaned))
        adj[cleaned[-1]].append((cleaned[0], list(reversed(cleaned))))
    if not adj:
        raise RuntimeError("road graph is empty")
    start = min(adj, key=lambda item: Point(item).distance(start_point))
    goal = min(adj, key=lambda item: Point(item).distance(end_point))
    dist = {start: 0.0}
    prev: dict[tuple[float, float], tuple[float, float] | None] = {start: None}
    edge: dict[tuple[tuple[float, float], tuple[float, float]], list[tuple[float, float]]] = {}
    queue = [(0.0, start)]
    while queue:
        traveled, current = heapq.heappop(queue)
        if traveled != dist[current]:
            continue
        if current == goal:
            break
        for nxt, coords in adj[current]:
            step = Point(current).distance(Point(nxt))
            candidate = traveled + step
            if candidate < dist.get(nxt, 1e100):
                dist[nxt] = candidate
                prev[nxt] = current
                edge[(current, nxt)] = coords
                heapq.heappush(queue, (candidate, nxt))
    if goal not in prev:
        raise RuntimeError("split roads do not connect")
    chain = []
    cursor: tuple[float, float] | None = goal
    while cursor is not None:
        chain.append(cursor)
        cursor = prev[cursor]
    chain.reverse()
    full: list[tuple[float, float]] = []
    for left, right in zip(chain, chain[1:]):
        coords = edge[(left, right)]
        full.extend(coords if not full or coords[0] != full[-1] else coords[1:])
    if len(full) < 2:
        raise RuntimeError("split road path is too short")
    return LineString(full)


def _farthest_east(lines: list[LineString], origin: Point) -> Point:
    import heapq
    from collections import defaultdict

    adj: dict[tuple[float, float], list[tuple[float, float]]] = defaultdict(list)

    def node(coord: tuple[float, float]) -> tuple[float, float]:
        return (round(coord[0], 5), round(coord[1], 5))

    for line in lines:
        ends = [node(line.coords[0]), node(line.coords[-1])]
        if ends[0] == ends[1]:
            continue
        adj[ends[0]].append(ends[1])
        adj[ends[1]].append(ends[0])
    start = min(adj, key=lambda item: Point(item).distance(origin))
    dist = {start: 0.0}
    queue = [(0.0, start)]
    while queue:
        traveled, current = heapq.heappop(queue)
        if traveled != dist[current]:
            continue
        for nxt in adj[current]:
            step = Point(current).distance(Point(nxt))
            candidate = traveled + step
            if candidate < dist.get(nxt, 1e100):
                dist[nxt] = candidate
                heapq.heappush(queue, (candidate, nxt))
    return Point(max(dist, key=lambda item: item[0]))


def val_verde_line(roads: dict[str, BaseGeometry], county: BaseGeometry) -> BaseGeometry:
    """International Bridge along Spur 239 to U.S. 90, then east to Kinney.

    TIGER names the bridge approach "Spr 239" and the rest "State Loop 239".
    U.S. 90 through Del Rio is several joined pieces, separate from U.S. 90
    farther west in the county.
    """
    us_lines = _lines(_road_in_county(roads, "us90", county))
    spur_lines = _lines(_clip(roads["spur239"], county))
    if not us_lines or not spur_lines:
        raise RuntimeError("Val Verde split is missing U.S. 90 or Spur 239")
    us90 = unary_union(us_lines)
    spur_geom = unary_union(spur_lines)
    spur_point, join = nearest_points(spur_geom, us90)
    if spur_point.distance(join) > 0.04:
        raise RuntimeError("Spur 239 does not meet U.S. 90 in Val Verde")
    south = min(
        (Point(coord) for line in spur_lines for coord in (line.coords[0], line.coords[-1])),
        key=lambda point: point.y,
    )
    spur = _route_between(spur_lines, south, spur_point)
    spur = _extend_to_boundary(spur, county, join)
    east = _farthest_east(us_lines, join)
    highway = _route_between(us_lines, join, east)
    highway = _extend_to_boundary(highway, county, join)
    bridge = LineString([spur_point, join]) if spur_point.distance(join) > 1e-5 else LineString()
    parts: list[BaseGeometry] = [spur, highway]
    if not bridge.is_empty:
        parts.append(bridge)
    return _merge_lines(unary_union(parts))


def deer_zone_for(page: dict[str, Any] | None) -> str:
    if not page:
        return "none"
    zones: set[str] = set()
    for animal in page.get("animals", []):
        if animal.get("species") != "white_tailed_deer":
            continue
        zone = (animal.get("zone") or "").lower()
        if "south" in zone:
            zones.add("south")
        elif "north" in zone:
            zones.add("north")
    if zones == {"north", "south"}:
        return "split"
    if zones == {"south"}:
        return "south"
    if zones == {"north"}:
        return "north"
    return "none"


def _round_coords(value: Any, digits: int = 5) -> Any:
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, list):
        return [_round_coords(item, digits) for item in value]
    return value


def _feature(geom: BaseGeometry, props: dict[str, Any]) -> dict[str, Any]:
    raw = mapping(geom)
    raw["coordinates"] = _round_coords(raw["coordinates"])
    return {"type": "Feature", "properties": props, "geometry": raw}


def _norm(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def build_collections(
    counties: list[tuple[str, BaseGeometry]],
    roads: dict[str, BaseGeometry],
    pages_by_slug: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    slug_by_norm = {_norm(page.get("county") or slug): slug for slug, page in pages_by_slug.items()}
    county_features = []
    split_features = []
    for name, geom in sorted(counties, key=lambda item: item[0]):
        slug = slug_by_norm.get(_norm(name))
        if not slug:
            raise RuntimeError(f"no Outdoor Annual slug for {name}")
        simple = geom.simplify(0.0015, preserve_topology=True)
        simple = _polygonal(simple) or geom
        page = pages_by_slug.get(slug)
        county_features.append(
            _feature(
                simple,
                {"slug": slug, "name": page.get("county") if page else name, "deerZone": deer_zone_for(page)},
            )
        )
        line: BaseGeometry | None = None
        label = ""
        if slug in SIMPLE_SPLITS:
            key = SIMPLE_SPLITS[slug]
            line = _road_in_county(roads, key, geom, widen=True)
            label = ROAD_LABEL[key]
        elif slug == "bexar":
            line = bexar_line(roads, geom)
            label = "U.S. Highway 90, Loop 1604, and IH 10"
        elif slug == "val-verde":
            line = val_verde_line(roads, geom)
            label = "Spur 239 and U.S. Highway 90"
        if line is None or line.is_empty:
            continue
        line = line.intersection(geom.buffer(0.005))
        kept = [part for part in _lines(line) if part.length >= 0.008]
        line = unary_union(kept) if kept else line
        if line.is_empty:
            raise RuntimeError(f"split line for {slug} fell outside the county")
        simplified = []
        for part in _lines(line):
            short = part.simplify(0.0004, preserve_topology=False)
            if short.length >= 0.008:
                simplified.append(short)
        line = unary_union(simplified) if simplified else line
        split_features.append(_feature(line, {"slug": slug, "name": name, "road": label}))
    return (
        {"type": "FeatureCollection", "features": county_features},
        {"type": "FeatureCollection", "features": split_features},
    )


def pages_from_cache() -> dict[str, dict[str, Any]]:
    pages: dict[str, dict[str, Any]] = {}
    for page in load_county_pages(ROOT / "cache" / "counties").values():
        slug = page.get("slug")
        if slug:
            pages[slug] = page
    return pages


def write_county_layers(pages_by_slug: dict[str, dict[str, Any]] | None = None) -> None:
    pages = pages_by_slug if pages_by_slug is not None else pages_from_cache()
    if len(pages) < 250:
        raise RuntimeError(f"expected 254 county pages, found {len(pages)}")
    paths = ensure_tiger()
    counties = load_county_shapes(paths)
    roads = load_roads(paths)
    county_fc, split_fc = build_collections(counties, roads, pages)
    DATA.mkdir(parents=True, exist_ok=True)
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    for name, payload in (("counties.geojson", county_fc), ("county-splits.geojson", split_fc)):
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        (DATA / name).write_text(text)
        (WEB_DATA / name).write_text(text)
    print(
        f"wrote {len(county_fc['features'])} counties, {len(split_fc['features'])} split lines"
    )


def write_counties_json(pages_by_slug: dict[str, dict[str, Any]] | None = None) -> None:
    pages = pages_by_slug if pages_by_slug is not None else pages_from_cache()
    text = json.dumps(pages, ensure_ascii=False, separators=(",", ":"))
    DATA.mkdir(parents=True, exist_ok=True)
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "counties.json").write_text(text)
    (WEB_DATA / "counties.json").write_text(text)
    print(f"wrote {len(pages)} county regulation pages")


if __name__ == "__main__":
    pages = pages_from_cache()
    write_counties_json(pages)
    write_county_layers(pages)
