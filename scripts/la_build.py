#!/usr/bin/env python3
"""Build Louisiana publicLand package: WMAs, opportunities, licenses, regs."""

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

STATE = "la"
# Official LDWF MapServer often returns empty layers; ArcGIS Online mirror works.
WMA_URL = (
    "https://services1.arcgis.com/6euNCaGPCgCzgAVF/arcgis/rest/services/"
    "LDWF_WMA_Refuge/FeatureServer/0/query?where=1%3D1&outFields=*&f=geojson"
    "&outSR=4326&returnGeometry=true"
)
WMA_URL_FALLBACK = (
    "https://services7.arcgis.com/oZApK97pGkADa0Bn/arcgis/rest/services/"
    "LDWF_WMA_Boundaries_Shapefile/FeatureServer/0/query?where=1%3D1&outFields=*"
    "&f=geojson&outSR=4326&returnGeometry=true"
)
BUY_URL = "https://louisianaoutdoors.com/"
SEASONS_URL = "https://www.wlf.louisiana.gov/page/seasons-and-regulations"
FEES_URL = "https://www.wlf.louisiana.gov/page/license-and-permit-fee-list"


def _unit_id(props: dict, idx: int) -> str:
    name = str(props.get("NAME") or props.get("Name") or f"wma-{idx}")
    return f"wma:{slugify(name)}"


def _unit_props(props: dict, uid: str) -> dict:
    name = title_case_name(str(props.get("NAME") or props.get("Name") or uid))
    return {
        "id": uid,
        "unitIds": [uid],
        "name": name,
        "kind": "wma",
        "type": "wma",
        "source": "ldwf",
        "counties": [],
        "region": "",
        "acres": acres_from_props(props, "GIS_Acres", "ACRES", "Acres", "acres"),
        "link": props.get("Link") or props.get("LINK") or "",
        "lease": props.get("Lease") or "WMA",
        "species": ["white_tailed_deer", "turkey", "dove", "waterfowl", "squirrel"],
        "methods": ["archery", "muzzleloader", "firearm", "shotgun"],
        "access": ["wma_permit", "lottery"],
    }


def build_licenses() -> dict:
    return license_guide(
        title="Louisiana hunting licenses and WMA access",
        season_year="2026-27",
        intro=(
            "A Basic Hunting License is required for most hunters. Deer, turkey, and waterfowl "
            "need additional licenses. A WMA Access Permit is required on LDWF WMAs/refuges "
            "(ages 18+). Confirm fees at LDWF before you buy."
        ),
        where_to_buy=[
            {
                "id": "internet",
                "title": "Online",
                "body": f"Buy licenses and WMA access at {BUY_URL}.",
            },
            {
                "id": "agent",
                "title": "License vendor",
                "body": "Authorized vendors sell hunting licenses statewide.",
            },
            {
                "id": "lottery",
                "title": "WMA lottery hunts",
                "body": "Deer, turkey, dove, waterfowl, and other lottery hunts are applied for through LDWF’s lottery system.",
            },
            {
                "id": "otc",
                "title": "Over the counter / self-clearing",
                "body": "Many WMA hunts are open with self-clearing permits during published seasons; lotteries are separate.",
            },
            {
                "id": "corps",
                "title": "Corps of Engineers lakes",
                "body": "Some USACE projects require a separate lake/Recreation.gov permit in addition to LDWF licenses.",
            },
        ],
        deadlines=[
            {
                "name": "License validity",
                "date": None,
                "detail": "Licenses are valid 365 days from purchase.",
            },
            {
                "name": "WMA lottery applications",
                "date": None,
                "detail": "Windows vary by hunt — check LDWF lottery listings.",
            },
        ],
        fees=[
            {"item": "Basic Hunting", "resident": "$20", "nonresident": "$200"},
            {"item": "Deer license", "resident": "$15", "nonresident": "$100"},
            {"item": "Turkey license", "resident": "$12", "nonresident": "$50"},
            {"item": "Waterfowl license", "resident": "$12", "nonresident": "$50"},
            {"item": "Youth Hunting", "resident": "$5", "nonresident": "$5"},
            {"item": "WMA Access Annual Permit", "resident": "$20", "nonresident": "$20"},
            {"item": "WMA Access 5-Day Permit", "resident": "$5", "nonresident": "$5"},
            {"item": "Sportsman's Paradise", "resident": "$100", "nonresident": "$400"},
        ],
        sources=[
            {"name": "Louisiana Outdoors license sales", "url": BUY_URL},
            {"name": "License and permit fee list", "url": FEES_URL},
            {"name": "Seasons and regulations", "url": SEASONS_URL},
            {"name": "Lottery hunts", "url": "https://www.wlf.louisiana.gov/page/lottery-hunts"},
        ],
        residency_rules=[
            "Most deer, turkey, dove, waterfowl, and other WMA lottery hunts are open to nonresidents who hold the required nonresident licenses and WMA access permit.",
            "Bear harvest permits are residents only (nonresident fee listed as n/a).",
            "Commercial alligator lottery harvests on WMAs/public lakes require Louisiana residency; recreational alligator lottery entry is residents only (nonresidents may accompany a resident winner with the proper alligator sports hunter license).",
            "Nonresident Native 10-day licenses are available only to people born in Louisiana who no longer reside there.",
        ],
    )


