#!/usr/bin/env python3
"""Build New Mexico unitGrid package: GMUs, draw/OTC hunts, licenses, regs."""

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
    license_guide,
    load_census_counties,
    map_units_from_geojson,
    meta_shell,
    mirror_tree,
    regulation_guide,
    report_fetch,
    title_case_name,
    write_json,
)

STATE = "nm"
GMU_URL = (
    "https://mapservice.nmstatelands.org/arcgis/rest/services/Public/Hunting_/"
    "MapServer/3/query?where=1%3D1&outFields=*&f=geojson&outSR=4326&returnGeometry=true"
)
BUY_URL = "https://onlinesales.wildlife.dgf.nm.gov/"
RULES_URL = "https://wildlife.dgf.nm.gov/hunting/rules-info/"
DRAW_URL = "https://wildlife.dgf.nm.gov/hunting/drawing/"


def _gmu_id(props: dict, idx: int) -> str:
    code = str(props.get("GMU") or "").strip() or str(idx + 1)
    return f"gmu:{code}"


def _gmu_props(props: dict, uid: str) -> dict:
    code = uid.split(":", 1)[1]
    return {
        "id": uid,
        "kind": "gmu",
        "code": code,
        "name": f"GMU {code}",
        "region": _region_for(code),
        "acres": acres_from_props(props, "ACRES", "Acres", "acres"),
        "bearZone": props.get("BEAR_ZONE"),
        "cougarZone": props.get("COUGAR_ZON"),
    }


def _region_for(code: str) -> str:
    try:
        n = int("".join(ch for ch in code if ch.isdigit()) or "0")
    except ValueError:
        return "Other"
    if n <= 15:
        return "Northwest"
    if n <= 30:
        return "Southwest"
    if n <= 45:
        return "Northeast"
    return "Southeast"


def build_licenses() -> dict:
    return license_guide(
        title="New Mexico hunting licenses, draws, and fees",
        season_year="2026-27",
        intro=(
            "Public-land deer and elk licenses are issued through the NMDGF big-game draw. "
            "A Game-Hunting License is required before most tags. Fees below are the 2026–27 "
            "amounts published by NMDGF. Confirm before you apply or pay."
        ),
        where_to_buy=[
            {
                "id": "internet",
                "title": "Online",
                "body": f"Apply for the draw and buy OTC licenses at {BUY_URL}.",
            },
            {
                "id": "agent",
                "title": "License vendor",
                "body": "License vendors sell OTC licenses and can help with draw applications. A vendor fee applies.",
            },
            {
                "id": "draw",
                "title": "Big-game draw",
                "body": (
                    "Deer, elk, pronghorn, and other big-game public licenses are a random draw "
                    "(no preference points). Application deadline for 2026 was March 18; results April 22."
                ),
            },
            {
                "id": "otc",
                "title": "Over the counter",
                "body": "Game-Hunting License, turkey, and private-land-only deer/pronghorn licenses sell OTC after the draw window.",
            },
            {
                "id": "mail",
                "title": "Phone / mail",
                "body": "NMDGF Licensing can take phone applications. Confirm current phone sales at wildlife.dgf.nm.gov.",
            },
        ],
        deadlines=[
            {
                "name": "Big-game draw application",
                "date": "2026-03-18",
                "detail": "Results published about April 22, 2026.",
            },
            {
                "name": "License year",
                "date": "2027-03-31",
                "detail": "2026–27 licenses generally run April 1, 2026 through March 31, 2027.",
            },
        ],
        fees=[
            {"item": "Game-Hunting License", "resident": "$25", "nonresident": "$90"},
            {"item": "Game-Hunting & Fishing License", "resident": "$42", "nonresident": "Not issued"},
            {"item": "Junior Game-Hunting License", "resident": "$10", "nonresident": "$20"},
            {"item": "Deer license (standard draw)", "resident": "$60", "nonresident": "$398"},
            {"item": "Deer license (quality / high-demand)", "resident": "$60", "nonresident": "$623"},
            {"item": "Elk mature bull / either-sex (standard)", "resident": "$100", "nonresident": "$773"},
            {"item": "Elk antlerless (resident)", "resident": "$70", "nonresident": "Not issued"},
            {"item": "Pronghorn license", "resident": "$70", "nonresident": "$423"},
            {"item": "Draw application fee (included in draw license)", "resident": "$7", "nonresident": "$13"},
        ],
        sources=[
            {"name": "NMDGF online sales", "url": BUY_URL},
            {"name": "2026–27 Hunting Rules & Info", "url": RULES_URL},
            {"name": "Draw information", "url": DRAW_URL},
        ],
        hunt_series=[
            {"id": "deer", "label": "Deer draw", "points": False},
            {"id": "elk", "label": "Elk draw", "points": False},
            {"id": "pronghorn", "label": "Pronghorn draw", "points": False},
            {"id": "turkey", "label": "Turkey", "points": False},
        ],
        preference_points=[
            "New Mexico does not use preference points for big-game draws. Each application is random.",
        ],
        residency_rules=[
            "State law allocates most draw licenses about 84% to residents, 10% to applicants with a New Mexico–registered outfitter, and 6% to nonresidents without an outfitter.",
            "Antlerless (cow) elk draw licenses are residents only; nonresidents cannot apply for those codes.",
            "Hunts held exclusively on State Game Commission WMAs are residents only. Nonresidents may still apply for hunts that run concurrently on both WMA and other public land.",
            "Nonresidents may buy private-land elk licenses and may apply for either-sex or mature-bull public elk draws (subject to the 6%/10% quotas).",
            "The Game-Hunting & Fishing combo and antlerless elk license are not issued to nonresidents (see fee table).",
        ],
    )


