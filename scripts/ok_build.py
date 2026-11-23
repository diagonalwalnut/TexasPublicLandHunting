#!/usr/bin/env python3
"""Build Oklahoma publicLand package: WMAs, opportunities, licenses, regs."""

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
    slugify,
    title_case_name,
    write_json,
)

STATE = "ok"
WMA_URL = (
    "https://services1.arcgis.com/jRf8jjFwxedITdFe/arcgis/rest/services/"
    "Public_WMA_Boundaries/FeatureServer/1/query?where=1%3D1&outFields=*&f=geojson"
    "&outSR=4326&returnGeometry=true"
)
BUY_URL = "https://gooutdoorsoklahoma.com/"
HUNT_URL = "https://www.wildlifedepartment.com/hunting"
CTRL_URL = "https://www.wildlifedepartment.com/hunting/controlledhunts"


def _unit_id(props: dict, idx: int) -> str:
    name = str(props.get("WMANAME") or props.get("SHORTNAME") or f"wma-{idx}")
    return f"wma:{slugify(name)}"


def _unit_props(props: dict, uid: str) -> dict:
    name = title_case_name(str(props.get("WMANAME") or props.get("SHORTNAME") or uid))
    return {
        "id": uid,
        "unitIds": [uid],
        "name": name,
        "kind": "wma",
        "type": str(props.get("WMATYPE") or "WMA").lower(),
        "source": "odwc",
        "counties": [],
        "region": str(props.get("REGION") or ""),
        "acres": acres_from_props(props, "ACRES", "Acres", "acres"),
        "ownership": props.get("OWNERSHIP") or "",
        "species": ["white_tailed_deer", "turkey", "dove", "quail", "waterfowl"],
        "methods": ["archery", "muzzleloader", "firearm", "shotgun"],
        "access": ["wma_permit", "controlled_draw"],
    }


def build_licenses() -> dict:
    return license_guide(
        title="Oklahoma hunting licenses and controlled hunts",
        season_year="2026-27",
        intro=(
            "A hunting license is required to hunt in Oklahoma. Controlled hunts (deer, elk, "
            "antelope, turkey) are a separate application with preference points. Confirm fees "
            "at Go Outdoors Oklahoma before you buy."
        ),
        where_to_buy=[
            {
                "id": "internet",
                "title": "Go Outdoors Oklahoma",
                "body": f"Buy licenses and apply for controlled hunts at {BUY_URL}.",
            },
            {
                "id": "agent",
                "title": "License vendor",
                "body": "Authorized vendors sell hunting licenses statewide.",
            },
            {
                "id": "draw",
                "title": "Controlled hunt draw",
                "body": "Limited public hunts on WMAs and some Corps lands use the controlled-hunt application and preference points.",
            },
            {
                "id": "otc",
                "title": "Over the counter / open WMA",
                "body": "Many WMA seasons are open under statewide seasons with area-specific restrictions — no draw required.",
            },
            {
                "id": "corps",
                "title": "Corps of Engineers lakes",
                "body": "Tulsa District lakes open large acreages to public hunting under ODWC seasons; some hunts are controlled.",
            },
        ],
        deadlines=[
            {
                "name": "Controlled hunt application",
                "date": None,
                "detail": "Windows vary by species — check ODWC controlled hunts each year.",
            },
            {
                "name": "Archery deer (typical)",
                "date": "2026-10-01",
                "detail": "Statewide archery deer often opens Oct 1 — confirm the current regs.",
            },
        ],
        fees=[
            {"item": "Resident hunting license", "resident": "See Go Outdoors OK", "nonresident": "See Go Outdoors OK"},
            {"item": "Resident combination hunting/fishing", "resident": "See Go Outdoors OK", "nonresident": "—"},
            {"item": "Nonresident hunting license", "resident": "—", "nonresident": "See Go Outdoors OK"},
            {"item": "Deer gun license / tags", "resident": "See Go Outdoors OK", "nonresident": "See Go Outdoors OK"},
            {"item": "Controlled hunt application", "resident": "See Go Outdoors OK", "nonresident": "See Go Outdoors OK"},
        ],
        sources=[
            {"name": "Go Outdoors Oklahoma", "url": BUY_URL},
            {"name": "ODWC hunting", "url": HUNT_URL},
            {"name": "Controlled hunts", "url": CTRL_URL},
        ],
        preference_points=[
            "Oklahoma controlled hunts use preference points for many deer, elk, antelope, and turkey hunts.",
            "Points are tracked in your Go Outdoors Oklahoma account.",
        ],
    )


