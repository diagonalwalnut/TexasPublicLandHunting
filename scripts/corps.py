"""Build U.S. Army Corps of Engineers (USACE) hunting areas from the curated dataset.

The curated source of truth is ``data/corps/areas.json`` (one entry per Texas
Corps lake with public hunting). Each area is mapped to a ``Unit`` compatible with
the TPWD pipeline plus Corps-specific fields, a set of opportunities (species x
method x date window) with ``access="corps_permit"``, and a GeoJSON feature.

Season date windows reuse the same machinery as the TPWD catalog: the county
Outdoor Annual calendars (``county_seasons.windows_from_county``) with a regional
fallback (``seasons.windows_for``), so Corps and TPWD dates stay consistent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shapely.geometry import shape

from county_seasons import lookup_county, windows_from_county
from geometry import centroid_point, geom_to_geojson
from seasons import windows_for
from species import SPECIES

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CORPS_DIR = DATA / "corps"

CORPS_ACCESS = "corps_permit"
CORPS_TYPE = "corps_lake"
CORPS_SOURCE = "usace"

VALID_METHODS = {"archery", "firearm", "muzzleloader", "shotgun", "any_legal"}

# Only allow links to a small set of official/known hosts.
ALLOWED_LINK_SUFFIXES = (
    ".usace.army.mil",
    "tpwd.texas.gov",
    "recreation.gov",
    "tamu.edu",
    "angelo.edu",
)


def _safe_link(url: str) -> str:
    url = (url or "").strip()
    if not url.lower().startswith("https://"):
        return ""
    host = url.split("/", 3)[2].lower()
    host = host.split("@")[-1].split(":")[0]
    if any(host == suf.lstrip(".") or host.endswith(suf) for suf in ALLOWED_LINK_SUFFIXES):
        return url
    return ""


def _clean_links(raw: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in raw or []:
        url = _safe_link(str(item.get("url") or ""))
        label = str(item.get("label") or "").strip()
        if url and label:
            out.append({"label": label, "url": url})
    return out


def _date_method(species: str, method: str) -> str:
    """Pick the county-calendar season to borrow dates from for a Corps method."""
    if species in {"white_tailed_deer", "mule_deer"} and method == "shotgun":
        # Shotgun slugs for deer are used during the general (firearm) season.
        return "firearm"
    return method


def _windows(
    county_index: dict[str, Any],
    county_pages: list[dict[str, Any]],
    region: str,
    species: str,
    method: str,
) -> tuple[list[dict[str, str]], str, str]:
    """Return (windows, dateSource, sourceCounty) for a species/method."""
    date_method = _date_method(species, method)
    for page in county_pages:
        found = windows_from_county(page, species, date_method, CORPS_ACCESS)
        if found:
            return found, "county", page["county"]
    return windows_for(species, date_method, region, CORPS_ACCESS), "county_default", ""


def _load_geometry(area: dict[str, Any]):
    """Return a Shapely geometry for an area, or None for a point fallback."""
    spec = str(area.get("geometry") or "point").strip().lower()
    if spec in {"", "point", "tier0"}:
        return None
    # "digitized" or an explicit relative path -> read a committed GeoJSON file.
    rel = area["id"] + ".geojson" if spec == "digitized" else spec
    path = CORPS_DIR / rel
    if not path.exists():
        return None
    fc = json.loads(path.read_text())
    geoms = []
    feats = fc.get("features") if isinstance(fc, dict) else None
    if feats is None and isinstance(fc, dict) and fc.get("type"):
        feats = [{"geometry": fc}]
    for feat in feats or []:
        geom = feat.get("geometry") or feat
        if not geom or geom.get("type") not in {"Polygon", "MultiPolygon"}:
            continue
        try:
            geoms.append(shape(geom))
        except Exception:
            continue
    if not geoms:
        return None
    from shapely.ops import unary_union

    merged = unary_union(geoms)
    if merged.is_empty or merged.geom_type not in {"Polygon", "MultiPolygon"}:
        return None
    return merged.simplify(0.0008, preserve_topology=True)


def load_areas() -> list[dict[str, Any]]:
    path = CORPS_DIR / "areas.json"
    return json.loads(path.read_text())


def build_corps(
    county_index: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (units, opportunities, features) for all curated Corps areas."""
    areas = load_areas()
    units: list[dict[str, Any]] = []
    opportunities: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []
    opp_id = 0

    for area in areas:
        area_id = str(area["id"]).strip()
        name = str(area["name"]).strip()
        counties = [str(c).strip() for c in area.get("counties", []) if str(c).strip()]
        region = str(area.get("region") or "").strip()
        lon = area.get("lon")
        lat = area.get("lat")

        county_pages: list[dict[str, Any]] = []
        seen: set[str] = set()
        for cname in counties:
            page = lookup_county(county_index, cname)
            if not page or page.get("slug") in seen:
                continue
            seen.add(page.get("slug"))
            county_pages.append(page)

        geom = _load_geometry(area)
        if geom is not None:
            c = centroid_point(geom)
            if c:
                lon, lat = c.x, c.y

        species_entries = area.get("species", [])
        species_set = sorted({e["species"] for e in species_entries})
        methods_set = sorted(
            {m for e in species_entries for m in e.get("methods", []) if m in VALID_METHODS}
        )
        links = _clean_links(area.get("links", []))
        map_pdf = _safe_link(str(area.get("mapPdfUrl") or ""))

        unit = {
            "id": area_id,
            "unitIds": [area_id],
            "name": name,
            "counties": counties,
            "region": region,
            "acres": area.get("acres"),
            "type": CORPS_TYPE,
            "source": CORPS_SOURCE,
            "managingAgency": str(area.get("managingAgency") or "").strip(),
            "permitRequired": bool(area.get("permitRequired")),
            "permitInfo": str(area.get("permitInfo") or "").strip(),
            "permitCost": str(area.get("permitCost") or "").strip(),
            "means": str(area.get("means") or "").strip(),
            "links": links,
            "mapPdfUrl": map_pdf,
            "pdfUrl": "",
            "aerialPdfUrl": "",
            "registration": "none",
            "legalGameTags": [],
            "legalGameText": str(area.get("means") or "").strip(),
            "species": species_set,
            "methods": methods_set,
            "access": [CORPS_ACCESS],
            "complexes": [],
            "hasEpostcard": False,
            "hasRegularPermit": False,
            "epostcardUrl": "",
            "countySlugs": [p["slug"] for p in county_pages],
            "bookletPage": None,
            "bookletPdfPage": None,
            "bookletUrl": "",
            "lon": round(lon, 5) if lon is not None else None,
            "lat": round(lat, 5) if lat is not None else None,
        }
        if geom is not None:
            unit["boundaryNote"] = (
                "Map boundary is the Corps project land from USGS PAD-US, "
                "not the hunt compartments in the lake PDF."
            )
        units.append(unit)

        unit_methods: set[str] = set()
        for entry in species_entries:
            species = entry["species"]
            species_label = SPECIES.get(species, species)
            note = str(entry.get("notes") or "").strip()
            for method in entry.get("methods", []):
                if method not in VALID_METHODS:
                    continue
                wins, date_source, source_county = _windows(
                    county_index, county_pages, region, species, method
                )
                for win in wins:
                    opp_id += 1
                    opportunities.append(
                        {
                            "id": f"co{opp_id}",
                            "unitId": area_id,
                            "species": species,
                            "speciesLabel": species_label,
                            "methods": [method],
                            "access": CORPS_ACCESS,
                            "start": win["start"],
                            "end": win["end"],
                            "dateSource": date_source,
                            "county": source_county,
                            "notes": note,
                        }
                    )
                    unit_methods.add(method)

        unit["methods"] = sorted(unit_methods) or methods_set

        if geom is not None:
            geometry = geom_to_geojson(geom)
        elif unit["lon"] is not None and unit["lat"] is not None:
            geometry = {"type": "Point", "coordinates": [unit["lon"], unit["lat"]]}
        else:
            continue
        props = {k: v for k, v in unit.items() if k not in {"lon", "lat"}}
        props["lon"] = unit["lon"]
        props["lat"] = unit["lat"]
        features.append(
            {"type": "Feature", "id": area_id, "properties": props, "geometry": geometry}
        )

    return units, opportunities, features
