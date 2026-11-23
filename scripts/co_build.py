#!/usr/bin/env python3
"""Build Colorado unitGrid package: GMUs, limited/OTC hunts, licenses, regs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from state_common import (  # noqa: E402
    CACHE,
    DATA,
    CENSUS_COUNTIES_URL,
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
    write_json,
)

STATE = "co"
GMU_URL = (
    "https://services5.arcgis.com/ttNGmDvKQA7oeDQ3/arcgis/rest/services/"
    "CPWAdminData/FeatureServer/6/query?where=1%3D1&outFields=*&f=geojson"
    "&outSR=4326&returnGeometry=true"
)
# Fallback note if CPW layer fails — Census counties used as interim.
BUY_URL = "https://www.cpwshop.com/"
BROCHURE_URL = "https://cpw.state.co.us/activities/hunting/big-game"
OTC_URL = "https://cpw.state.co.us/activities/hunting/big-game/over-counter-otc-licenses"
BGSS_URL = "https://cpw.state.co.us/sites/default/files/dam/ifgylu070o/final_bgss2025-2029.pdf"


def _gmu_id(props: dict, idx: int) -> str:
    code = str(props.get("GMUID") or props.get("GMU") or idx + 1).strip()
    return f"gmu:{code}"


def _gmu_props(props: dict, uid: str) -> dict:
    code = uid.split(":", 1)[1]
    try:
        n = int(code)
    except ValueError:
        n = 0
    region = "Plains" if n >= 90 or (103 <= n <= 171) else "West / mountains"
    # Rough I-25 split: many plains GMUs are 90+; keep mountain units West.
    if n and n < 90:
        region = "West of I-25"
    elif n:
        region = "East of I-25 / plains"
    return {
        "id": uid,
        "kind": "gmu",
        "code": code,
        "name": f"GMU {code}",
        "region": region,
        "acres": acres_from_props(props, "AcresGISCa", "AcresGISCalc", "ACRES", "acres"),
        "countyHint": props.get("COUNTY"),
    }


def build_licenses() -> dict:
    return license_guide(
        title="Colorado hunting licenses, draws, and fees",
        season_year="2026",
        intro=(
            "Most deer licenses and many elk licenses are limited (draw). Some elk licenses "
            "sell over the counter by unit and season. Fees change; confirm on CPWshop before you pay."
        ),
        where_to_buy=[
            {
                "id": "internet",
                "title": "CPWshop online",
                "body": f"Buy licenses and enter draws at {BUY_URL}.",
            },
            {
                "id": "agent",
                "title": "License agent",
                "body": "CPW license agents sell OTC products and can help with applications.",
            },
            {
                "id": "draw",
                "title": "Limited license draw",
                "body": (
                    "Primary and secondary draws award limited deer, elk, pronghorn, and other big-game "
                    "licenses. Preference points apply by species."
                ),
            },
            {
                "id": "otc",
                "title": "Over the counter",
                "body": "Selected elk (and some other) licenses sell OTC by season and unit list — see CPW OTC page.",
            },
            {
                "id": "mail",
                "title": "Phone",
                "body": "CPW customer service can process some license sales by phone. Confirm current hours.",
            },
        ],
        deadlines=[
            {
                "name": "Big-game draw application (typical)",
                "date": "2026-04-01",
                "detail": "Confirm the exact 2026 primary-draw deadline in the Big Game brochure.",
            },
            {
                "name": "Archery deer/elk (west of I-25)",
                "date": "2026-09-02",
                "detail": "Opens Sept 2; closes Sept 30, 2026 per BGSS 2025–2029.",
            },
        ],
        fees=[
            {"item": "Habitat Stamp (required with most licenses)", "resident": "$12.47", "nonresident": "$12.47"},
            {"item": "Annual fishing + small game combo (approx.)", "resident": "See CPWshop", "nonresident": "See CPWshop"},
            {"item": "Deer license (limited)", "resident": "See CPWshop", "nonresident": "See CPWshop"},
            {"item": "Elk license (limited or OTC)", "resident": "See CPWshop", "nonresident": "See CPWshop"},
            {"item": "Preference point (deer/elk)", "resident": "See CPWshop", "nonresident": "See CPWshop"},
        ],
        sources=[
            {"name": "CPWshop", "url": BUY_URL},
            {"name": "Big game hunting", "url": BROCHURE_URL},
            {"name": "OTC licenses", "url": OTC_URL},
            {"name": "2025–2029 Big Game Season Structure", "url": BGSS_URL},
        ],
        hunt_series=[
            {"id": "deer", "label": "Deer limited", "points": True},
            {"id": "elk", "label": "Elk limited / OTC", "points": True},
            {"id": "pronghorn", "label": "Pronghorn", "points": True},
            {"id": "bear", "label": "Bear", "points": False},
        ],
        preference_points=[
            "Colorado uses preference points for limited deer, elk, pronghorn, and moose licenses.",
            "OTC elk licenses do not use preference points.",
            "Leftover limited licenses, when offered, are a separate sale after the draws.",
        ],
        residency_rules=[
            "Nonresidents get a share of primary-draw deer, elk, sheep, and goat licenses: up to about 20% when the hunt needed six or more resident points to draw, and up to about 25% when it needed fewer than six points for deer/elk.",
            "Nonresident allocation percentages do not apply to the secondary draw or leftover limited licenses.",
            "Nonresidents can buy most OTC licenses, but for 2026 OTC archery elk west of I-25 (and GMU 140) moved into limited draw codes; NR OTC archery elk remains only for listed units east of I-25.",
            "Many units remain OTC for residents while nonresidents must draw — confirm the current Big Game brochure by hunt code.",
        ],
    )


def build_regulations() -> dict:
    return regulation_guide(
        title="Colorado methods, restrictions, and GMU rules",
        methods=[
            {
                "id": "archery",
                "label": "Archery",
                "summary": "Longbow, recurve, or compound bow meeting CPW draw-weight and broadhead rules for big game.",
            },
            {
                "id": "muzzleloader",
                "label": "Muzzleloader",
                "summary": "Muzzleloader-only season uses legal muzzleloading rifles; optics rules follow the brochure.",
            },
            {
                "id": "firearm",
                "label": "Rifle / firearm",
                "summary": "Centerfire rifles and other legal firearms for regular rifle seasons.",
            },
            {
                "id": "any_legal",
                "label": "Any legal method",
                "summary": "Some plains elk seasons allow any legal method of take for the license.",
            },
            {
                "id": "shotgun",
                "label": "Shotgun",
                "summary": "Shotguns for turkey, dove, and small game as listed.",
            },
        ],
        prohibited=[
            "Hunting without a valid license for that species, unit, and manner of take.",
            "Hunting in closed areas, national parks, or private land without permission.",
            "Using artificial light or thermal/night vision where prohibited.",
            "Shooting from or across a public road.",
        ],
        unit_rules=[
            "Limited licenses are valid only in the GMU(s) printed on the license.",
            "OTC elk licenses list eligible units; you choose among them for that season.",
            "Plains (east of I-25) deer and elk seasons differ from west-of-I-25 structure.",
            "Manner of take (archery, muzzleloader, rifle) is part of the hunt code.",
        ],
        sources=[
            {"name": "Big game hunting", "url": BROCHURE_URL},
            {"name": "2025–2029 Big Game Season Structure", "url": BGSS_URL},
            {"name": "OTC licenses", "url": OTC_URL},
        ],
    )


def build_hunts(units: list[dict]) -> list[dict]:
    west = [u["id"] for u in units if "West" in u.get("region", "")]
    east = [u["id"] for u in units if "East" in u.get("region", "") or "Plains" in u.get("region", "")]
    if not west:
        west = [u["id"] for u in units]
    if not east:
        east = [u["id"] for u in units]
    all_ids = [u["id"] for u in units]

    return [
        {
            "id": "co-elk-archery-west",
            "huntNumber": None,
            "name": "Elk archery — west of I-25",
            "species": "elk",
            "speciesLabel": "Elk",
            "series": "elk",
            "methods": ["archery"],
            "access": "general_otc",
            "bagLimit": "Per license (either-sex / antlered / antlerless by code)",
            "start": "2026-09-02",
            "end": "2026-09-30",
            "tag": "Archery elk (OTC or limited by unit)",
            "tagSaleDeadline": None,
            "applicationDeadline": "2026-04-01",
            "scope": "region",
            "unitIds": west,
            "restrictions": [],
            "notes": "BGSS 2025–2029: archery deer/elk west of I-25 and GMU 140 is Sept 2–30 annually. Many units are OTC for residents.",
        },
        {
            "id": "co-deer-archery-west",
            "huntNumber": None,
            "name": "Deer archery — west of I-25",
            "species": "deer",
            "speciesLabel": "Deer",
            "series": "deer",
            "methods": ["archery"],
            "access": "controlled_draw",
            "bagLimit": "Per limited license",
            "start": "2026-09-02",
            "end": "2026-09-30",
            "tag": "Limited archery deer",
            "tagSaleDeadline": None,
            "applicationDeadline": "2026-04-01",
            "scope": "region",
            "unitIds": west,
            "restrictions": [],
            "notes": "All archery deer licenses are limited by GMU/DAU.",
        },
        {
            "id": "co-muzzleloader",
            "huntNumber": None,
            "name": "Muzzleloader deer/elk — west structure",
            "species": "elk",
            "speciesLabel": "Elk",
            "series": "elk",
            "methods": ["muzzleloader"],
            "access": "controlled_draw",
            "bagLimit": "Per license",
            "start": "2026-09-12",
            "end": "2026-09-20",
            "tag": "Muzzleloader elk/deer",
            "tagSaleDeadline": None,
            "applicationDeadline": "2026-04-01",
            "scope": "region",
            "unitIds": west,
            "restrictions": [],
            "notes": "2026 muzzleloader window Sept 12–20 per CPW season announcements.",
        },
        {
            "id": "co-rifle-1",
            "huntNumber": None,
            "name": "First regular rifle",
            "species": "elk",
            "speciesLabel": "Elk",
            "series": "elk",
            "methods": ["firearm"],
            "access": "controlled_draw",
            "bagLimit": "Per license",
            "start": "2026-10-14",
            "end": "2026-10-18",
            "tag": "Rifle elk/deer",
            "tagSaleDeadline": None,
            "applicationDeadline": "2026-04-01",
            "scope": "multi_gmu",
            "unitIds": west,
            "restrictions": [],
            "notes": "1st rifle season Oct 14–18, 2026.",
        },
        {
            "id": "co-rifle-2-otc",
            "huntNumber": None,
            "name": "Second rifle elk (OTC bulls in listed units)",
            "species": "elk",
            "speciesLabel": "Elk",
            "series": "elk",
            "methods": ["firearm"],
            "access": "general_otc",
            "bagLimit": "Antlered elk where OTC",
            "start": "2026-10-24",
            "end": "2026-11-01",
            "tag": "OTC rifle bull elk",
            "tagSaleDeadline": None,
            "applicationDeadline": None,
            "scope": "multi_gmu",
            "unitIds": west,
            "restrictions": [],
            "notes": "2nd rifle Oct 24–Nov 1, 2026. OTC bull lists are unit-specific — confirm CPW OTC page.",
        },
        {
            "id": "co-rifle-3-otc",
            "huntNumber": None,
            "name": "Third rifle elk (OTC bulls in listed units)",
            "species": "elk",
            "speciesLabel": "Elk",
            "series": "elk",
            "methods": ["firearm"],
            "access": "general_otc",
            "bagLimit": "Antlered elk where OTC",
            "start": "2026-11-07",
            "end": "2026-11-15",
            "tag": "OTC rifle bull elk",
            "tagSaleDeadline": None,
            "applicationDeadline": None,
            "scope": "multi_gmu",
            "unitIds": west,
            "restrictions": [],
            "notes": "3rd rifle Nov 7–15, 2026.",
        },
        {
            "id": "co-rifle-4",
            "huntNumber": None,
            "name": "Fourth regular rifle",
            "species": "elk",
            "speciesLabel": "Elk",
            "series": "elk",
            "methods": ["firearm"],
            "access": "controlled_draw",
            "bagLimit": "Per license",
            "start": "2026-11-18",
            "end": "2026-11-22",
            "tag": "Rifle elk/deer",
            "tagSaleDeadline": None,
            "applicationDeadline": "2026-04-01",
            "scope": "multi_gmu",
            "unitIds": west,
            "restrictions": [],
            "notes": "4th rifle Nov 18–22, 2026.",
        },
        {
            "id": "co-plains-deer-archery",
            "huntNumber": None,
            "name": "Plains archery deer (split windows)",
            "species": "deer",
            "speciesLabel": "Deer",
            "series": "deer",
            "methods": ["archery"],
            "access": "controlled_draw",
            "bagLimit": "Per limited license",
            "start": "2026-10-01",
            "end": "2026-10-23",
            "tag": "Limited plains archery deer",
            "tagSaleDeadline": None,
            "applicationDeadline": "2026-04-01",
            "scope": "region",
            "unitIds": east,
            "restrictions": [],
            "notes": "Plains archery also reopens Nov 4–30 and Dec 15–31 in many units (separate rows omitted for brevity).",
        },
        {
            "id": "co-plains-elk-rifle",
            "huntNumber": None,
            "name": "Plains rifle elk",
            "species": "elk",
            "speciesLabel": "Elk",
            "series": "elk",
            "methods": ["any_legal"],
            "access": "general_otc",
            "bagLimit": "Per OTC/limited plains elk license",
            "start": "2026-09-01",
            "end": "2027-01-31",
            "tag": "Plains elk",
            "tagSaleDeadline": None,
            "applicationDeadline": None,
            "scope": "region",
            "unitIds": east,
            "restrictions": [],
            "notes": "Plains rifle elk Sept 1–Jan 31 in eligible east-of-I-25 GMUs; any legal method.",
        },
        {
            "id": "co-dove",
            "huntNumber": None,
            "name": "Mourning dove",
            "species": "dove",
            "speciesLabel": "Mourning dove",
            "series": "migratory",
            "methods": ["shotgun"],
            "access": "general_otc",
            "bagLimit": "Federal/state daily bag",
            "start": "2026-09-01",
            "end": "2026-11-29",
            "tag": "Small game + HIP",
            "tagSaleDeadline": None,
            "applicationDeadline": None,
            "scope": "statewide",
            "unitIds": all_ids,
            "restrictions": [],
            "notes": "Confirm the current migratory bird season framework.",
        },
        {
            "id": "co-turkey-spring",
            "huntNumber": None,
            "name": "Spring turkey",
            "species": "turkey",
            "speciesLabel": "Wild turkey",
            "series": "turkey",
            "methods": ["shotgun", "archery"],
            "access": "controlled_draw",
            "bagLimit": "Per turkey license",
            "start": "2027-04-10",
            "end": "2027-05-31",
            "tag": "Turkey license",
            "tagSaleDeadline": None,
            "applicationDeadline": None,
            "scope": "statewide",
            "unitIds": all_ids,
            "restrictions": [],
            "notes": "Spring turkey dates vary by unit; confirm the turkey brochure.",
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    cache = CACHE / STATE
    failures: list[str] = []
    sources_notes: list[str] = []

    try:
        raw = download_geojson(GMU_URL, cache / "gmu.raw.geojson", force=args.force)
        report_fetch("CO GMUs (CPW)", True, f"{len(raw.get('features', []))} features")
        sources_notes.append(f"CPW GMU FeatureServer layer 6: {GMU_URL}")
    except Exception as exc:
        failures.append(f"CO GMUs: {exc}")
        report_fetch("CO GMUs (CPW)", False, str(exc))
        raw = {"type": "FeatureCollection", "features": []}
        sources_notes.append(
            "CPW GMU fetch failed — interim county polygons may be used; see SOURCES.md."
        )

    used_counties_as_units = False
    units: list[dict] = []
    primary: dict = {"type": "FeatureCollection", "features": []}

    if raw.get("features"):
        units, primary = map_units_from_geojson(raw, id_fn=_gmu_id, props_fn=_gmu_props)
    else:
        # Interim: Census counties as unit polygons (documented).
        used_counties_as_units = True
        try:
            from state_common import simplify_feature, feature_collection

            counties_fc = load_census_counties(STATE, force=args.force)
            feats = []
            for feat in counties_fc["features"]:
                p = feat["properties"]
                props = {
                    "id": f"gmu:county-{p['geoid']}",
                    "kind": "gmu_interim_county",
                    "code": p["geoid"],
                    "name": f"{p['name']} County (interim GMU proxy)",
                    "region": "Interim county proxy",
                    "acres": None,
                    "lon": None,
                    "lat": None,
                }
                simplified = simplify_feature(feat, props, feature_id=props["id"])
                if simplified:
                    feats.append(simplified)
                    units.append(simplified["properties"])
            primary = feature_collection(feats)
            report_fetch("CO interim counties-as-GMUs", True, f"{len(feats)} counties")
            sources_notes.append(
                "INTERIM: Real CPW GMUs unavailable at build time; Census counties used as unit polygons."
            )
        except Exception as exc:
            failures.append(f"CO interim counties: {exc}")

    # Dedup
    seen: set[str] = set()
    dedup_u, dedup_f = [], []
    for u, f in zip(units, primary["features"]):
        if u["id"] in seen:
            continue
        seen.add(u["id"])
        dedup_u.append(u)
        dedup_f.append(f)
    units, primary = dedup_u, {"type": "FeatureCollection", "features": dedup_f}

    try:
        counties = load_census_counties(STATE, force=args.force)
        report_fetch("CO counties", True, f"{len(counties['features'])} counties")
    except Exception as exc:
        failures.append(f"CO counties: {exc}")
        report_fetch("CO counties", False, str(exc))
        counties = {"type": "FeatureCollection", "features": []}

    hunts = build_hunts(units) if units else []
    try:
        from corps_multi import build_corps_for_state

        _cu, _co, public_feats = build_corps_for_state("co")
        public_land = {"type": "FeatureCollection", "features": public_feats}
        report_fetch("CO Corps public land", True, f"{len(public_feats)} features")
    except Exception as exc:
        public_land = {"type": "FeatureCollection", "features": []}
        report_fetch("CO Corps public land", False, str(exc))
        failures.append(f"CO Corps: {exc}")

    meta = meta_shell(
        season_year="2026",
        disclaimer=(
            "Unofficial planning aid compiled from Colorado Parks and Wildlife public GIS and the "
            "2025–2029 Big Game Season Structure / 2026 season announcements. Hunt codes, OTC lists, "
            "and boundaries change. Confirm every hunt with CPW before you apply or hunt."
        ),
        sources=[
            {"name": "CPW GMU boundaries", "url": GMU_URL.split("/query")[0]},
            {"name": "Big game hunting", "url": BROCHURE_URL},
            {"name": "OTC licenses", "url": OTC_URL},
            {"name": "2025–2029 BGSS PDF", "url": BGSS_URL},
            {"name": "Census counties", "url": CENSUS_COUNTIES_URL},
        ],
        species=[
            {"id": "deer", "label": "Deer"},
            {"id": "elk", "label": "Elk"},
            {"id": "turkey", "label": "Wild turkey"},
            {"id": "dove", "label": "Mourning dove"},
            {"id": "bear", "label": "Black bear"},
        ],
        methods=[
            {"id": "archery", "label": "Archery"},
            {"id": "muzzleloader", "label": "Muzzleloader"},
            {"id": "firearm", "label": "Rifle / firearm"},
            {"id": "any_legal", "label": "Any legal method"},
            {"id": "shotgun", "label": "Shotgun"},
        ],
        access=[
            {"id": "controlled_draw", "label": "Limited draw"},
            {"id": "general_otc", "label": "Over the counter"},
            {"id": "corps_permit", "label": "Corps / USACE permit"},
        ],
        counts={
            "unitCount": len(units),
            "huntCount": len(hunts),
            "countyCount": len(counties["features"]),
            "polygonCount": len(primary["features"]),
            "publicLandCount": len(public_land["features"]),
            "usedCountyProxy": used_counties_as_units,
        },
        profile="unitGrid",
        agency="CPW",
    )

    out = DATA / STATE
    write_json(out / "units.json", units)
    write_json(out / "primary.geojson", primary)
    write_json(out / "units.geojson", primary)
    write_json(out / "hunts.json", hunts)
    write_json(out / "licenses.json", build_licenses())
    write_json(out / "regulations.json", build_regulations())
    write_json(out / "meta.json", meta)
    write_json(out / "counties.geojson", counties)
    write_json(out / "counties.json", counties_index(counties))
    write_json(out / "public-land.geojson", public_land)
    (out / "SOURCES.md").write_text(
        "# Colorado sources\n\n"
        + "\n".join(f"- {n}" for n in sources_notes)
        + f"\n- Buy: {BUY_URL}\n- BGSS: {BGSS_URL}\n",
        encoding="utf-8",
    )
    mirror_tree(STATE)
    print(f"co: {len(units)} units, {len(hunts)} hunts, {len(counties['features'])} counties")
    if failures and not units:
        print("failures:", "; ".join(failures))
        return 1
    if failures:
        print("warnings:", "; ".join(failures))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
