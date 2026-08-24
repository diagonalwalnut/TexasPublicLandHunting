"""Join APH catalog, KMZ polygons, Outdoor Annual dates, and optional PDF notes."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from shapely.geometry import Point, mapping

from booklet import BOOKLET_URL, load_booklet_pages, lookup_unit
from county_seasons import load_counties, lookup_county, split_counties, windows_from_county
from geometry import (
    centroid_point,
    dissolve,
    geom_to_geojson,
    parse_gpx_points,
    parse_kml_polygons,
)
from pdfs import apply_general_means, general_season_methods, methods_from_pdf_text, parse_pdf
from safe import resource_stem, tpwd_url
from seasons import SEASON_YEAR, default_calendar, windows_for
from species import SPECIES, classify_tag, legal_game_tags

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
DATA = ROOT / "data"
WEB_DATA = ROOT / "web" / "public" / "data"

PDF_BASE = "https://tpwd.texas.gov/huntwild/hunt/public/annual_public_hunting/resources"

# Approximate public coordinates for APH units missing from the 2026-27 KMZ.
FALLBACK_COORDS: dict[str, tuple[float, float]] = {
    "504": (-98.07, 30.54),  # Balcones Canyonlands NWR
    "1152": (-103.97, 29.47),  # Big Bend Ranch SP
    "1079": (-101.05, 34.41),  # Caprock Canyons SP
    "1097": (-99.75, 34.11),  # Copper Breaks SP
    "736": (-102.32, 34.55),  # Playa Lakes WMA Dimmitt
    "726": (-95.98, 31.30),  # Keechi Creek WMA
    "1019": (-97.36, 31.93),  # Lake Whitney SP
    "760": (-96.98, 28.47),  # Guadalupe Delta San Antonio River Unit
    "2533": (-99.73, 33.16),  # Haskell County Complex
    "2534": (-99.73, 33.16),
}

FALLBACK_NAME_COORDS: list[tuple[str, tuple[float, float]]] = [
    ("dead water", (-95.17, 31.82)),
    ("rocky point", (-95.14, 31.79)),
    ("sandy bluff", (-95.20, 31.77)),
    ("walnut branch", (-95.11, 31.84)),
]


def unit_ids(row: dict) -> list[str]:
    ids: list[str] = []
    for key in ("unitNumber", "unitNumber2", "unitNumber3", "unitNumber4", "unitNumber5"):
        raw = str(row.get(key) or "").strip()
        if not raw or raw in {"&ensp;", "&nbsp;", "none"}:
            continue
        cleaned = re.sub(r"[^0-9A-Za-z]", "", raw)
        if cleaned:
            ids.append(cleaned)
    return list(dict.fromkeys(ids))


def infer_type(name: str, unit_id: str) -> str:
    n = name.lower()
    if "wma" in n:
        return "wma"
    if " sp" in f" {n}" or n.endswith(" sp") or "state park" in n:
        return "state_park"
    if unit_id.isdigit() and int(unit_id) >= 2000:
        return "dove_lease"
    if "phl" in n or "public hunting" in n:
        return "phl"
    return "other"


def load_points() -> dict[str, tuple[float, float]]:
    pts: dict[str, tuple[float, float]] = {}
    for fname in ("hunt_points.geojson", "dove_points.geojson"):
        path = CACHE / fname
        if not path.exists():
            continue
        fc = json.loads(path.read_text())
        for feat in fc.get("features", []):
            props = feat.get("properties") or {}
            geom = feat.get("geometry") or {}
            coords = geom.get("coordinates")
            if not coords or geom.get("type") != "Point":
                continue
            lon, lat = float(coords[0]), float(coords[1])
            for key in ("Unit_Num", "LEASE_NUM", "unitNumber"):
                uid = str(props.get(key) or "").strip()
                if uid:
                    pts[uid] = (lon, lat)
            name = props.get("LoName") or props.get("LEASE_NAME") or props.get("Name")
            if name:
                pts[str(name).strip().lower()] = (lon, lat)
    gpx_hunt = CACHE / "PublicHuntLocatorPointsGPX2026-27" / "PublicHuntPts.gpx"
    gpx_lease = CACHE / "PublicHuntLocatorPointsGPX2026-27" / "LeasePts.gpx"
    for gpx in (gpx_hunt, gpx_lease):
        if gpx.exists():
            for name, xy in parse_gpx_points(gpx).items():
                pts[name.lower()] = xy
    return pts


def load_pdf_notes(area_pdf: str) -> dict:
    if not area_pdf:
        return {}
    path = CACHE / "pdfs" / f"{area_pdf}.pdf"
    if not path.exists():
        return {}
    return parse_pdf(path)


def build() -> None:
    catalog = json.loads((CACHE / "aph_202627.json").read_text())
    hunt_polys = parse_kml_polygons(
        CACHE / "kmz_hunt" / "doc.kml",
        ("PH_UnitNum", "Unit_Num"),
    )
    dove_polys = parse_kml_polygons(
        CACHE / "kmz_dove" / "doc.kml",
        ("LEASE_NUM", "Unit_Num"),
    )
    points = load_points()
    county_index = load_counties(CACHE / "counties")
    booklet = load_booklet_pages(CACHE / "pwd_bk_w7000_0112a.pdf")

    units = []
    opportunities = []
    unit_geoms = {}
    region_geoms: dict[str, list] = {}
    opp_id = 0

    for idx, row in enumerate(catalog):
        ids = unit_ids(row)
        name = str(row.get("areaName") or "").strip()
        if not ids:
            slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
            ids = [slug]
        primary = ids[0]
        region = str(row.get("region") or "").strip()
        county_names = split_counties(str(row.get("county") or "").strip())
        area_pdf = resource_stem(str(row.get("areaPDF") or "").strip())
        aerial = resource_stem(str(row.get("aerialPDFurl") or "").strip())
        pdf_url = tpwd_url(
            f"{PDF_BASE}/{area_pdf}.pdf"
            if area_pdf and area_pdf.lower() not in {"no_areamappdf", "none", ""}
            else ""
        )

        geoms = []
        acres = None
        for uid in ids:
            blob = hunt_polys.get(uid) or dove_polys.get(uid)
            if blob:
                geoms.append(blob["geometry"])
                if acres is None:
                    acres = blob.get("acres")
        geom = dissolve(geoms, simplify=0.0008) if geoms else None

        lonlat = None
        if geom is not None:
            c = centroid_point(geom)
            if c:
                lonlat = (c.x, c.y)
        if lonlat is None:
            for uid in ids:
                if uid in points:
                    lonlat = points[uid]
                    break
            if lonlat is None:
                lonlat = points.get(name.lower())
        if lonlat is None:
            for uid in ids:
                if uid in FALLBACK_COORDS:
                    lonlat = FALLBACK_COORDS[uid]
                    break
        if lonlat is None:
            lname = name.lower()
            for needle, xy in FALLBACK_NAME_COORDS:
                if needle in lname:
                    lonlat = xy
                    break

        unit_type = infer_type(name, primary)
        pdf_sections = load_pdf_notes(area_pdf)
        legal_text = pdf_sections.get("LEGAL GAME") or pdf_sections.get("MEANS RESTRICTION") or ""
        pdf_blob = " ".join(pdf_sections.values()) if pdf_sections else legal_text
        pdf_methods = methods_from_pdf_text(pdf_blob) if pdf_blob else []
        general_means = general_season_methods(pdf_blob) if pdf_blob else None
        registration = "none"
        blob_text = " ".join(pdf_sections.values()).lower()
        if "electronic on-site" in blob_text or "eosr" in blob_text:
            registration = "eosr"
        elif "on-site registration" in blob_text or "osr" in blob_text:
            registration = "osr"

        complexes = [
            str(row.get(f"complex{i}")).strip()
            for i in range(1, 7)
            if str(row.get(f"complex{i}") or "").strip()
        ]
        tags = legal_game_tags(row)
        classified = []
        for tag in tags:
            classified.extend(classify_tag(tag))

        extra_access = []
        if row.get("epostcard_label"):
            extra_access.append("e_postcard")
        if row.get("regular_label"):
            extra_access.append("regular_permit")

        county_pages = []
        seen_slugs = set()
        for cname in county_names:
            page = lookup_county(county_index, cname)
            if not page or page.get("slug") in seen_slugs:
                continue
            seen_slugs.add(page.get("slug"))
            county_pages.append(page)

        species_set = sorted({c["species"] for c in classified if c["species"] != "fishing"})
        methods_set = sorted({m for c in classified for m in c["methods"]})
        access_set = sorted({c["access"] for c in classified} | set(extra_access))
        if not access_set:
            access_set = ["aph_walk_in"]

        feature_id = primary
        # Keep complexes unique even if they share a blank primary id.
        if any(u["id"] == feature_id for u in units):
            feature_id = f"{primary}-{idx}"

        unit = {
            "id": feature_id,
            "unitIds": ids,
            "name": name,
            "counties": county_names,
            "region": region,
            "acres": acres,
            "type": unit_type,
            "pdfUrl": pdf_url,
            "aerialPdfUrl": tpwd_url(
                f"{PDF_BASE}/{aerial}.pdf"
                if aerial and aerial.lower() not in {"no_areamappdf", "none"}
                else ""
            ),
            "registration": registration,
            "legalGameTags": tags,
            "legalGameText": legal_text,
            "species": species_set,
            "methods": methods_set,
            "access": access_set,
            "complexes": complexes,
            "hasEpostcard": bool(row.get("epostcard_label")),
            "hasRegularPermit": bool(row.get("regular_label")),
            "epostcardUrl": tpwd_url(str(row.get("epostcard_url") or "")),
            "countySlugs": [p["slug"] for p in county_pages],
            "lon": lonlat[0] if lonlat else None,
            "lat": lonlat[1] if lonlat else None,
        }
        booklet_rec = lookup_unit(booklet, ids, name)
        unit["bookletPage"] = booklet_rec["bookletPage"] if booklet_rec else None
        unit["bookletPdfPage"] = booklet_rec["bookletPdfPage"] if booklet_rec else None
        unit["bookletUrl"] = tpwd_url(booklet_rec["bookletUrl"] if booklet_rec else BOOKLET_URL)
        units.append(unit)
        if geom is not None:
            unit_geoms[feature_id] = geom
            region_geoms.setdefault(region, []).append(geom)

        for item in classified:
            methods = list(item["methods"])
            used_general_dates = False
            if item["species"] in {"white_tailed_deer", "mule_deer", "feral_hog", "coyote"}:
                methods, used_general_dates = apply_general_means(
                    methods, item["sourceTag"], general_means
                )
            if pdf_methods and item["species"] == "white_tailed_deer" and "any_legal" in methods:
                methods = pdf_methods
            for method in methods:
                wins: list[dict[str, str]] = []
                date_source = "county_default"
                source_county = ""
                if pdf_sections and item["species"] == "white_tailed_deer" and pdf_methods:
                    date_source = "unit_pdf"
                date_method = "firearm" if used_general_dates and method != "archery" else method
                for page in county_pages:
                    found = windows_from_county(page, item["species"], date_method, item["access"])
                    if found:
                        wins = found
                        source_county = page["county"]
                        if date_source != "unit_pdf":
                            date_source = "county"
                        break
                if not wins:
                    wins = windows_for(item["species"], date_method, region, item["access"])
                    date_source = "unit_pdf" if date_source == "unit_pdf" else "county_default"
                for win in wins:
                    opp_id += 1
                    opportunities.append(
                        {
                            "id": f"o{opp_id}",
                            "unitId": feature_id,
                            "species": item["species"],
                            "speciesLabel": item["speciesLabel"],
                            "methods": [method],
                            "access": item["access"],
                            "start": win["start"],
                            "end": win["end"],
                            "dateSource": date_source,
                            "county": source_county,
                            "notes": item["sourceTag"],
                        }
                    )
        unit["methods"] = sorted(
            {m for o in opportunities if o["unitId"] == feature_id for m in o["methods"]}
        ) or methods_set

    features = []
    for unit in units:
        geom = unit_geoms.get(unit["id"])
        if geom is not None:
            geometry = geom_to_geojson(geom)
        elif unit["lon"] is not None:
            geometry = {"type": "Point", "coordinates": [round(unit["lon"], 5), round(unit["lat"], 5)]}
        else:
            continue
        props = {k: v for k, v in unit.items() if k not in {"lon", "lat"}}
        props["lon"] = unit["lon"]
        props["lat"] = unit["lat"]
        features.append({"type": "Feature", "id": unit["id"], "properties": props, "geometry": geometry})

    region_features = []
    colors = {
        "Panhandle": "#c4a35a",
        "Dallas/Ft. Worth": "#7aa2c4",
        "Austin/Waco": "#6b8f71",
        "Central Texas": "#8f6b4a",
        "Pineywoods": "#2f6b4f",
        "Houston/Beaumont": "#3d7a8c",
        "San Antonio/Corpus Christi": "#b56b4a",
        "Trans-Pecos": "#8a6f9b",
    }
    for region, geoms in region_geoms.items():
        merged = dissolve(geoms, simplify=0.012)
        if merged is None:
            continue
        c = centroid_point(merged)
        region_features.append(
            {
                "type": "Feature",
                "id": region,
                "properties": {
                    "name": region,
                    "unitCount": len(geoms),
                    "color": colors.get(region, "#6b8f71"),
                    "lon": c.x if c else None,
                    "lat": c.y if c else None,
                },
                "geometry": geom_to_geojson(merged, ndigits=4),
            }
        )

    species_in_use = sorted({o["species"] for o in opportunities if o["species"] != "fishing"})
    meta = {
        "seasonYear": SEASON_YEAR,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "unitCount": len(units),
        "opportunityCount": len(opportunities),
        "polygonCount": sum(1 for f in features if f["geometry"]["type"] != "Point"),
        "disclaimer": (
            "Unofficial planning aid compiled from Texas Parks and Wildlife Department public data. "
            "Regulations, dates, and boundaries change. Confirm every hunt with the current Public "
            "Hunting Lands Map Booklet / unit PDF and the Outdoor Annual before you go."
        ),
        "sources": [
            {
                "name": "APH Area/Legal Game search (2026-27)",
                "url": "https://tpwd.texas.gov/huntwild/hunt/public/annual_public_hunting/search.phtml",
            },
            {
                "name": "2026-27 Public Hunt Area Details KMZ",
                "url": "https://tpwd.texas.gov/huntwild/hunt/public/annual_public_hunting/resources/map/PublicHuntAreasDetailsKMZ2026-27.zip",
            },
            {
                "name": "Outdoor Annual seasons by county",
                "url": "https://tpwd.texas.gov/regulations/outdoor-annual/regs/counties/anderson",
            },
            {
                "name": "2026-27 Public Hunting Lands Map Booklet",
                "url": BOOKLET_URL,
            },
            {
                "name": "TPWD Public Hunt Locator Map (ArcGIS)",
                "url": "https://tpwd.texas.gov/server/rest/services/Wildlife/TPWD_PublicHuntLocatorMap/MapServer",
            },
        ],
        "species": [{"id": k, "label": SPECIES[k]} for k in species_in_use],
        "methods": [
            {"id": "archery", "label": "Archery"},
            {"id": "firearm", "label": "Firearm / rifle"},
            {"id": "muzzleloader", "label": "Muzzleloader"},
            {"id": "shotgun", "label": "Shotgun"},
            {"id": "any_legal", "label": "Any legal means"},
        ],
        "access": [
            {"id": "aph_walk_in", "label": "APH walk-in"},
            {"id": "youth", "label": "Youth"},
            {"id": "youth_adult", "label": "Youth/adult"},
            {"id": "e_postcard", "label": "E-Postcard"},
            {"id": "regular_permit", "label": "Regular (daily) permit"},
            {"id": "drawn", "label": "Drawn / special permit"},
        ],
        "regions": sorted({u["region"] for u in units if u["region"]}),
        "counties": sorted({c for u in units for c in u["counties"]}),
        "countiesWithCalendars": sum(1 for u in units if u.get("countySlugs")),
        "unitsWithBookletPage": sum(1 for u in units if u.get("bookletPage")),
        "bookletUrl": BOOKLET_URL,
    }

    DATA.mkdir(parents=True, exist_ok=True)
    WEB_DATA.mkdir(parents=True, exist_ok=True)
    payload = {
        "units.geojson": {"type": "FeatureCollection", "features": features},
        "regions.geojson": {"type": "FeatureCollection", "features": region_features},
        "opportunities.json": opportunities,
        "units.json": units,
        "seasons.json": default_calendar(),
        "counties.json": {
            page["slug"]: page
            for page in county_index.values()
            if isinstance(page, dict) and page.get("slug")
        },
        "meta.json": meta,
    }
    for name, obj in payload.items():
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        (DATA / name).write_text(text)
        (WEB_DATA / name).write_text(text)

    sources_md = [
        "# Data sources",
        "",
        f"Season: **{SEASON_YEAR}** (September 1, 2026 – August 31, 2027).",
        f"Generated: {meta['generatedAt']}",
        "",
        "This dataset is an unofficial compilation. TPWD publications remain authoritative.",
        "",
    ]
    for src in meta["sources"]:
        sources_md.append(f"- [{src['name']}]({src['url']})")
    sources_md += [
        "",
        f"- Units: {meta['unitCount']}",
        f"- Hunt opportunities (species × method × date window): {meta['opportunityCount']}",
        f"- Units with polygons: {meta['polygonCount']}",
        f"- Units with county Outdoor Annual calendars: {meta.get('countiesWithCalendars', 0)}",
        f"- Units with Map Booklet page numbers: {meta.get('unitsWithBookletPage', 0)}",
        "",
        "Unit map PDFs are not republished here; each unit links to the official TPWD PDF.",
        "",
    ]
    (DATA / "SOURCES.md").write_text("\n".join(sources_md))
    print(
        f"wrote {len(units)} units, {len(opportunities)} opportunities, "
        f"{meta['polygonCount']} polygons, {len(region_features)} regions"
    )


if __name__ == "__main__":
    build()