def build_regulations() -> dict:
    return regulation_guide(
        title="New Mexico methods, restrictions, and GMU rules",
        methods=[
            {
                "id": "archery",
                "label": "Bow",
                "summary": "Longbow, recurve, or compound bow meeting NMDGF draw-weight and broadhead rules. Crossbows are a separate sporting-arm class where listed.",
            },
            {
                "id": "muzzleloader",
                "label": "Muzzleloader",
                "summary": "Muzzleloading rifles meeting caliber and ignition rules for the hunt code. Scopes and sabots follow the current booklet.",
            },
            {
                "id": "firearm",
                "label": "Any legal firearm / rifle",
                "summary": "Centerfire rifles and other legal firearms listed for the hunt code. Magazine and caliber restrictions apply.",
            },
            {
                "id": "any_legal",
                "label": "Any legal sporting arm",
                "summary": "Any sporting arm legal for that species under NMDGF rules for the hunt code.",
            },
            {
                "id": "shotgun",
                "label": "Shotgun",
                "summary": "Shotguns for turkey, dove, and small game as listed; non-toxic shot where required for waterfowl.",
            },
        ],
        prohibited=[
            "Hunting without the license and carcass tag (or e-tag) required for that species.",
            "Hunting public land with a private-land-only license.",
            "Using bait for big game where prohibited in the current rules.",
            "Shooting from or across a public road.",
            "Hunting in closed areas, national parks, or tribal land without tribal authorization.",
        ],
        unit_rules=[
            "A hunt code is legal only in the GMUs printed for that code in the Hunting Rules & Info.",
            "WMA-only hunts are restricted to the named wildlife management area inside the GMU.",
            "Weapon type (bow, muzzleloader, any legal firearm) is part of the hunt code — do not assume any-weapon.",
            "Bag limits and antler restrictions are per hunt code; one deer or elk license per hunter per year in most cases.",
        ],
        sources=[
            {"name": "2026–27 Hunting Rules & Info", "url": RULES_URL},
            {"name": "NMDGF hunting", "url": "https://wildlife.dgf.nm.gov/hunting/"},
        ],
    )