def build_regulations() -> dict:
    return regulation_guide(
        title="Louisiana methods, WMA rules, and restrictions",
        methods=[
            {
                "id": "archery",
                "label": "Archery",
                "summary": "Archery deer seasons follow Deer Areas 1–10 and individual WMA schedules.",
            },
            {
                "id": "muzzleloader",
                "label": "Primitive firearms",
                "summary": "Primitive firearms seasons are set by deer area and by WMA schedule.",
            },
            {
                "id": "firearm",
                "label": "Firearms",
                "summary": "Still-hunt and with-or-without-dogs firearms seasons vary by deer area; WMAs often still-hunt only.",
            },
            {
                "id": "shotgun",
                "label": "Shotgun",
                "summary": "Turkey, dove, and waterfowl; non-toxic shot for waterfowl.",
            },
        ],
        prohibited=[
            "Using a WMA without a WMA Access Permit (ages 18+) and self-clearing check-in where required.",
            "Hunting outside the dates and methods on that WMA’s individual schedule.",
            "Baiting where prohibited; leaving trash or cutting trees on WMAs.",
        ],
        unit_rules=[
            "Each WMA publishes its own schedule — WMA dates override private-land deer-area dates on that property.",
            "Lottery hunts require a drawn permit for that specific hunt.",
            "Self-clearing permits are required for most activities on WMAs.",
        ],
        sources=[
            {"name": "Seasons and regulations", "url": SEASONS_URL},
            {"name": "WMA schedules (eRegulations)", "url": "https://www.eregulations.com/louisiana/hunting"},
        ],
    )


