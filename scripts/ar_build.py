#!/usr/bin/env python3
"""Build Arkansas publicLand package: WMAs, deer zones, opportunities, licenses."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from state_common import (  # noqa: E402
    CACHE,
    DATA,
    acres_from_props,
    counties_index,
    download_geojson,
    feature_collection,
    license_guide,
    load_census_counties,
    map_units_from_geojson,
    meta_shell,
    mirror_tree,
    regulation_guide,
    report_fetch,
    simplify_feature,
    slugify,
    title_case_name,
    write_json,
)

STATE = "ar"
WMA_URL = (
    "https://gisec2.agfc.com/arcgis/rest/services/GIS/AGFC_DATA/FeatureServer/11/query"
    "?where=1%3D1&outFields=*&f=geojson&outSR=4326&returnGeometry=true"
)
ZONE_URL = (
    "https://gisec2.agfc.com/arcgis/rest/services/GIS/AGFC_DATA/FeatureServer/12/query"
    "?where=1%3D1&outFields=*&f=geojson&outSR=4326&returnGeometry=true"
)
BUY_URL = "https://www.agfc.com/licenses/"
DEER_URL = "https://www.agfc.com/hunting/deer/deer-seasons-and-limits-by-zone/"
GUIDE_URL = "https://www.agfc.com/hunting/"


# Modern-gun end dates by zone group for 2026-27 (plus statewide Dec 26-28).
ZONE_MODERN = {
    "1": ("2026-11-14", "2026-12-06"),
    "2": ("2026-11-14", "2026-12-06"),
    "3": ("2026-11-14", "2026-12-06"),
    "6": ("2026-11-14", "2026-12-06"),
    "7": ("2026-11-14", "2026-12-06"),
    "8": ("2026-11-14", "2026-12-06"),
    "10": ("2026-11-14", "2026-12-06"),
    "11": ("2026-11-14", "2026-12-06"),
    "4": ("2026-11-14", "2026-11-22"),
    "5": ("2026-11-14", "2026-11-22"),
    "4A": ("2026-11-14", "2026-12-13"),
    "5A": ("2026-11-14", "2026-12-13"),
    "14": ("2026-11-14", "2026-12-13"),
    "15": ("2026-11-14", "2026-12-13"),
    "9": ("2026-11-14", "2026-12-20"),
    "12": ("2026-11-14", "2026-12-20"),
    "13": ("2026-11-14", "2026-12-20"),
    "16": ("2026-11-14", "2026-12-25"),
    "16A": ("2026-11-14", "2026-12-25"),
    "17": ("2026-11-14", "2026-12-25"),
}

ZONE_ALT = {
    # Oct 17-25 + Dec 12-14
    "group_a": {
        "zones": {"1", "2", "3", "6", "7", "8", "10", "11"},
        "windows": [("2026-10-17", "2026-10-25"), ("2026-12-12", "2026-12-14")],
    },
    # Oct 17-25 + Dec 19-21
    "group_b": {
        "zones": {"4A", "5A", "14", "15"},
        "windows": [("2026-10-17", "2026-10-25"), ("2026-12-19", "2026-12-21")],
    },
    # Oct 17-25 only
    "group_c": {
        "zones": {"9", "12", "13", "16", "16A", "17"},
        "windows": [("2026-10-17", "2026-10-25")],
    },
    # Closed
    "group_d": {"zones": {"4", "5"}, "windows": []},
}


def _unit_id(props: dict, idx: int) -> str:
    name = str(props.get("fname") or props.get("wma") or props.get("flabel") or f"wma-{idx}")
    return f"wma:{slugify(name)}"


def _unit_props(props: dict, uid: str) -> dict:
    name = title_case_name(str(props.get("fname") or props.get("wma") or props.get("flabel") or uid))
    counties = [c.strip() for c in str(props.get("county") or "").split(",") if c.strip()]
    return {
        "id": uid,
        "unitIds": [uid],
        "name": name,
        "kind": "wma",
        "type": "wma",
        "source": "agfc",
        "counties": counties,
        "region": str(props.get("wma_zone") or ""),
        "acres": acres_from_props(props, "acres", "ACRES"),
        "owner": props.get("owner") or "",
        "species": ["white_tailed_deer", "turkey", "dove", "squirrel", "waterfowl"],
        "methods": ["archery", "muzzleloader", "firearm", "shotgun"],
        "access": ["wma_permit", "lottery"],
    }


def build_licenses() -> dict:
    return license_guide(
        title="Arkansas hunting licenses, WMA permits, and fees",
        season_year="2026-27",
        intro=(
            "A hunting license is required to hunt in Arkansas. Many WMAs require additional "
            "deer/turkey permits drawn through AGFC. Confirm current fees before you buy."
        ),
        where_to_buy=[
            {
                "id": "internet",
                "title": "Online",
                "body": f"Buy licenses and apply for WMA permits at {BUY_URL}.",
            },
            {
                "id": "agent",
                "title": "License agent",
                "body": "AGFC license agents sell hunting licenses statewide.",
            },
            {
                "id": "lottery",
                "title": "WMA permit draw",
                "body": "WMA deer/turkey permit applications typically open June 1–July 1. Leftovers may be offered later.",
            },
            {
                "id": "otc",
                "title": "Over the counter",
                "body": "Private-land deer seasons do not need a WMA permit; public land often does.",
            },
            {
                "id": "corps",
                "title": "Corps of Engineers lakes",
                "body": "Corps project lands may allow public hunting under AGFC seasons with lake-specific restrictions.",
            },
        ],
        deadlines=[
            {
                "name": "WMA permit application",
                "date": "2026-07-01",
                "detail": "Application window typically June 1–July 1.",
            },
            {
                "name": "Early buck-only archery",
                "date": "2026-08-29",
                "detail": "Aug 29–31, 2026 statewide early buck archery.",
            },
        ],
        fees=[
            {"item": "Resident wildlife conservation license / hunting", "resident": "See AGFC", "nonresident": "See AGFC"},
            {"item": "Resident sportsman / combination", "resident": "See AGFC", "nonresident": "See AGFC"},
            {"item": "Nonresident annual hunting", "resident": "—", "nonresident": "See AGFC"},
            {"item": "WMA deer/turkey permit (drawn)", "resident": "See AGFC", "nonresident": "See AGFC"},
            {"item": "Lake / WMA conservation permit (if required)", "resident": "See AGFC", "nonresident": "See AGFC"},
        ],
        sources=[
            {"name": "AGFC licenses", "url": BUY_URL},
            {"name": "Deer seasons by zone", "url": DEER_URL},
            {"name": "AGFC hunting", "url": GUIDE_URL},
        ],
    )


def build_regulations() -> dict:
    return regulation_guide(
        title="Arkansas methods, deer zones, and WMA rules",
        methods=[
            {
                "id": "archery",
                "label": "Archery / crossbow",
                "summary": "Early buck-only Aug 29–31; general archery Sept 26–Feb 28 on private land and many public areas.",
            },
            {
                "id": "muzzleloader",
                "label": "Alternative firearms",
                "summary": "Formerly muzzleloader — Oct 17–25 plus December splits by zone; closed in zones 4 and 5.",
            },
            {
                "id": "firearm",
                "label": "Modern gun",
                "summary": "Opens Nov 14; end date depends on deer zone. Christmas holiday hunt Dec 26–28 statewide.",
            },
            {
                "id": "shotgun",
                "label": "Shotgun",
                "summary": "Turkey, dove, small game, and waterfowl as listed.",
            },
        ],
        prohibited=[
            "Hunting a WMA without the required WMA permit when one is listed for that season.",
            "Using dogs for deer where the zone or WMA prohibits dogs.",
            "Hunting outside zone or WMA dates.",
        ],
        unit_rules=[
            "Private-land deer zones and WMA/NWR zones are separate — each WMA is its own zone in the guidebook.",
            "Christmas holiday modern gun Dec 26–28 is statewide unless a WMA closes it.",
            "Youth modern gun hunts Nov 7–8 and Jan 2–3 — check WMA exceptions.",
        ],
        sources=[
            {"name": "Deer seasons by zone", "url": DEER_URL},
            {"name": "AGFC hunting", "url": GUIDE_URL},
        ],
    )


def _zone_code_from_props(props: dict) -> str:
    raw = str(
        props.get("ZONE")
        or props.get("Zone")
        or props.get("DEERZONE")
        or props.get("deer_zone")
        or props.get("flabel")
        or props.get("fname")
        or props.get("NAME")
        or props.get("Name")
        or ""
    ).strip()
    raw = raw.replace("Deer Zone", "Zone")
    raw = raw.replace("ZONE", "Zone")
    if raw.lower().startswith("zone"):
        raw = raw[4:].strip()
    return raw.strip()


def _latest_zone_features(zone_fc: dict) -> list[dict]:
    """AGFC layer stacks historical seasons — keep the newest year per zone label."""
    best_year = -1
    for feat in zone_fc.get("features", []):
        props = feat.get("properties") or {}
        try:
            year = int(str(props.get("season") or "0")[:4])
        except ValueError:
            year = 0
        if year > best_year:
            best_year = year
    chosen: dict[str, dict] = {}
    for feat in zone_fc.get("features", []):
        props = feat.get("properties") or {}
        try:
            year = int(str(props.get("season") or "0")[:4])
        except ValueError:
            year = 0
        if best_year > 0 and year != best_year:
            continue
        code = _zone_code_from_props(props)
        if not code:
            continue
        # Prefer official current labels; keep first polygon per code.
        if code not in chosen:
            chosen[code] = feat
    return list(chosen.values())


def build_zones(zone_fc: dict) -> tuple[list[dict], dict]:
    zones: list[dict] = []
    feats: list[dict] = []
    for feat in _latest_zone_features(zone_fc):
        props = feat.get("properties") or {}
        code = _zone_code_from_props(props)
        zid = f"zone:{code}"
        modern = ZONE_MODERN.get(code)
        if modern is None:
            # Historic labels like 4B/5B/1A — approximate with sibling zone or default group.
            base = "".join(ch for ch in code if ch.isdigit() or ch == "A")
            modern = ZONE_MODERN.get(base) or ZONE_MODERN.get(code.rstrip("AB")) or ("2026-11-14", "2026-12-06")
        alt_windows: list[tuple[str, str]] = []
        for group in ZONE_ALT.values():
            if code in group["zones"] or code.rstrip("B") in group["zones"]:
                alt_windows = group["windows"]
                break
        row = {
            "id": zid,
            "code": code,
            "name": f"Deer Zone {code}",
            "modernGunStart": modern[0],
            "modernGunEnd": modern[1],
            "alternativeFirearms": [{"start": a, "end": b} for a, b in alt_windows],
            "archeryStart": "2026-09-26",
            "archeryEnd": "2027-02-28",
            "earlyBuckArcheryStart": "2026-08-29",
            "earlyBuckArcheryEnd": "2026-08-31",
            "christmasGunStart": "2026-12-26",
            "christmasGunEnd": "2026-12-28",
            "gisSeasonYear": props.get("season"),
        }
        simplified = simplify_feature(feat, row, feature_id=zid)
        if not simplified:
            continue
        zones.append(row)
        feats.append(simplified)
    zones.sort(key=lambda z: (len(z["code"]), z["code"]))
    return zones, feature_collection(feats)


def build_opportunities(units: list[dict], zones: list[dict]) -> list[dict]:
    opps: list[dict] = []
    oid = 0
    # Zone-level deer opportunities (place rows for In Season differences).
    for zone in zones:
        for species, label, methods, start, end, access, notes in [
            ("white_tailed_deer", "White-tailed deer", ["archery"], zone["earlyBuckArcheryStart"], zone["earlyBuckArcheryEnd"], "general_otc", "Early buck-only archery"),
            ("white_tailed_deer", "White-tailed deer", ["archery"], zone["archeryStart"], zone["archeryEnd"], "general_otc", "Archery"),
            ("white_tailed_deer", "White-tailed deer", ["firearm"], zone["modernGunStart"], zone["modernGunEnd"], "general_otc", "Modern gun"),
            ("white_tailed_deer", "White-tailed deer", ["firearm"], zone["christmasGunStart"], zone["christmasGunEnd"], "general_otc", "Christmas holiday modern gun"),
        ]:
            oid += 1
            opps.append(
                {
                    "id": f"arz{oid}",
                    "unitId": zone["id"],
                    "species": species,
                    "speciesLabel": label,
                    "methods": methods,
                    "access": access,
                    "start": start,
                    "end": end,
                    "dateSource": "agfc_deer_zone",
                    "county": "",
                    "notes": notes,
                    "placeType": "deer_zone",
                }
            )
        for win in zone.get("alternativeFirearms") or []:
            oid += 1
            opps.append(
                {
                    "id": f"arz{oid}",
                    "unitId": zone["id"],
                    "species": "white_tailed_deer",
                    "speciesLabel": "White-tailed deer",
                    "methods": ["muzzleloader"],
                    "access": "general_otc",
                    "start": win["start"],
                    "end": win["end"],
                    "dateSource": "agfc_deer_zone",
                    "county": "",
                    "notes": "Alternative firearms",
                    "placeType": "deer_zone",
                }
            )

    # WMA baseline opportunities
    for unit in units:
        if unit.get("source") == "usace":
            continue
        for species, label, methods, start, end, access, notes in [
            ("white_tailed_deer", "White-tailed deer", ["archery"], "2026-09-26", "2027-02-28", "wma_permit", "WMA archery — confirm WMA zone schedule"),
            ("white_tailed_deer", "White-tailed deer", ["firearm"], "2026-11-14", "2026-12-06", "lottery", "Many WMAs require drawn deer permits"),
            ("turkey", "Wild turkey", ["shotgun"], "2027-04-10", "2027-05-05", "lottery", "Spring turkey — WMA permit often required"),
            ("dove", "Dove", ["shotgun"], "2026-09-05", "2026-10-25", "wma_permit", "Dove — confirm federal framework"),
            ("squirrel", "Squirrel", ["any_legal"], "2026-09-12", "2027-02-28", "wma_permit", "Squirrel"),
        ]:
            oid += 1
            opps.append(
                {
                    "id": f"ar{oid}",
                    "unitId": unit["id"],
                    "species": species,
                    "speciesLabel": label,
                    "methods": methods,
                    "access": access,
                    "start": start,
                    "end": end,
                    "dateSource": "agfc_wma_baseline",
                    "county": (unit.get("counties") or [""])[0],
                    "notes": notes,
                }
            )
    return opps


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    cache = CACHE / STATE
    failures: list[str] = []

    try:
        raw = download_geojson(WMA_URL, cache / "wma.raw.geojson", force=args.force)
        report_fetch("AR WMAs", True, f"{len(raw.get('features', []))} features")
    except Exception as exc:
        report_fetch("AR WMAs", False, str(exc))
        failures.append(f"AR WMAs: {exc}")
        raw = {"type": "FeatureCollection", "features": []}

    units, geo = map_units_from_geojson(raw, id_fn=_unit_id, props_fn=_unit_props)
    seen: set[str] = set()
    dedup_u, dedup_f = [], []
    for u, f in zip(units, geo["features"]):
        if u["id"] in seen:
            continue
        seen.add(u["id"])
        dedup_u.append(u)
        dedup_f.append(f)
    units, geo = dedup_u, {"type": "FeatureCollection", "features": dedup_f}

    try:
        zone_raw = download_geojson(ZONE_URL, cache / "deer-zones.raw.geojson", force=args.force)
        report_fetch("AR deer zones", True, f"{len(zone_raw.get('features', []))} features")
    except Exception as exc:
        report_fetch("AR deer zones", False, str(exc))
        failures.append(f"AR zones: {exc}")
        zone_raw = {"type": "FeatureCollection", "features": []}

    zones, zones_geo = build_zones(zone_raw)
    # If GIS zones lacked codes, synthesize from ZONE_MODERN
    if not zones:
        zones = []
        for code, modern in ZONE_MODERN.items():
            alt_windows = []
            for group in ZONE_ALT.values():
                if code in group["zones"]:
                    alt_windows = group["windows"]
                    break
            zones.append(
                {
                    "id": f"zone:{code}",
                    "code": code,
                    "name": f"Deer Zone {code}",
                    "modernGunStart": modern[0],
                    "modernGunEnd": modern[1],
                    "alternativeFirearms": [{"start": a, "end": b} for a, b in alt_windows],
                    "archeryStart": "2026-09-26",
                    "archeryEnd": "2027-02-28",
                    "earlyBuckArcheryStart": "2026-08-29",
                    "earlyBuckArcheryEnd": "2026-08-31",
                    "christmasGunStart": "2026-12-26",
                    "christmasGunEnd": "2026-12-28",
                }
            )
        zones_geo = {"type": "FeatureCollection", "features": []}

    try:
        counties = load_census_counties(STATE, force=args.force)
        report_fetch("AR counties", True, f"{len(counties['features'])} counties")
    except Exception as exc:
        failures.append(f"AR counties: {exc}")
        counties = {"type": "FeatureCollection", "features": []}

    try:
        from corps_multi import build_corps_for_state

        corps_units, corps_opps, corps_feats = build_corps_for_state("ar")
        units = units + corps_units
        geo["features"] = geo["features"] + corps_feats
        report_fetch("AR Corps merge", True, f"{len(corps_units)} lakes")
    except Exception as exc:
        report_fetch("AR Corps merge", False, str(exc))
        corps_opps = []
        failures.append(f"AR Corps: {exc}")

    opps = build_opportunities(units, zones) + corps_opps

    meta = meta_shell(
        season_year="2026-27",
        disclaimer=(
            "Unofficial planning aid compiled from Arkansas Game and Fish Commission public GIS "
            "and the 2026–27 deer zone seasons. WMA schedules are individual zones — confirm the "
            "guidebook before you hunt."
        ),
        sources=[
            {"name": "AGFC WMA Boundaries", "url": WMA_URL.split("/query")[0]},
            {"name": "AGFC Deer Zones", "url": ZONE_URL.split("/query")[0]},
            {"name": "Deer seasons by zone", "url": DEER_URL},
            {"name": "AGFC licenses", "url": BUY_URL},
        ],
        species=[
            {"id": "white_tailed_deer", "label": "White-tailed deer"},
            {"id": "turkey", "label": "Wild turkey"},
            {"id": "dove", "label": "Dove"},
            {"id": "squirrel", "label": "Squirrel"},
            {"id": "waterfowl", "label": "Waterfowl"},
        ],
        methods=[
            {"id": "archery", "label": "Archery"},
            {"id": "muzzleloader", "label": "Alternative firearms"},
            {"id": "firearm", "label": "Modern gun"},
            {"id": "shotgun", "label": "Shotgun"},
            {"id": "any_legal", "label": "Any legal means"},
        ],
        access=[
            {"id": "general_otc", "label": "Private land / no WMA permit"},
            {"id": "wma_permit", "label": "WMA open with permit"},
            {"id": "lottery", "label": "WMA permit draw"},
            {"id": "corps_permit", "label": "Corps / USACE permit"},
        ],
        counts={
            "unitCount": len(units),
            "opportunityCount": len(opps),
            "zoneCount": len(zones),
            "countyCount": len(counties["features"]),
            "polygonCount": len(geo["features"]),
        },
        profile="publicLand",
        agency="AGFC",
    )

    out = DATA / STATE
    write_json(out / "units.json", units)
    write_json(out / "units.geojson", geo)
    write_json(out / "opportunities.json", opps)
    write_json(out / "zones.json", zones)
    write_json(out / "zones.geojson", zones_geo)
    write_json(out / "licenses.json", build_licenses())
    write_json(out / "regulations.json", build_regulations())
    write_json(out / "meta.json", meta)
    write_json(out / "counties.geojson", counties)
    write_json(out / "counties.json", counties_index(counties))
    (out / "SOURCES.md").write_text(
        "# Arkansas sources\n\n"
        f"- WMAs: {WMA_URL}\n"
        f"- Deer zones: {ZONE_URL}\n"
        f"- Seasons: {DEER_URL}\n"
        f"- Buy: {BUY_URL}\n",
        encoding="utf-8",
    )
    mirror_tree(STATE)
    print(f"ar: {len(units)} units, {len(zones)} zones, {len(opps)} opportunities")
    if failures and not units:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
