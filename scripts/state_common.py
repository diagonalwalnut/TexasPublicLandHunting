"""Shared helpers for multi-state hunting data builds.

Download ArcGIS GeoJSON (with paging), simplify polygons, write JSON/GeoJSON,
Census county outlines, and license-guide payloads.
"""

from __future__ import annotations

import json
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WEB_DATA = ROOT / "web" / "public" / "data"
CACHE = ROOT / "cache"

USER_AGENT = "texaspubliclandhunting-state-build/1.0"
SIMPLIFY_TOLERANCE = 0.004
COUNTY_TOLERANCE = 0.008

# Census FIPS state codes used for county outline filtering.
STATE_FIPS = {
    "nm": "35",
    "co": "08",
    "la": "22",
    "ar": "05",
    "ok": "40",
    "tx": "48",
    "or": "41",
}

# Plotly's county GeoJSON (Census Tiger-derived) — reliable public source.
CENSUS_COUNTIES_URL = (
    "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Any, *, pretty: bool = False) -> None:
    ensure_dir(path.parent)
    if pretty:
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    else:
        text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    path.write_text(text, encoding="utf-8")


def write_both(state: str, name: str, payload: Any, *, pretty: bool = False) -> None:
    """Write the same payload under data/<state>/ and web/public/data/<state>/."""
    for base in (DATA / state, WEB_DATA / state):
        write_json(base / name, payload, pretty=pretty)


def mirror_tree(state: str) -> None:
    """Copy every file from data/<state> into web/public/data/<state>."""
    src = DATA / state
    dst = WEB_DATA / state
    ensure_dir(dst)
    if dst.exists():
        for child in dst.iterdir():
            if child.is_file():
                child.unlink()
    for path in src.iterdir():
        if path.is_file():
            shutil.copy2(path, dst / path.name)


def fetch_bytes(url: str, dest: Path, *, force: bool = False, min_size: int = 200) -> Path:
    ensure_dir(dest.parent)
    if dest.exists() and dest.stat().st_size >= min_size and not force:
        return dest
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as res:
        dest.write_bytes(res.read())
    return dest


def fetch_json(url: str, dest: Path | None = None, *, force: bool = False) -> Any:
    if dest is not None:
        fetch_bytes(url, dest, force=force)
        return json.loads(dest.read_text(encoding="utf-8"))
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as res:
        return json.loads(res.read().decode("utf-8"))


def _with_query(url: str, **params: Any) -> str:
    parts = urllib.parse.urlsplit(url)
    q = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
    for key, value in params.items():
        if value is None:
            continue
        q[key] = str(value)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(q), parts.fragment)
    )


def download_geojson(
    url: str,
    dest: Path,
    *,
    page_size: int = 1000,
    force: bool = False,
) -> dict[str, Any]:
    """Download an ArcGIS (or plain) GeoJSON query, paging with resultOffset."""
    if dest.exists() and dest.stat().st_size > 1000 and not force:
        return json.loads(dest.read_text(encoding="utf-8"))

    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        page_url = _with_query(
            url,
            resultOffset=offset,
            resultRecordCount=page_size,
            f="geojson",
            outSR=4326,
            returnGeometry="true",
        )
        # Some URLs already set f=geojson; keep them.
        if "f=" not in url.lower():
            page_url = _with_query(page_url, f="geojson")
        try:
            payload = fetch_json(page_url)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"GeoJSON download failed ({exc.code}): {page_url}") from exc
        if isinstance(payload, dict) and payload.get("error"):
            raise RuntimeError(f"GeoJSON error from {page_url}: {payload['error']}")
        batch = payload.get("features") if isinstance(payload, dict) else None
        if not batch:
            break
        features.extend(batch)
        if len(batch) < page_size:
            break
        offset += len(batch)
        if offset > 50000:
            break

    fc = {"type": "FeatureCollection", "features": features}
    write_json(dest, fc)
    return fc


def simplify_geometry(geom: Any, tolerance: float = SIMPLIFY_TOLERANCE) -> Any:
    try:
        g = shape(geom) if not hasattr(geom, "geom_type") else geom
    except Exception:
        return None
    g = make_valid(g)
    if g.is_empty:
        return None
    if g.geom_type == "GeometryCollection":
        polys = [p for p in g.geoms if p.geom_type in {"Polygon", "MultiPolygon"} and not p.is_empty]
        if not polys:
            return None
        g = unary_union(polys)
    if g.geom_type not in {"Polygon", "MultiPolygon"}:
        return None
    simplified = g.simplify(tolerance, preserve_topology=True)
    simplified = make_valid(simplified)
    if simplified.is_empty or simplified.geom_type not in {"Polygon", "MultiPolygon"}:
        return None
    return simplified


def simplify_feature(
    feature: dict[str, Any],
    props: dict[str, Any],
    *,
    tolerance: float = SIMPLIFY_TOLERANCE,
    feature_id: str | None = None,
) -> dict[str, Any] | None:
    geom = simplify_geometry(feature.get("geometry"), tolerance)
    if geom is None:
        return None
    fid = feature_id if feature_id is not None else props.get("id")
    out: dict[str, Any] = {
        "type": "Feature",
        "properties": props,
        "geometry": mapping(geom),
    }
    if fid is not None:
        out["id"] = fid
    return out