def build_opportunities(units: list[dict]) -> list[dict]:
    opps: list[dict] = []
    oid = 0
    # Deer Area–style regional rows applied to all WMAs as a planning baseline;
    # individual WMA schedules may shorten or close seasons.
    windows = [
        ("white_tailed_deer", "White-tailed deer", ["archery"], "2026-10-01", "2027-01-31", "wma_permit", "Archery baseline (many WMAs Oct 1–Jan 31)"),
        ("white_tailed_deer", "White-tailed deer", ["muzzleloader"], "2026-11-14", "2026-11-20", "wma_permit", "Primitive firearms — confirm deer area / WMA"),
        ("white_tailed_deer", "White-tailed deer", ["firearm"], "2026-11-21", "2027-01-03", "wma_permit", "Firearms still-hunt baseline — confirm WMA"),
        ("white_tailed_deer", "White-tailed deer", ["firearm"], "2026-10-01", "2027-01-31", "lottery", "Some WMAs use deer lottery hunts instead of open seasons"),
        ("turkey", "Wild turkey", ["shotgun", "archery"], "2027-04-03", "2027-05-02", "wma_permit", "Private-land Area A window; WMA turkey often shorter or lottery"),
        ("turkey", "Wild turkey", ["shotgun"], "2027-03-26", "2027-03-28", "lottery", "Youth / physically challenged turkey lottery on some areas"),
        ("dove", "Dove", ["shotgun"], "2026-09-05", "2026-09-20", "wma_permit", "Early dove segment — confirm federal framework"),
        ("dove", "Dove", ["shotgun"], "2026-10-10", "2026-12-07", "wma_permit", "Later dove segments vary"),
        ("waterfowl", "Waterfowl", ["shotgun"], "2026-11-14", "2027-01-31", "wma_permit", "Duck season splits vary by zone"),
        ("squirrel", "Squirrel", ["any_legal", "shotgun"], "2026-10-03", "2027-02-28", "wma_permit", "Squirrel season baseline"),
    ]
    for unit in units:
        for species, label, methods, start, end, access, notes in windows:
            # Skip turkey open row for most — keep lottery + one open sample on larger areas
            if species == "turkey" and access == "wma_permit" and (unit.get("acres") or 0) < 5000:
                continue
            oid += 1
            opps.append(
                {
                    "id": f"la{oid}",
                    "unitId": unit["id"],
                    "species": species,
                    "speciesLabel": label,
                    "methods": methods,
                    "access": access,
                    "start": start,
                    "end": end,
                    "dateSource": "ldwf_season_table",
                    "county": "",
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

    raw = {"type": "FeatureCollection", "features": []}
    for label, url in [("LA WMA (AGOL)", WMA_URL), ("LA WMA shapefile mirror", WMA_URL_FALLBACK)]:
        try:
            raw = download_geojson(url, cache / "wma.raw.geojson", force=args.force)
            if raw.get("features"):
                report_fetch(label, True, f"{len(raw['features'])} features")
                break
            report_fetch(label, False, "0 features")
        except Exception as exc:
            report_fetch(label, False, str(exc))
            failures.append(f"{label}: {exc}")

    units, geo = map_units_from_geojson(raw, id_fn=_unit_id, props_fn=_unit_props)
    seen: set[str] = set()
    dedup_u, dedup_f = [], []
    for u, f in zip(units, geo["features"]):
        if u["id"] in seen:
            continue
        seen.add(u["id"])
        dedup_u.append(u)
        dedup_f.append(f)
    units = dedup_u
    geo = {"type": "FeatureCollection", "features": dedup_f}

    try:
        counties = load_census_counties(STATE, force=args.force)
        report_fetch("LA parishes", True, f"{len(counties['features'])} parishes")
    except Exception as exc:
        failures.append(f"LA counties: {exc}")
        counties = {"type": "FeatureCollection", "features": []}

    # Merge Corps units for LA
    try:
        from corps_multi import build_corps_for_state

        corps_units, corps_opps, corps_feats = build_corps_for_state("la")
        units = units + corps_units
        geo["features"] = geo["features"] + corps_feats
    except Exception as exc:
        report_fetch("LA Corps merge", False, str(exc))
        corps_opps = []
        failures.append(f"LA Corps: {exc}")
    else:
        report_fetch("LA Corps merge", True, f"{len(corps_units)} lakes")

    opps = build_opportunities([u for u in units if u.get("source") != "usace"]) + corps_opps

    meta = meta_shell(
        season_year="2026-27",
        disclaimer=(
            "Unofficial planning aid compiled from Louisiana Department of Wildlife and Fisheries "
            "public maps and season tables. WMA schedules override statewide deer-area dates on those "
            "properties. Confirm every hunt with LDWF before you go."
        ),
        sources=[
            {"name": "LDWF WMA/Refuge polygons", "url": WMA_URL.split("/query")[0]},
            {"name": "Seasons and regulations", "url": SEASONS_URL},
            {"name": "License fees", "url": FEES_URL},
            {"name": "License sales", "url": BUY_URL},
        ],
        species=[
            {"id": "white_tailed_deer", "label": "White-tailed deer"},
            {"id": "turkey", "label": "Wild turkey"},
            {"id": "dove", "label": "Dove"},
            {"id": "waterfowl", "label": "Waterfowl"},
            {"id": "squirrel", "label": "Squirrel"},
        ],
        methods=[
            {"id": "archery", "label": "Archery"},
            {"id": "muzzleloader", "label": "Primitive firearms"},
            {"id": "firearm", "label": "Firearms"},
            {"id": "shotgun", "label": "Shotgun"},
            {"id": "any_legal", "label": "Any legal means"},
        ],
        access=[
            {"id": "wma_permit", "label": "WMA access / self-clearing"},
            {"id": "lottery", "label": "Lottery"},
            {"id": "corps_permit", "label": "Corps / USACE permit"},
        ],
        counts={
            "unitCount": len(units),
            "opportunityCount": len(opps),
            "countyCount": len(counties["features"]),
            "polygonCount": len(geo["features"]),
        },
        profile="publicLand",
        agency="LDWF",
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
        "# Louisiana sources\n\n"
        f"- WMA polygons: {WMA_URL}\n"
        f"- Fallback shapefile service: {WMA_URL_FALLBACK}\n"
        f"- Note: gis.wlf.la.gov LDWF_WMA_Refuge MapServer returned empty layers at build time.\n"
        f"- Seasons: {SEASONS_URL}\n"
        f"- Buy: {BUY_URL}\n",
        encoding="utf-8",
    )
    mirror_tree(STATE)
    print(f"la: {len(units)} units, {len(opps)} opportunities, {len(counties['features'])} parishes")
    if failures and not units:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