def build_regulations() -> dict:
    return regulation_guide(
        title="Oklahoma methods, WMA rules, and restrictions",
        methods=[
            {
                "id": "archery",
                "label": "Archery",
                "summary": "Archery deer season is typically statewide with WMA-specific closures or antlerless rules.",
            },
            {
                "id": "muzzleloader",
                "label": "Muzzleloader",
                "summary": "Primitive firearms deer season dates follow the current ODWC regs.",
            },
            {
                "id": "firearm",
                "label": "Gun / rifle",
                "summary": "Deer gun season is typically late November; some areas are controlled hunts only.",
            },
            {
                "id": "shotgun",
                "label": "Shotgun",
                "summary": "Turkey, dove, quail, and waterfowl; non-toxic shot for waterfowl.",
            },
        ],
        prohibited=[
            "Hunting a controlled hunt without the drawn permit.",
            "Hunting in refuge or closed portions of a WMA.",
            "Violating area-specific firearm or vehicle restrictions posted for that WMA.",
        ],
        unit_rules=[
            "Each WMA may have special regulations that differ from the statewide season.",
            "Some Corps lakes are open under ODWC seasons; others host controlled hunts.",
            "Preference points apply only to controlled-hunt applications.",
        ],
        sources=[
            {"name": "ODWC hunting", "url": HUNT_URL},
            {"name": "Controlled hunts", "url": CTRL_URL},
        ],
    )