def feature_collection(features: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "FeatureCollection", "features": list(features)}


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "unit"


def title_case_name(raw: str) -> str:
    raw = re.sub(r"\s+", " ", (raw or "").strip())
    if not raw:
        return ""
    parts = []
    for word in raw.split(" "):
        if word.isupper() and len(word) > 2:
            parts.append(word.title())
        else:
            parts.append(word)
    return " ".join(parts)


def acres_from_props(props: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        if key in props and props[key] not in (None, ""):
            try:
                return round(float(props[key]), 1)
            except (TypeError, ValueError):
                continue
    return None


def centroid_lon_lat(geom: Any) -> tuple[float | None, float | None]:
    try:
        c = geom.centroid
        return round(float(c.x), 5), round(float(c.y), 5)
    except Exception:
        return None, None


def load_census_counties(state_code: str, *, force: bool = False) -> dict[str, Any]:
    """Return simplified county FeatureCollection for a two-letter state code."""
    fips = STATE_FIPS[state_code.lower()]
    cache_path = CACHE / "census" / "counties-fips.geojson"
    raw = fetch_json(CENSUS_COUNTIES_URL, cache_path, force=force)
    features = []
    for feat in raw.get("features", []):
        props = feat.get("properties") or {}
        if str(props.get("STATE") or "") != fips:
            continue
        name = str(props.get("NAME") or "").strip()
        county_fips = str(props.get("COUNTY") or "").zfill(3)
        geoid = f"{fips}{county_fips}"
        out_props = {
            "id": f"county:{geoid}",
            "name": name,
            "state": state_code.lower(),
            "stateFips": fips,
            "countyFips": county_fips,
            "geoid": geoid,
        }
        simplified = simplify_feature(feat, out_props, tolerance=COUNTY_TOLERANCE, feature_id=out_props["id"])
        if simplified:
            features.append(simplified)
    features.sort(key=lambda f: f["properties"]["name"])
    return feature_collection(features)


def counties_index(geo: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for feat in geo.get("features", []):
        p = feat["properties"]
        rows.append(
            {
                "id": p["id"],
                "name": p["name"],
                "state": p["state"],
                "geoid": p["geoid"],
                "slug": slugify(p["name"]),
            }
        )
    return rows


def license_guide(
    *,
    title: str,
    season_year: str,
    intro: str,
    where_to_buy: list[dict[str, str]],
    deadlines: list[dict[str, Any]],
    fees: list[dict[str, str]],
    sources: list[dict[str, str]],
    hunt_series: list[dict[str, Any]] | None = None,
    preference_points: list[str] | None = None,
    residency_rules: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": title,
        "seasonYear": season_year,
        "intro": intro,
        "whereToBuy": where_to_buy,
        "deadlines": deadlines,
        "fees": fees,
        "sources": sources,
    }
    if hunt_series is not None:
        payload["huntSeries"] = hunt_series
    if preference_points is not None:
        payload["preferencePoints"] = preference_points
    if residency_rules is not None:
        payload["residencyRules"] = residency_rules
    return payload


def regulation_guide(
    *,
    title: str,
    methods: list[dict[str, str]],
    prohibited: list[str],
    unit_rules: list[str],
    sources: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "title": title,
        "methods": methods,
        "prohibited": prohibited,
        "unitRules": unit_rules,
        "sources": sources,
    }


def meta_shell(
    *,
    season_year: str,
    disclaimer: str,
    sources: list[dict[str, str]],
    species: list[dict[str, str]],
    methods: list[dict[str, str]],
    access: list[dict[str, str]],
    counts: dict[str, Any],
    profile: str,
    agency: str,
) -> dict[str, Any]:
    payload = {
        "seasonYear": season_year,
        "generatedAt": now_iso(),
        "profile": profile,
        "agency": agency,
        "disclaimer": disclaimer,
        "sources": sources,
        "species": species,
        "methods": methods,
        "access": access,
        "counts": counts,
    }
    payload.update(counts)
    return payload


def map_units_from_geojson(
    fc: dict[str, Any],
    *,
    id_fn: Callable[[dict[str, Any], int], str],
    props_fn: Callable[[dict[str, Any], str], dict[str, Any]],
    tolerance: float = SIMPLIFY_TOLERANCE,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build unit rows + simplified FeatureCollection from a raw GeoJSON FC."""
    units: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []
    for idx, feat in enumerate(fc.get("features", [])):
        raw = feat.get("properties") or {}
        uid = id_fn(raw, idx)
        props = props_fn(raw, uid)
        simplified = simplify_feature(feat, props, tolerance=tolerance, feature_id=uid)
        if simplified is None:
            continue
        lon, lat = centroid_lon_lat(shape(simplified["geometry"]))
        props = {**props, "lon": lon, "lat": lat}
        simplified["properties"] = props
        units.append(props)
        features.append(simplified)
    return units, feature_collection(features)


def report_fetch(label: str, ok: bool, detail: str = "") -> None:
    status = "ok" if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {label}{suffix}")