def build_hunts(unit_ids: list[str]) -> list[dict]:
    by_region: dict[str, list[str]] = {}
    for uid in unit_ids:
        code = uid.split(":", 1)[1]
        by_region.setdefault(_region_for(code), []).append(uid)

    nw = by_region.get("Northwest", unit_ids[:15])
    sw = by_region.get("Southwest", unit_ids[15:30] if len(unit_ids) > 30 else unit_ids)
    ne = by_region.get("Northeast", unit_ids)
    se = by_region.get("Southeast", unit_ids)

    hunts: list[dict] = [
        {
            "id": "nm-deer-bow-nw",
            "huntNumber": "DER-2-xxx",
            "name": "Deer bow — Northwest GMUs",
            "species": "deer",
            "speciesLabel": "Deer",
            "series": "deer",
            "methods": ["archery"],
            "access": "controlled_draw",
            "bagLimit": "One fork-antlered deer per license",
            "start": "2026-09-01",
            "end": "2026-09-24",
            "tag": "Deer draw license",
            "tagSaleDeadline": None,
            "applicationDeadline": "2026-03-18",
            "scope": "region",
            "unitIds": nw,
            "restrictions": [],
            "notes": "Representative bow window for many Northwest GMUs. Confirm the exact hunt code in the NMDGF booklet.",
        },
        {
            "id": "nm-deer-bow-sw",
            "huntNumber": "DER-2-xxx",
            "name": "Deer bow — Southwest GMUs",
            "species": "deer",
            "speciesLabel": "Deer",
            "series": "deer",
            "methods": ["archery"],
            "access": "controlled_draw",
            "bagLimit": "One fork-antlered deer per license",
            "start": "2026-09-01",
            "end": "2026-09-24",
            "tag": "Deer draw license",
            "tagSaleDeadline": None,
            "applicationDeadline": "2026-03-18",
            "scope": "region",
            "unitIds": sw,
            "restrictions": [],
            "notes": "Southwest bow deer; Coues hunts in some GMUs use different late windows.",
        },
        {
            "id": "nm-deer-muzzle-nw",
            "huntNumber": "DER-3-xxx",
            "name": "Deer muzzleloader — Northwest",
            "species": "deer",
            "speciesLabel": "Deer",
            "series": "deer",
            "methods": ["muzzleloader"],
            "access": "controlled_draw",
            "bagLimit": "One fork-antlered deer per license",
            "start": "2026-09-27",
            "end": "2026-10-03",
            "tag": "Deer draw license",
            "tagSaleDeadline": None,
            "applicationDeadline": "2026-03-18",
            "scope": "region",
            "unitIds": nw,
            "restrictions": [],
            "notes": "Typical early muzzleloader window; some GMUs use late October dates instead.",
        },
        {
            "id": "nm-deer-rifle-ne",
            "huntNumber": "DER-1-xxx",
            "name": "Deer rifle — Northeast GMUs",
            "species": "deer",
            "speciesLabel": "Deer",
            "series": "deer",
            "methods": ["firearm"],
            "access": "controlled_draw",
            "bagLimit": "One fork-antlered deer per license",
            "start": "2026-10-31",
            "end": "2026-11-04",
            "tag": "Deer draw license",
            "tagSaleDeadline": None,
            "applicationDeadline": "2026-03-18",
            "scope": "region",
            "unitIds": ne,
            "restrictions": [],
            "notes": "Five-day rifle windows vary by GMU; this row groups Northeast units.",
        },
        {
            "id": "nm-deer-rifle-se",
            "huntNumber": "DER-1-xxx",
            "name": "Deer rifle — Southeast GMUs",
            "species": "deer",
            "speciesLabel": "Deer",
            "series": "deer",
            "methods": ["firearm"],
            "access": "controlled_draw",
            "bagLimit": "One fork-antlered deer per license",
            "start": "2026-11-07",
            "end": "2026-11-11",
            "tag": "Deer draw license",
            "tagSaleDeadline": None,
            "applicationDeadline": "2026-03-18",
            "scope": "region",
            "unitIds": se,
            "restrictions": [],
            "notes": "Southeast rifle grouping; confirm hunt code dates.",
        },
        {
            "id": "nm-elk-bow-early",
            "huntNumber": "ELK-2-xxx",
            "name": "Elk archery — early either-sex",
            "species": "elk",
            "speciesLabel": "Elk",
            "series": "elk",
            "methods": ["archery"],
            "access": "controlled_draw",
            "bagLimit": "One elk per license (either-sex where listed)",
            "start": "2026-09-01",
            "end": "2026-09-14",
            "tag": "Elk draw license",
            "tagSaleDeadline": None,
            "applicationDeadline": "2026-03-18",
            "scope": "multi_gmu",
            "unitIds": [u for u in unit_ids if _region_for(u.split(":", 1)[1]) in {"Northwest", "Southwest"}],
            "restrictions": [],
            "notes": "Early September bow either-sex window used in many mountain GMUs.",
        },
        {
            "id": "nm-elk-bow-late",
            "huntNumber": "ELK-2-xxx",
            "name": "Elk archery — late either-sex",
            "species": "elk",
            "speciesLabel": "Elk",
            "series": "elk",
            "methods": ["archery"],
            "access": "controlled_draw",
            "bagLimit": "One elk per license (either-sex where listed)",
            "start": "2026-09-15",
            "end": "2026-09-24",
            "tag": "Elk draw license",
            "tagSaleDeadline": None,
            "applicationDeadline": "2026-03-18",
            "scope": "multi_gmu",
            "unitIds": [u for u in unit_ids if _region_for(u.split(":", 1)[1]) in {"Northwest", "Southwest"}],
            "restrictions": [],
            "notes": "Second September bow window.",
        },
        {
            "id": "nm-elk-rifle-bull",
            "huntNumber": "ELK-1-xxx",
            "name": "Elk rifle — mature bull",
            "species": "elk",
            "speciesLabel": "Elk",
            "series": "elk",
            "methods": ["firearm"],
            "access": "controlled_draw",
            "bagLimit": "One mature bull",
            "start": "2026-10-17",
            "end": "2026-10-21",
            "tag": "Elk draw license (MB)",
            "tagSaleDeadline": None,
            "applicationDeadline": "2026-03-18",
            "scope": "multi_gmu",
            "unitIds": unit_ids,
            "restrictions": [],
            "notes": "Representative five-day mature-bull rifle window; codes vary by GMU.",
        },
        {
            "id": "nm-turkey-spring",
            "huntNumber": None,
            "name": "Spring turkey",
            "species": "turkey",
            "speciesLabel": "Wild turkey",
            "series": "turkey",
            "methods": ["shotgun", "archery"],
            "access": "general_otc",
            "bagLimit": "Per turkey license / permit",
            "start": "2027-04-15",
            "end": "2027-05-15",
            "tag": "Turkey permit + Game-Hunting License",
            "tagSaleDeadline": None,
            "applicationDeadline": None,
            "scope": "statewide",
            "unitIds": unit_ids,
            "restrictions": [],
            "notes": "Spring turkey timing follows the current NMDGF turkey proclamation; confirm before hunting.",
        },
        {
            "id": "nm-dove-fall",
            "huntNumber": None,
            "name": "Mourning dove — fall",
            "species": "dove",
            "speciesLabel": "Mourning dove",
            "series": "migratory",
            "methods": ["shotgun"],
            "access": "general_otc",
            "bagLimit": "Federal/state daily bag",
            "start": "2026-09-01",
            "end": "2026-11-05",
            "tag": "Game-Hunting License + HIP",
            "tagSaleDeadline": None,
            "applicationDeadline": None,
            "scope": "statewide",
            "unitIds": unit_ids,
            "restrictions": [],
            "notes": "Migratory bird seasons follow the federal framework; confirm the current dove split.",
        },
    ]
    return hunts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    cache = CACHE / STATE
    failures: list[str] = []

    try:
        raw = download_geojson(GMU_URL, cache / "gmu.raw.geojson", force=args.force)
        report_fetch("NM GMUs", True, f"{len(raw.get('features', []))} features")
    except Exception as exc:
        failures.append(f"NM GMUs: {exc}")
        report_fetch("NM GMUs", False, str(exc))
        raw = {"type": "FeatureCollection", "features": []}

    units, primary = map_units_from_geojson(raw, id_fn=_gmu_id, props_fn=_gmu_props)
    # Deduplicate by id (some services return multipart rows).
    seen: set[str] = set()
    dedup_units = []
    dedup_feats = []
    for unit, feat in zip(units, primary["features"]):
        if unit["id"] in seen:
            continue
        seen.add(unit["id"])
        dedup_units.append(unit)
        dedup_feats.append(feat)
    units = dedup_units
    primary = {"type": "FeatureCollection", "features": dedup_feats}

    try:
        counties = load_census_counties(STATE, force=args.force)
        report_fetch("NM counties", True, f"{len(counties['features'])} counties")
    except Exception as exc:
        failures.append(f"NM counties: {exc}")
        report_fetch("NM counties", False, str(exc))
        counties = {"type": "FeatureCollection", "features": []}

    hunts = build_hunts([u["id"] for u in units]) if units else []
    try:
        from corps_multi import build_corps_for_state

        _cu, _co, public_feats = build_corps_for_state("nm")
        public_land = {"type": "FeatureCollection", "features": public_feats}
        report_fetch("NM Corps public land", True, f"{len(public_feats)} features")
    except Exception as exc:
        public_land = {"type": "FeatureCollection", "features": []}
        report_fetch("NM Corps public land", False, str(exc))
        failures.append(f"NM Corps: {exc}")

    licenses = build_licenses()
    regulations = build_regulations()
    meta = meta_shell(
        season_year="2026-27",
        disclaimer=(
            "Unofficial planning aid compiled from New Mexico Department of Game and Fish public maps "
            "and the 2026–27 Hunting Rules & Info. Hunt codes, dates, quotas, and boundaries change. "
            "Confirm every hunt with NMDGF before you apply or hunt."
        ),
        sources=[
            {"name": "NM GMU polygons (NM State Lands MapServer)", "url": GMU_URL.split("/query")[0]},
            {"name": "2026–27 Hunting Rules & Info", "url": RULES_URL},
            {"name": "NMDGF online sales", "url": BUY_URL},
            {"name": "Census county outlines", "url": "https://www.census.gov/geographies/mapping-files.html"},
        ],
        species=[
            {"id": "deer", "label": "Deer"},
            {"id": "elk", "label": "Elk"},
            {"id": "turkey", "label": "Wild turkey"},
            {"id": "dove", "label": "Mourning dove"},
            {"id": "pronghorn", "label": "Pronghorn"},
        ],
        methods=[
            {"id": "archery", "label": "Bow"},
            {"id": "muzzleloader", "label": "Muzzleloader"},
            {"id": "firearm", "label": "Firearm / rifle"},
            {"id": "any_legal", "label": "Any legal sporting arm"},
            {"id": "shotgun", "label": "Shotgun"},
        ],
        access=[
            {"id": "controlled_draw", "label": "Draw"},
            {"id": "general_otc", "label": "Over the counter"},
            {"id": "corps_permit", "label": "Corps / USACE permit"},
        ],
        counts={
            "unitCount": len(units),
            "huntCount": len(hunts),
            "countyCount": len(counties["features"]),
            "polygonCount": len(primary["features"]),
            "publicLandCount": len(public_land["features"]),
        },
        profile="unitGrid",
        agency="NMDGF",
    )

    out = DATA / STATE
    write_json(out / "units.json", units)
    write_json(out / "primary.geojson", primary)
    write_json(out / "units.geojson", primary)
    write_json(out / "hunts.json", hunts)
    write_json(out / "licenses.json", licenses)
    write_json(out / "regulations.json", regulations)
    write_json(out / "meta.json", meta)
    write_json(out / "counties.geojson", counties)
    write_json(out / "counties.json", counties_index(counties))
    write_json(out / "public-land.geojson", public_land)
    (out / "SOURCES.md").write_text(
        "# New Mexico sources\n\n"
        f"- GMUs: {GMU_URL}\n"
        f"- Rules: {RULES_URL}\n"
        f"- Buy: {BUY_URL}\n"
        "- Counties: Census / Plotly county GeoJSON\n",
        encoding="utf-8",
    )
    mirror_tree(STATE)
    print(f"nm: {len(units)} GMUs, {len(hunts)} hunts, {len(counties['features'])} counties")
    if failures:
        print("failures:", "; ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
