#!/usr/bin/env python3
"""Multi-state USACE Corps hunting units from data/corps/areas.json.

Extends the Texas Corps pattern: each area may include a ``state`` field
(``tx``, ``la``, ``ar``, ``ok``, ``nm``, ``co``, …). Texas areas omit season
windows and reuse Outdoor Annual county calendars via ``corps.build_corps``.
Other states use curated ``windows`` on each species entry (or defaults).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from shapely.geometry import mapping, shape  # noqa: E402

from corps import (  # noqa: E402
    ALLOWED_LINK_SUFFIXES,
    CORPS_ACCESS,
    CORPS_DIR,
    CORPS_SOURCE,
    CORPS_TYPE,
    VALID_METHODS,
    _clean_links,
    _load_geometry,
    _safe_link,
    build_corps,
    load_areas,
)
from species import SPECIES  # noqa: E402
from state_common import write_json  # noqa: E402

# Extra official hosts beyond the Texas-oriented list in corps.py
EXTRA_LINK_SUFFIXES = (
    ".usace.army.mil",
    "recreation.gov",
    "wlf.louisiana.gov",
    "louisianaoutdoors.com",
    "agfc.com",
    "wildlifedepartment.com",
    "gooutdoorsoklahoma.com",
    "wildlife.dgf.nm.gov",
    "cpw.state.co.us",
    "cpwshop.com",
    "tpwd.texas.gov",
)

DEFAULT_WINDOWS: dict[str, list[dict[str, str]]] = {
    "white_tailed_deer": [
        {"start": "2026-10-01", "end": "2027-01-15", "method": "archery"},
        {"start": "2026-11-15", "end": "2026-12-06", "method": "firearm"},
    ],
    "mule_deer": [
        {"start": "2026-10-01", "end": "2026-12-15", "method": "archery"},
        {"start": "2026-10-24", "end": "2026-11-04", "method": "firearm"},
    ],
    "elk": [
        {"start": "2026-09-02", "end": "2026-09-30", "method": "archery"},
        {"start": "2026-10-24", "end": "2026-11-01", "method": "firearm"},
    ],
    "turkey": [{"start": "2027-04-10", "end": "2027-05-10", "method": "shotgun"}],
    "dove": [{"start": "2026-09-01", "end": "2026-10-31", "method": "shotgun"}],
    "waterfowl": [{"start": "2026-11-14", "end": "2027-01-31", "method": "shotgun"}],
    "squirrel": [{"start": "2026-10-01", "end": "2027-02-28", "method": "shotgun"}],
    "quail": [{"start": "2026-11-08", "end": "2027-02-15", "method": "shotgun"}],
    "rabbit": [{"start": "2026-09-01", "end": "2027-03-15", "method": "shotgun"}],
    "feral_hog": [{"start": "2026-09-01", "end": "2027-08-31", "method": "archery"}],
}


def area_state(area: dict[str, Any]) -> str:
    return str(area.get("state") or "tx").strip().lower()


def areas_for_state(state: str) -> list[dict[str, Any]]:
    code = state.strip().lower()
    return [a for a in load_areas() if area_state(a) == code]


def _host_allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    suffixes = ALLOWED_LINK_SUFFIXES + EXTRA_LINK_SUFFIXES
    return any(host == suf.lstrip(".") or host.endswith(suf) for suf in suffixes)


def _safe_link_multi(url: str) -> str:
    url = (url or "").strip()
    if not url.lower().startswith("https://"):
        return ""
    return url if _host_allowed(url) else ""


def _clean_links_multi(raw: list[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in raw or []:
        url = _safe_link_multi(str(item.get("url") or ""))
        label = str(item.get("label") or "").strip()
        if url and label:
            out.append({"label": label, "url": url})
    return out


def _windows_for_entry(entry: dict[str, Any], method: str) -> list[dict[str, str]]:
    custom = entry.get("windows")
    if custom:
        wins = []
        for w in custom:
            if w.get("method") and w["method"] != method:
                continue
            wins.append({"start": w["start"], "end": w["end"]})
        if wins:
            return wins
    species = entry["species"]
    defaults = DEFAULT_WINDOWS.get(species, [{"start": "2026-09-01", "end": "2027-02-28"}])
    matched = [ {"start": d["start"], "end": d["end"]} for d in defaults if d.get("method", method) == method ]
    return matched or [{"start": defaults[0]["start"], "end": defaults[0]["end"]}]


def build_corps_for_state(
    state: str,
    *,
    county_index: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (units, opportunities, features) for Corps areas in ``state``."""
    code = state.strip().lower()
    if code == "tx":
        from county_seasons import load_counties

        idx = county_index if county_index is not None else {}
        if not idx:
            cache = ROOT / "cache" / "counties"
            if cache.exists():
                idx = load_counties(cache)
        return build_corps(idx)

    areas = areas_for_state(code)
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

        geom = _load_geometry(area)
        if geom is not None:
            try:
                c = geom.centroid
                lon, lat = c.x, c.y
            except Exception:
                pass

        species_entries = area.get("species", [])
        legal_game = area.get("legalGame") or [
            SPECIES.get(e["species"], e["species"]) for e in species_entries
        ]
        species_set = sorted({e["species"] for e in species_entries})
        methods_set = sorted(
            {m for e in species_entries for m in e.get("methods", []) if m in VALID_METHODS}
        )
        links = _clean_links_multi(area.get("links", []))
        map_pdf = _safe_link_multi(str(area.get("mapPdfUrl") or ""))

        unit = {
            "id": area_id,
            "unitIds": [area_id],
            "name": name,
            "counties": counties,
            "region": region,
            "acres": area.get("acres"),
            "type": CORPS_TYPE,
            "kind": "corps_lake",
            "source": CORPS_SOURCE,
            "state": code,
            "managingAgency": str(area.get("managingAgency") or "").strip(),
            "permitRequired": bool(area.get("permitRequired")),
            "permitInfo": str(area.get("permitInfo") or "").strip(),
            "permitCost": str(area.get("permitCost") or "").strip(),
            "means": str(area.get("means") or "").strip(),
            "legalGame": legal_game,
            "legalGameText": str(area.get("means") or "").strip(),
            "links": links,
            "mapPdfUrl": map_pdf,
            "pdfUrl": "",
            "aerialPdfUrl": "",
            "registration": "none",
            "legalGameTags": list(legal_game),
            "species": species_set,
            "methods": methods_set,
            "access": [CORPS_ACCESS],
            "complexes": [],
            "hasEpostcard": False,
            "hasRegularPermit": False,
            "epostcardUrl": "",
            "countySlugs": [c.lower().replace(" ", "-") for c in counties],
            "bookletPage": None,
            "bookletPdfPage": None,
            "bookletUrl": "",
            "lon": round(lon, 5) if lon is not None else None,
            "lat": round(lat, 5) if lat is not None else None,
        }
        if geom is not None:
            unit["boundaryNote"] = (
                "Map boundary is project land when a GeoJSON file is present; "
                "otherwise the unit is a point at the published coordinates."
            )
        units.append(unit)

        unit_methods: set[str] = set()
        for entry in species_entries:
            species = entry["species"]
            species_label = SPECIES.get(species, species.replace("_", " ").title())
            note = str(entry.get("notes") or "").strip()
            for method in entry.get("methods", []):
                if method not in VALID_METHODS:
                    continue
                for win in _windows_for_entry(entry, method):
                    opp_id += 1
                    opportunities.append(
                        {
                            "id": f"{code}-co{opp_id}",
                            "unitId": area_id,
                            "species": species,
                            "speciesLabel": species_label,
                            "methods": [method],
                            "access": CORPS_ACCESS,
                            "start": win["start"],
                            "end": win["end"],
                            "dateSource": "corps_curated",
                            "county": counties[0] if counties else "",
                            "notes": note,
                        }
                    )
                    unit_methods.add(method)
        unit["methods"] = sorted(unit_methods) or methods_set

        if geom is not None:
            geometry = mapping(geom)
        elif unit["lon"] is not None and unit["lat"] is not None:
            geometry = {"type": "Point", "coordinates": [unit["lon"], unit["lat"]]}
        else:
            continue
        props = {k: v for k, v in unit.items()}
        features.append(
            {"type": "Feature", "id": area_id, "properties": props, "geometry": geometry}
        )

    return units, opportunities, features


def ensure_tx_state_field() -> int:
    """Add state='tx' to any area missing a state field. Returns count updated."""
    path = CORPS_DIR / "areas.json"
    areas = json.loads(path.read_text())
    changed = 0
    for area in areas:
        if "state" not in area:
            area["state"] = "tx"
            changed += 1
    if changed:
        path.write_text(json.dumps(areas, indent=2) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", required=True, help="State code, e.g. la, ar, ok, nm, co, tx")
    parser.add_argument("--out", type=Path, help="Optional directory to write units/opps/geojson")
    args = parser.parse_args()
    ensure_tx_state_field()
    units, opps, feats = build_corps_for_state(args.state)
    print(f"corps {args.state}: {len(units)} units, {len(opps)} opportunities, {len(feats)} features")
    if args.out:
        write_json(args.out / "corps-units.json", units)
        write_json(args.out / "corps-opportunities.json", opps)
        write_json(args.out / "corps-units.geojson", {"type": "FeatureCollection", "features": feats})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