def build_opportunities(units: list[dict]) -> list[dict]:
    opps: list[dict] = []
    oid = 0
    # Regional differences: NW vs SE for deer gun illustration
    for unit in units:
        if unit.get("source") == "usace":
            continue
        region = (unit.get("region") or "").lower()
        # Archery statewide-ish
        oid += 1
        opps.append(
            {
                "id": f"ok{oid}",
                "unitId": unit["id"],
                "species": "white_tailed_deer",
                "speciesLabel": "White-tailed deer",
                "methods": ["archery"],
                "access": "wma_permit",
                "start": "2026-10-01",
                "end": "2027-01-15",
                "dateSource": "odwc_baseline",
                "county": "",
                "notes": "Archery deer — confirm ODWC openers and WMA antlerless rules",
            }
        )
        # Muzzleloader
        oid += 1
        opps.append(
            {
                "id": f"ok{oid}",
                "unitId": unit["id"],
                "species": "white_tailed_deer",
                "speciesLabel": "White-tailed deer",
                "methods": ["muzzleloader"],
                "access": "wma_permit",
                "start": "2026-10-24",
                "end": "2026-11-01",
                "dateSource": "odwc_baseline",
                "county": "",
                "notes": "Primitive firearms — confirm current dates",
            }
        )
        # Gun season — slightly different note by region
        gun_end = "2026-12-06" if "northwest" in region or "west" in region else "2026-11-29"
        oid += 1
        opps.append(
            {
                "id": f"ok{oid}",
                "unitId": unit["id"],
                "species": "white_tailed_deer",
                "speciesLabel": "White-tailed deer",
                "methods": ["firearm"],
                "access": "wma_permit",
                "start": "2026-11-21",
                "end": gun_end,
                "dateSource": "odwc_baseline",
                "county": "",
                "notes": "Deer gun season baseline; some WMAs are controlled-hunt only",
            }
        )
        oid += 1
        opps.append(
            {
                "id": f"ok{oid}",
                "unitId": unit["id"],
                "species": "white_tailed_deer",
                "speciesLabel": "White-tailed deer",
                "methods": ["firearm"],
                "access": "controlled_draw",
                "start": "2026-11-21",
                "end": "2026-11-29",
                "dateSource": "odwc_controlled",
                "county": "",
                "notes": "Controlled deer hunts on selected WMAs / Corps areas",
            }
        )
        oid += 1
        opps.append(
            {
                "id": f"ok{oid}",
                "unitId": unit["id"],
                "species": "turkey",
                "speciesLabel": "Wild turkey",
                "methods": ["shotgun", "archery"],
                "access": "controlled_draw",
                "start": "2027-04-10",
                "end": "2027-05-10",
                "dateSource": "odwc_controlled",
                "county": "",
                "notes": "Spring turkey — many public areas are controlled hunts",
            }
        )
        oid += 1
        opps.append(
            {
                "id": f"ok{oid}",
                "unitId": unit["id"],
                "species": "dove",
                "speciesLabel": "Dove",
                "methods": ["shotgun"],
                "access": "wma_permit",
                "start": "2026-09-01",
                "end": "2026-10-31",
                "dateSource": "odwc_baseline",
                "county": "",
                "notes": "Dove — confirm federal framework and field openings",
            }
        )
        oid += 1
        opps.append(
            {
                "id": f"ok{oid}",
                "unitId": unit["id"],
                "species": "quail",
                "speciesLabel": "Quail",
                "methods": ["shotgun"],
                "access": "wma_permit",
                "start": "2026-11-08",
                "end": "2027-02-15",
                "dateSource": "odwc_baseline",
                "county": "",
                "notes": "Quail season baseline",
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
        report_fetch("OK WMAs", True, f"{len(raw.get('features', []))} features")
    except Exception as exc:
        report_fetch("OK WMAs", False, str(exc))
        failures.append(f"OK WMAs: {exc}")
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
        counties = load_census_counties(STATE, force=args.force)
        report_fetch("OK counties", True, f"{len(counties['features'])} counties")
    except Exception as exc:
        failures.append(f"OK counties: {exc}")
        counties = {"type": "FeatureCollection", "features": []}

    try:
        from corps_multi import build_corps_for_state

        corps_units, corps_opps, corps_feats = build_corps_for_state("ok")
        units = units + corps_units
        geo["features"] = geo["features"] + corps_feats
        report_fetch("OK Corps merge", True, f"{len(corps_units)} lakes")
    except Exception as exc:
        report_fetch("OK Corps merge", False, str(exc))
        corps_opps = []
        failures.append(f"OK Corps: {exc}")

    opps = build_opportunities(units) + corps_opps

    meta = meta_shell(
        season_year="2026-27",
        disclaimer=(
            "Unofficial planning aid compiled from Oklahoma Department of Wildlife Conservation "
            "public WMA maps and season summaries. Controlled-hunt lists and area regs change. "
            "Confirm every hunt with ODWC before you apply or hunt."
        ),
        sources=[
            {"name": "ODWC Public WMA Boundaries", "url": WMA_URL.split("/query")[0]},
            {"name": "ODWC hunting", "url": HUNT_URL},
            {"name": "Controlled hunts", "url": CTRL_URL},
            {"name": "Go Outdoors Oklahoma", "url": BUY_URL},
        ],
        species=[
            {"id": "white_tailed_deer", "label": "White-tailed deer"},
            {"id": "turkey", "label": "Wild turkey"},
            {"id": "dove", "label": "Dove"},
            {"id": "quail", "label": "Quail"},
            {"id": "waterfowl", "label": "Waterfowl"},
        ],
        methods=[
            {"id": "archery", "label": "Archery"},
            {"id": "muzzleloader", "label": "Muzzleloader"},
            {"id": "firearm", "label": "Gun / rifle"},
            {"id": "shotgun", "label": "Shotgun"},
            {"id": "any_legal", "label": "Any legal means"},
        ],
        access=[
            {"id": "wma_permit", "label": "Open WMA / statewide regs"},
            {"id": "controlled_draw", "label": "Controlled hunt"},
            {"id": "corps_permit", "label": "Corps / USACE permit"},
        ],
        counts={
            "unitCount": len(units),
            "opportunityCount": len(opps),
            "countyCount": len(counties["features"]),
            "polygonCount": len(geo["features"]),
        },
        profile="publicLand",
        agency="ODWC",
    )

    out = DATA / STATE
    write_json(out / "units.json", units)
    write_json(out / "units.geojson", geo)
    write_json(out / "opportunities.json", opps)
    write_json(out / "licenses.json", build_licenses())
    write_json(out / "regulations.json", build_regulations())
    write_json(out / "meta.json", meta)
    write_json(out / "counties.geojson", counties)
    write_json(out / "counties.json", counties_index(counties))
    (out / "SOURCES.md").write_text(
        "# Oklahoma sources\n\n"
        f"- WMAs: {WMA_URL}\n"
        f"- Hunting: {HUNT_URL}\n"
        f"- Controlled hunts: {CTRL_URL}\n"
        f"- Buy: {BUY_URL}\n",
        encoding="utf-8",
    )
    mirror_tree(STATE)
    print(f"ok: {len(units)} units, {len(opps)} opportunities, {len(counties['features'])} counties")
    if failures and not units:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
