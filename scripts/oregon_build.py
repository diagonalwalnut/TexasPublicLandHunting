"""Compile the admin Oregon hunting beta from ODFW public sources.

Downloads wildlife-management-unit and eastern deer-hunt-area polygons,
parses 2026 controlled-hunt rows from the big-game regulations text, and
writes simplified JSON/GeoJSON under data/oregon and web/public/data/oregon.

Regulations text is the markdown extraction of the 2026 ODFW big-game booklet.
Pass --text if you already have it; otherwise the script downloads the PDF
and extracts text with PyMuPDF.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from shapely.geometry import mapping, shape

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "oregon"
WEB = ROOT / "web" / "public" / "data" / "oregon"
CACHE = ROOT / "cache" / "oregon"

WMU_QUERY = (
    "https://nrimp.dfw.state.or.us/arcgis/rest/services/ODFW_Admin/"
    "WildlifeManagementUnits/FeatureServer/0/query?where=1%3D1"
    "&outFields=UNIT_NUM,UNIT_NAME,Acres,REGION&returnGeometry=true&outSR=4326&f=geojson"
)
DHA_QUERY = (
    "https://nrimp.dfw.state.or.us/arcgis/rest/services/ORHAM/"
    "ODFW_Eastern_Oregon_Deer_Hunt_Areas/FeatureServer/0/query?where=1%3D1"
    "&outFields=HerdRange,HuntArea&returnGeometry=true&outSR=4326&f=geojson"
)
BIG_GAME_PDF = (
    "https://www.eregulations.com/assets/docs/resources/OR/"
    "26ORHD_LR3_2026-03-03-202905_asij.pdf"
)
REGS_URL = "https://www.eregulations.com/oregon/hunting"
GAME_BIRD_URL = "https://www.eregulations.com/oregon/hunting/game-bird/game-bird-seasons"
MIGRATORY_URL = "https://www.eregulations.com/oregon/hunting/game-bird/migratory-game-bird-seasons"
SEASONS_URL = "https://myodfw.com/big-game-hunting/seasons"
BUY_URL = "https://myodfw.com"
DRAW_URL = "https://myodfw.com/articles/controlled-hunt-navigation"
EAST_DEER_URL = "https://myodfw.com/articles/eastern-oregon-deer-hunts"

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

SECTION_RE = re.compile(
    r"^(?:#{1,3}\s*)?(ANY LEGAL WEAPON|ARCHERY|MUZZLELOADER|YOUTH ONLY).*(CONTROLLED|DEER HUNTS|ELK HUNTS|BIGHORN|GOAT)",
    re.I,
)
HUNT_RE = re.compile(
    r"(?<![A-Z0-9])((?:[A-Z]{2}\d{3}(?:-\d+|[A-Z]\d*)?)|(?:(?!19\d\d)(?!20\d\d)\d{3}(?:[A-Z]\d*)?)|(?:[LMN]\d{2}[A-Z]?\d*))(?![A-Z0-9])"
)
DATE_RE = re.compile(
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(\d{1,2})"
    r"\s*[-–]\s*"
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\.?\s+(\d{1,2})(?:,\s*(\d{4}))?",
    re.I,
)

SERIES_SPECIES = {
    "100": ("deer", "Deer"),
    "200": ("elk", "Elk"),
    "400": ("pronghorn", "Pronghorn"),
    "500": ("bighorn_sheep", "Bighorn sheep"),
    "600": ("deer", "Deer"),
    "700": ("black_bear", "Black bear"),
    "900": ("mountain_goat", "Rocky Mountain goat"),
    "L": ("deer", "Deer"),
    "M": ("elk", "Elk"),
    "N": ("pronghorn", "Pronghorn"),
}


def fetch(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1000:
        return
    req = urllib.request.Request(url, headers={"User-Agent": "oregon-hunt-beta/1.0"})
    with urllib.request.urlopen(req, timeout=120) as res:
        dest.write_bytes(res.read())


def simplify_feature(feature: dict, props: dict) -> dict:
    geom = shape(feature["geometry"]).simplify(0.004, preserve_topology=True)
    return {"type": "Feature", "id": props["id"], "properties": props, "geometry": mapping(geom)}


def title_name(raw: str) -> str:
    return " ".join(part.capitalize() if part.isupper() else part for part in raw.split())


def iso_date(month: str, day: str, year: int | None, start_month: int | None) -> tuple[str, int]:
    m = MONTHS[month.lower().rstrip(".")]
    y = year if year else 2026
    if year is None and start_month is not None and m < start_month:
        y = 2026 + 1
    return f"{y:04d}-{m:02d}-{int(day):02d}", m


def section_context(header: str) -> dict | None:
    h = header.upper()
    if "100 SERIES" in h:
        series = "100"
    elif "600 SERIES" in h:
        series = "600"
    elif "200 SERIES" in h:
        series = "200"
    elif "400 SERIES" in h:
        series = "400"
    elif "700 SERIES" in h:
        series = "700"
    elif "BIGHORN" in h:
        series = "500"
    elif "ROCKY MTN GOAT" in h or "ROCKY MOUNTAIN GOAT" in h:
        series = "900"
    elif "DEER HUNTS" in h:
        series = "L"
    elif "ELK HUNTS" in h:
        series = "M"
    else:
        return None
    if "ARCHERY" in h:
        methods = ["archery"]
    elif "MUZZLELOADER" in h:
        methods = ["muzzleloader"]
    else:
        methods = ["any_legal"]
    species, label = SERIES_SPECIES[series]
    access = "premium" if series in {"L", "M", "N"} else "controlled_draw"
    if "YOUTH" in h:
        access = "youth_draw"
    return {
        "series": series,
        "species": species,
        "speciesLabel": label,
        "methods": methods,
        "access": access,
        "youth": "YOUTH" in h,
    }


def flatten(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\|", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text


def parse_controlled(text: str) -> list[dict]:
    hunts: list[dict] = []
    ctx: dict | None = None
    seen: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("| ---"):
            continue
        header = re.sub(r"^#+\s*", "", line)
        if SECTION_RE.match(header) and "CONTINUED" not in header.upper():
            nxt = section_context(header)
            if nxt:
                ctx = nxt
            continue
        if ctx is None:
            continue
        flat = flatten(line)
        flat = re.sub(r"HUNT\s*#\s*HUNT NAME.*?APPLICANTS", " ", flat, flags=re.I)
        for match in HUNT_RE.finditer(flat):
            number = match.group(1)
            if number in seen:
                continue
            tail = flat[match.end() :]
            date = DATE_RE.search(tail)
            if not date:
                continue
            before = tail[: date.start()].strip(" *-")
            bag_at = re.search(r"\bOne\b", before, re.I)
            if not bag_at:
                continue
            name = re.sub(r"\s+", " ", before[: bag_at.start()]).strip(" -*")
            bag = re.sub(r"\s+", " ", before[bag_at.start() :]).strip(" -*")
            if len(name) < 3 or len(name) > 80 or len(bag) > 160:
                continue
            if re.match(r"^(NEW\b|\d)", name, re.I):
                continue
            if not re.search(r"[A-Za-z]{3,}", name):
                continue
            start, sm = iso_date(date.group(1), date.group(2), None, None)
            end, _ = iso_date(date.group(3), date.group(4), int(date.group(5)) if date.group(5) else None, sm)
            after = tail[date.end() :]
            nums = re.findall(r"\d[\d,]*|NEW", after)
            tags = None
            applicants = None
            if nums:
                token = nums[0].replace(",", "")
                if token != "NEW":
                    tags = int(token)
                if len(nums) > 1 and nums[1] != "NEW":
                    applicants = int(nums[1].replace(",", ""))
            methods = list(ctx["methods"])
            notes = []
            if "*" in name or "*" in bag:
                notes.append("Boundary is not the entire unit or hunt area. Confirm the written description.")
            if "traditional" in name.lower():
                notes.append("Traditional bow only (long bow or recurve).")
            if "shotgun" in name.lower() and "muzzleloader" in name.lower():
                methods = ["shotgun", "muzzleloader"]
            seen.add(number)
            hunts.append(
                {
                    "id": f"ctrl-{number}",
                    "huntNumber": number,
                    "name": name,
                    "species": ctx["species"],
                    "speciesLabel": ctx["speciesLabel"],
                    "series": ctx["series"],
                    "methods": methods,
                    "access": ctx["access"],
                    "bagLimit": bag,
                    "start": start,
                    "end": end,
                    "tag": tag_for(ctx),
                    "tagSaleDeadline": None,
                    "applicationDeadline": "2026-02-10" if ctx["series"] == "700" else "2026-05-15",
                    "tags2026": tags,
                    "firstChoiceApplicants2025": applicants,
                    "scope": "linked",
                    "unitIds": [],
                    "restrictions": notes,
                    "notes": "Controlled hunt. Tag sale deadline is the day before the hunt opens.",
                }
            )
    return hunts


def tag_for(ctx: dict) -> str:
    series = ctx["series"]
    if series == "100":
        return "Controlled 100 Series Deer Tag"
    if series == "600":
        return "Controlled 600 Series Deer Tag"
    if series == "200":
        return "Controlled 200 Series Elk Tag"
    if series == "400":
        return "Controlled Pronghorn Antelope Tag"
    if series == "500":
        return "Controlled Bighorn Sheep Tag"
    if series == "700":
        return "Controlled Spring Bear Tag"
    if series == "900":
        return "Controlled Rocky Mountain Goat Tag"
    if series == "L":
        return "Premium deer tag"
    if series == "M":
        return "Premium elk tag"
    return "Controlled hunt tag"


def link_units(hunt: dict, wmu_ids: set[str], area_ids: set[str]) -> None:
    number = hunt["huntNumber"] or ""
    area = re.match(r"^([A-Z]{2})(\d{3})", number)
    if area:
        code = f"{area.group(1)}-{area.group(2)[1:]}"
        uid = f"dha:{code}"
        if uid in area_ids:
            hunt["unitIds"] = [uid]
            return
    premium = re.match(r"^[LMN](\d{2})", number)
    numeric = re.match(r"^(\d)(\d{2})", number)
    unit_num = None
    if premium:
        unit_num = int(premium.group(1))
    elif numeric and hunt["series"] in {"100", "200", "400", "600", "700"}:
        unit_num = int(numeric.group(2))
    if unit_num is not None:
        uid = f"wmu:{unit_num}"
        if uid in wmu_ids:
            hunt["unitIds"] = [uid]


def general_hunt(**kwargs) -> dict:
    base = {
        "huntNumber": None,
        "tags2026": None,
        "firstChoiceApplicants2025": None,
        "applicationDeadline": None,
        "restrictions": ["No hunting seasons on national park or tribal reservation lands inside these areas."],
        "scope": "units",
    }
    base.update(kwargs)
    return base


def general_seasons(wmu_ids: set[str]) -> list[dict]:
    west = [f"wmu:{n}" for n in range(10, 31) if f"wmu:{n}" in wmu_ids]
    cascades = [f"wmu:{n}" for n in (16, 19, 21, 22, 29, 30) if f"wmu:{n}" in wmu_ids]
    coast_first = [f"wmu:{n}" for n in (11, 12, 14, 15, 17, 18, 20, 23, 28) if f"wmu:{n}" in wmu_ids]
    coast_bull = [f"wmu:{n}" for n in (11, 15, 17, 18, 23, 28) if f"wmu:{n}" in wmu_ids]
    coast_spike = [f"wmu:{n}" for n in (12, 14, 20) if f"wmu:{n}" in wmu_ids]
    archery_buck = [f"wmu:{n}" for n in (11, 12, 14, 22, 24, 27, 28) if f"wmu:{n}" in wmu_ids]
    archery_either = [f"wmu:{n}" for n in (15, 16, 19, 21) if f"wmu:{n}" in wmu_ids]
    archery_late = [f"wmu:{n}" for n in (25, 29, 30, 23) if f"wmu:{n}" in wmu_ids]
    powers = [f"wmu:{n}" for n in (26,) if f"wmu:{n}" in wmu_ids]
    late_trad = [f"wmu:{n}" for n in (10, 17, 18, 20) if f"wmu:{n}" in wmu_ids]
    elk_arch_either = [f"wmu:{n}" for n in (15, 20, 23, 25, 28) if f"wmu:{n}" in wmu_ids]
    elk_arch_bull = [f"wmu:{n}" for n in (11, 12, 14, 17, 18, 27) if f"wmu:{n}" in wmu_ids]
    elk_arch_cascade = [f"wmu:{n}" for n in (16, 19, 21, 22, 29, 30) if f"wmu:{n}" in wmu_ids]
    elk_arch_3pt = [f"wmu:{n}" for n in (10, 24) if f"wmu:{n}" in wmu_ids]
    elk_arch_east_either = [f"wmu:{n}" for n in (35, 38, 40, 41, 42, 43, 44, 45, 64, 67, 68, 69, 70, 71, 73) if f"wmu:{n}" in wmu_ids]
    elk_arch_east_bull = [f"wmu:{n}" for n in (31, 32, 33, 34, 39, 74, 75, 76) if f"wmu:{n}" in wmu_ids]
    squirrel_north = [f"wmu:{n}" for n in (34, 35, 39, 41, 42) if f"wmu:{n}" in wmu_ids]
    all_managed = sorted(uid for uid in wmu_ids if uid != "wmu:0")
    damage_full = [f"wmu:{n}" for n in (15, 23, 40, 43, 44) if f"wmu:{n}" in wmu_ids]
    rows = [
        general_hunt(
            id="gen-deer-alw-west",
            name="Western Oregon general buck deer",
            species="deer",
            speciesLabel="Deer",
            series="general",
            methods=["any_legal"],
            access="general_otc",
            bagLimit="One buck with visible antler",
            start="2026-10-03",
            end="2026-11-06",
            tag="General Any Legal Weapon Western Oregon Tag",
            tagSaleDeadline="2026-10-02",
            unitIds=west,
            notes="Eastern Oregon any-legal-weapon deer is controlled hunts only, on deer hunt areas.",
        ),
        general_hunt(
            id="gen-deer-alw-west-youth",
            name="Western Oregon youth deer extension",
            species="deer",
            speciesLabel="Deer",
            series="general",
            methods=["any_legal"],
            access="youth",
            bagLimit="One buck with visible antler",
            start="2026-11-07",
            end="2026-11-08",
            tag="Unfilled general any-legal-weapon western deer tag, or unfilled 119A",
            tagSaleDeadline="2026-10-02",
            unitIds=west,
            notes="Youth 12–17 only. Mentored youth program participants are not eligible.",
        ),
        general_hunt(
            id="gen-deer-arch-west-buck",
            name="Western Oregon general archery deer",
            species="deer",
            speciesLabel="Deer",
            series="general",
            methods=["archery"],
            access="general_otc",
            bagLimit="One buck with visible antler",
            start="2026-08-29",
            end="2026-09-27",
            tag="General Archery Season Western Oregon Deer Tag",
            tagSaleDeadline="2026-08-28",
            unitIds=archery_buck,
            notes="Units 11, 12, 14, 22, 24, 27, and 28.",
        ),
        general_hunt(
            id="gen-deer-arch-west-either",
            name="Western Oregon general archery deer",
            species="deer",
            speciesLabel="Deer",
            series="general",
            methods=["archery"],
            access="general_otc",
            bagLimit="One deer",
            start="2026-08-29",
            end="2026-09-27",
            tag="General Archery Season Western Oregon Deer Tag",
            tagSaleDeadline="2026-08-28",
            unitIds=archery_either,
            notes="Units 15, 16, 19, and the northern portion of unit 21. South Indigo has its own boundary.",
        ),
        general_hunt(
            id="gen-deer-arch-late",
            name="Western Oregon late general archery deer",
            species="deer",
            speciesLabel="Deer",
            series="general",
            methods=["archery"],
            access="general_otc",
            bagLimit="One buck with visible antler, except one deer in unit 23",
            start="2026-08-29",
            end="2026-12-06",
            tag="General Archery Season Western Oregon Deer Tag",
            tagSaleDeadline="2026-08-28",
            unitIds=archery_late,
            notes="Open Aug. 29–Sept. 27 and Nov. 14–Dec. 6. White-tailed deer are legal in Melrose (23) only when the bag limit says so.",
            restrictions=["Season is split: Aug. 29–Sept. 27 and Nov. 14–Dec. 6, not the days in between."],
        ),
        general_hunt(
            id="gen-deer-arch-powers",
            name="Powers unit general archery deer",
            species="deer",
            speciesLabel="Deer",
            series="general",
            methods=["archery"],
            access="general_otc",
            bagLimit="One buck with visible antler",
            start="2026-08-29",
            end="2026-12-06",
            tag="General Archery Season Western Oregon Deer Tag",
            tagSaleDeadline="2026-08-28",
            unitIds=powers,
            notes="Aug. 29–Sept. 27 any legal archery weapon. Nov. 14–Dec. 6 traditional archery equipment only.",
            restrictions=["Late segment is traditional archery equipment only."],
        ),
        general_hunt(
            id="gen-deer-arch-late-trad",
            name="Western Oregon late archery deer",
            species="deer",
            speciesLabel="Deer",
            series="general",
            methods=["archery"],
            access="general_otc",
            bagLimit="One buck with visible antler",
            start="2026-08-29",
            end="2026-12-13",
            tag="General Archery Season Western Oregon Deer Tag",
            tagSaleDeadline="2026-08-28",
            unitIds=late_trad,
            notes="Open Aug. 29–Sept. 27 and Nov. 21–Dec. 13 in units 10, 17, 18, and 20.",
            restrictions=["Season is split: Aug. 29–Sept. 27 and Nov. 21–Dec. 13."],
        ),
        general_hunt(
            id="gen-elk-cascade",
            name="West Cascade general bull elk",
            species="elk",
            speciesLabel="Elk",
            series="general",
            methods=["any_legal"],
            access="general_otc",
            bagLimit="One bull elk",
            start="2026-11-07",
            end="2026-11-13",
            tag="General West Cascade Tag",
            tagSaleDeadline="2026-11-06",
            unitIds=cascades,
            notes="Units 16, 19, 21, 22, 29, and 30.",
        ),
        general_hunt(
            id="gen-elk-coast-1",
            name="Coast bull elk, first season",
            species="elk",
            speciesLabel="Elk",
            series="general",
            methods=["any_legal"],
            access="general_otc",
            bagLimit="One bull elk",
            start="2026-11-14",
            end="2026-11-17",
            tag="General Western Oregon Coast First Season Tag",
            tagSaleDeadline="2026-11-13",
            unitIds=coast_first,
            notes="Units 11, 12, 14, 15, 17, 18, 20, 23, and 28.",
        ),
        general_hunt(
            id="gen-elk-coast-2-bull",
            name="Coast elk, second season (bull)",
            species="elk",
            speciesLabel="Elk",
            series="general",
            methods=["any_legal"],
            access="general_otc",
            bagLimit="One bull elk",
            start="2026-11-21",
            end="2026-11-27",
            tag="General Western Oregon Coast Second Season Tag",
            tagSaleDeadline="2026-11-20",
            unitIds=coast_bull,
            notes="Units 11, 15, 17, 18, 23, and 28.",
        ),
        general_hunt(
            id="gen-elk-coast-2-spike",
            name="Coast elk, second season (spike)",
            species="elk",
            speciesLabel="Elk",
            series="general",
            methods=["any_legal"],
            access="general_otc",
            bagLimit="One spike elk",
            start="2026-11-21",
            end="2026-11-27",
            tag="General Western Oregon Coast Second Season Tag",
            tagSaleDeadline="2026-11-20",
            unitIds=coast_spike,
            notes="Units 12, 14, and 20.",
        ),
        general_hunt(
            id="gen-elk-rm-2",
            name="Rocky Mountain elk, second general season",
            species="elk",
            speciesLabel="Elk",
            series="general",
            methods=["any_legal"],
            access="general_otc",
            bagLimit="One spike elk",
            start="2026-11-07",
            end="2026-11-15",
            tag="General Eastern Oregon Rocky Mountain Second Season Tag",
            tagSaleDeadline="2026-11-06",
            unitIds=[f"wmu:{n}" for n in (48, 49, 50, 51, 52, 53, 61, 62, 63) if f"wmu:{n}" in wmu_ids],
            notes="Valid in units 49, 50, 52, 53, 61, 62, 63, unit 48 north and west of the North Fork John Day River, and unit 51 north of Hwy 245 and Burnt River Canyon Rd. Other eastern units are controlled.",
            restrictions=["Portions of units 48 and 51 only. Confirm the boundary before hunting."],
        ),
        general_hunt(
            id="gen-elk-arch-either",
            name="General archery elk",
            species="elk",
            speciesLabel="Elk",
            series="general",
            methods=["archery"],
            access="general_otc",
            bagLimit="One elk",
            start="2026-08-29",
            end="2026-09-27",
            tag="General Archery Season Tag",
            tagSaleDeadline="2026-08-28",
            unitIds=elk_arch_either,
            notes="Some eastern units are controlled archery only.",
        ),
        general_hunt(
            id="gen-elk-arch-bull",
            name="General archery elk",
            species="elk",
            speciesLabel="Elk",
            series="general",
            methods=["archery"],
            access="general_otc",
            bagLimit="One bull elk",
            start="2026-08-29",
            end="2026-09-27",
            tag="General Archery Season Tag",
            tagSaleDeadline="2026-08-28",
            unitIds=elk_arch_bull,
            notes="",
        ),
        general_hunt(
            id="gen-elk-arch-cascade",
            name="General archery elk, Cascade",
            species="elk",
            speciesLabel="Elk",
            series="general",
            methods=["archery"],
            access="general_otc",
            bagLimit="One bull elk, except one elk outside National Forest lands",
            start="2026-08-29",
            end="2026-09-27",
            tag="General Archery Season Tag",
            tagSaleDeadline="2026-08-28",
            unitIds=elk_arch_cascade,
            notes="Units 16, 19, 21, 22, 29, and 30.",
        ),
        general_hunt(
            id="gen-elk-arch-3pt",
            name="General archery elk",
            species="elk",
            speciesLabel="Elk",
            series="general",
            methods=["archery"],
            access="general_otc",
            bagLimit="One bull elk, 3 point or better",
            start="2026-08-29",
            end="2026-09-27",
            tag="General Archery Season Tag",
            tagSaleDeadline="2026-08-28",
            unitIds=elk_arch_3pt,
            notes="Units 10 and 24.",
        ),
        general_hunt(
            id="gen-elk-arch-east-either",
            name="Eastern general archery elk",
            species="elk",
            speciesLabel="Elk",
            series="general",
            methods=["archery"],
            access="general_otc",
            bagLimit="One elk",
            start="2026-08-29",
            end="2026-09-27",
            tag="General Archery Season Tag",
            tagSaleDeadline="2026-08-28",
            unitIds=elk_arch_east_either,
            notes="Also includes the southern portion of unit 51, the eastern portion of 65, the southern portion of 66, and unit 77 east of Hwy 97. Some eastern units are controlled only.",
            restrictions=["Several units are partial. Confirm the 2026 regulations map."],
        ),
        general_hunt(
            id="gen-elk-arch-east-bull",
            name="Eastern general archery elk",
            species="elk",
            speciesLabel="Elk",
            series="general",
            methods=["archery"],
            access="general_otc",
            bagLimit="One bull elk",
            start="2026-08-29",
            end="2026-09-27",
            tag="General Archery Season Tag",
            tagSaleDeadline="2026-08-28",
            unitIds=elk_arch_east_bull,
            notes="Also includes the portion of unit 77 west of Hwy 97.",
        ),
        general_hunt(
            id="gen-elk-damage-long",
            name="General antlerless elk damage",
            species="elk",
            speciesLabel="Elk",
            series="general",
            methods=["any_legal"],
            access="general_otc",
            bagLimit="One antlerless elk",
            start="2026-08-01",
            end="2027-03-31",
            tag="General Season Antlerless Elk Damage Tag",
            tagSaleDeadline=None,
            unitIds=damage_full,
            notes="Over the counter. No tag sale deadline. Mostly private land. Also valid in portions of other units; see the boundary descriptions.",
            restrictions=["Do not buy this tag unless you already have access. ODFW will not find a place to hunt."],
        ),
        general_hunt(
            id="gen-bear",
            name="General fall black bear",
            species="black_bear",
            speciesLabel="Black bear",
            series="general",
            methods=["any_legal"],
            access="general_otc",
            bagLimit="One bear",
            start="2026-08-01",
            end="2026-12-31",
            tag="General Season Fall Tag",
            tagSaleDeadline="2026-10-02",
            unitIds=all_managed,
            notes="Statewide, except closed lands. An additional fall tag has no sale deadline after the general tag is purchased.",
        ),
        general_hunt(
            id="gen-bear-additional",
            name="Additional fall black bear",
            species="black_bear",
            speciesLabel="Black bear",
            series="general",
            methods=["any_legal"],
            access="additional",
            bagLimit="One bear",
            start="2026-08-01",
            end="2026-12-31",
            tag="Additional General Season Fall Tag",
            tagSaleDeadline=None,
            unitIds=all_managed,
            notes="Requires the general-season fall bear tag first.",
        ),
        general_hunt(
            id="gen-cougar",
            name="General cougar",
            species="cougar",
            speciesLabel="Cougar",
            series="general",
            methods=["any_legal"],
            access="general_otc",
            bagLimit="One cougar",
            start="2026-01-01",
            end="2026-12-31",
            tag="General Season Cougar Tag",
            tagSaleDeadline="2026-10-02",
            unitIds=all_managed,
            notes="Statewide. An additional cougar tag has no sale deadline after the general tag is purchased.",
        ),
        general_hunt(
            id="gen-cougar-additional",
            name="Additional cougar",
            species="cougar",
            speciesLabel="Cougar",
            series="general",
            methods=["any_legal"],
            access="additional",
            bagLimit="One cougar",
            start="2026-01-01",
            end="2026-12-31",
            tag="Additional General Season Cougar Tag",
            tagSaleDeadline=None,
            unitIds=all_managed,
            notes="Requires the general-season cougar tag first.",
        ),
        general_hunt(
            id="gen-squirrel-north",
            name="Western gray squirrel, north-central",
            species="gray_squirrel",
            speciesLabel="Western gray squirrel",
            series="general",
            methods=["any_legal"],
            access="no_tag",
            bagLimit="See the game-mammal regulations",
            start="2026-09-15",
            end="2026-10-31",
            tag="No tag. Hunting license required for ages 12 and older.",
            tagSaleDeadline=None,
            unitIds=squirrel_north,
            notes="Units 34, 35, 39, 41, and 42.",
        ),
        general_hunt(
            id="gen-squirrel-rest",
            name="Western gray squirrel",
            species="gray_squirrel",
            speciesLabel="Western gray squirrel",
            series="general",
            methods=["any_legal"],
            access="no_tag",
            bagLimit="See the game-mammal regulations. No bag limit in part of the Rogue unit south of the Rogue River and north of Hwy 140.",
            start="2026-09-01",
            end="2026-11-15",
            tag="No tag. Hunting license required for ages 12 and older.",
            tagSaleDeadline=None,
            unitIds=[f"wmu:{n}" for n in list(range(10, 34)) + list(range(36, 39)) + [40] + list(range(43, 78)) if f"wmu:{n}" in wmu_ids],
            notes="Units 10–33, 36–38, 40, and 43–77.",
        ),
    ]
    return rows


def game_birds(wmu_ids: set[str]) -> list[dict]:
    west = sorted(uid for uid in wmu_ids if uid.startswith("wmu:"))
    # Region split is applied later from unit records. Here, store scope.
    def row(hid, name, species, label, start, end, bag, area, methods, notes, access="validation"):
        return {
            "id": hid,
            "huntNumber": None,
            "name": name,
            "species": species,
            "speciesLabel": label,
            "series": "game_bird",
            "methods": methods,
            "access": access,
            "bagLimit": bag,
            "start": start,
            "end": end,
            "tag": "Hunting license plus the validation named in the notes",
            "tagSaleDeadline": None,
            "applicationDeadline": None,
            "tags2026": None,
            "firstChoiceApplicants2025": None,
            "scope": area,
            "unitIds": west if area in {"statewide", "western", "eastern"} else [],
            "restrictions": [
                "Shotgun, archery, and other methods legal for game birds. Non-toxic shot is required for waterfowl.",
            ],
            "notes": notes,
        }

    return [
        row("gb-grouse", "Ruffed and blue grouse", "grouse", "Forest grouse", "2026-09-01", "2027-01-31", "3 of each species daily", "statewide", ["shotgun", "archery"], "Upland game bird validation, age 18 and older. Statewide."),
        row("gb-partridge", "Chukar and Hungarian partridge", "partridge", "Partridge", "2026-10-10", "2027-01-31", "8 combined daily (2 chukar in the Lower Klamath Hills)", "statewide", ["shotgun", "archery"], "Upland validation. Statewide."),
        row("gb-pheasant", "Rooster pheasant", "pheasant", "Pheasant", "2026-10-10", "2026-12-31", "2 roosters daily", "statewide", ["shotgun", "archery"], "Upland validation. Statewide, plus separate western Oregon fee pheasant hunts."),
        row("gb-quail-west", "Quail, western Oregon", "quail", "Quail", "2026-09-01", "2027-01-31", "10 California and mountain quail combined", "western", ["shotgun", "archery"], "Upland validation."),
        row("gb-quail-east", "Quail, eastern Oregon", "quail", "Quail", "2026-10-10", "2027-01-31", "10 combined, no more than 2 mountain quail", "eastern", ["shotgun", "archery"], "Upland validation."),
        row("gb-turkey-spring", "Spring wild turkey", "turkey", "Wild turkey", "2026-04-15", "2026-05-31", "Season bag is set by the number of turkey tags", "statewide", ["shotgun", "archery"], "Spring turkey tag. General season is over the counter."),
        row("gb-turkey-youth", "Youth spring turkey", "turkey", "Wild turkey", "2026-04-10", "2026-04-11", "Youth season bag follows the youth turkey rules", "statewide", ["shotgun", "archery"], "Youth hunters. See the game bird regulations.", "youth"),
        row("gb-dove-z1", "Mourning dove, zone 1", "dove", "Mourning dove", "2026-09-01", "2026-12-14", "15 daily", "migratory_zone_1", ["shotgun"], "Split season: Sept. 1–30 and Nov. 15–Dec. 14. Migratory bird validation / HIP. Zone lines are not wildlife-unit lines.", "validation"),
        row("gb-dove-z2", "Mourning dove, zone 2", "dove", "Mourning dove", "2026-09-01", "2026-10-30", "15 daily", "migratory_zone_2", ["shotgun"], "Zone 2 is Sept. 1–Oct. 30. Zone lines are not wildlife-unit lines."),
        row("gb-duck-z1", "Ducks, zone 1", "waterfowl", "Duck", "2026-10-17", "2027-01-31", "7 daily, with species caps inside that bag", "migratory_zone_1", ["shotgun"], "Split: Oct. 17–Nov. 1 and Nov. 5–Jan. 31, 2027. Non-toxic shot. Waterfowl validation and federal duck stamp when required. Scaup dates differ."),
        row("gb-duck-z2", "Ducks, zone 2", "waterfowl", "Duck", "2026-10-10", "2027-01-24", "7 daily, with species caps inside that bag", "migratory_zone_2", ["shotgun"], "Split: Oct. 10–Nov. 29 and Dec. 3–Jan. 24, 2027. Non-toxic shot."),
        row("gb-youth-wf", "Youth waterfowl", "waterfowl", "Waterfowl", "2026-09-26", "2026-09-27", "Youth waterfowl bag", "statewide", ["shotgun"], "Statewide youth days.", "youth"),
        row("gb-pigeon", "Band-tailed pigeon", "band_tailed_pigeon", "Band-tailed pigeon", "2026-09-15", "2026-09-23", "2 daily", "statewide", ["shotgun"], "Permit required."),
    ]


def licenses() -> dict:
    return {
        "title": "Oregon hunting licenses, tags, and draws",
        "seasonYear": "2026",
        "intro": "A hunting license is required before you buy most tags or enter a controlled-hunt draw. Fees below are the 2026 resident and nonresident amounts printed in the big-game regulations. Confirm the current fee before you pay.",
        "whereToBuy": [
            {
                "id": "internet",
                "title": "Internet",
                "body": "Buy at MyODFW.com. Choose electronic documents and carry them in the MyODFW app, or choose paper and print at home. You can buy the hunting license and submit a controlled-hunt application in the same session.",
            },
            {
                "id": "agent",
                "title": "License agent or ODFW office",
                "body": "License sales agents and ODFW offices that sell licenses can print documents or help you buy electronic ones. If an office changes a controlled-hunt application, a $2 handling fee applies each time. Online, the customer can change an application through May 25 with no extra fee.",
            },
            {
                "id": "mail",
                "title": "Mail",
                "body": "The 2026 regulations direct hunters to buy online or from an agent or ODFW office. ODFW does not list a general mail-order license counter in that booklet. Hunters who cannot use those channels should call Licensing at 503-947-6101.",
            },
            {
                "id": "otc",
                "title": "Over the counter",
                "body": "General-season deer, elk, bear, and cougar tags, and the antlerless elk damage tag, are sold over the counter to anyone with a valid hunting license, until the tag sale deadline (the damage tag has none). Leftover controlled tags, when offered, are a separate sale after the draw.",
            },
            {
                "id": "draw",
                "title": "Controlled hunt draw (lottery)",
                "body": "Limited-entry tags are a draw, not a first-come sale. Each application gets a random seven-digit number. For deer, elk, pronghorn, and spring bear (not premium hunts), 75% of tags go to first-choice applicants with the most preference points. The other 25% are random among all first-choice applicants. If tags remain, they go randomly through second to fifth choice. Preference points are not used for choices two through five. Bighorn sheep, Rocky Mountain goat, and premium hunts are 100% random and do not use preference points.",
            },
        ],
        "deadlines": [
            {"name": "Spring black bear application", "date": "2026-02-10", "detail": "Draw results by February 20."},
            {"name": "All other big game controlled applications", "date": "2026-05-15", "detail": "Draw results by June 12. Application changes online through May 25."},
            {"name": "Point-saver, if you skip the regular draw", "date": "2026-07-01", "detail": "July 1 through November 30. No other choices in that series."},
            {"name": "General deer or elk archery tag", "date": "2026-08-28", "detail": "Tag sale deadline."},
            {"name": "Western general deer, fall bear, cougar", "date": "2026-10-02", "detail": "Tag sale deadline. Additional bear and cougar tags have no deadline after the general tag is bought."},
            {"name": "West Cascade elk and Rocky Mountain elk, 2nd season", "date": "2026-11-06", "detail": "Tag sale deadline."},
            {"name": "Coast elk, first season", "date": "2026-11-13", "detail": "Tag sale deadline."},
            {"name": "Coast elk, second season", "date": "2026-11-20", "detail": "Tag sale deadline."},
            {"name": "Controlled deer, elk, pronghorn, sheep, goat tags", "date": None, "detail": "The day before that hunt begins. Sports Pac holders still redeem the voucher for the drawn hunt."},
        ],
        "huntSeries": [
            {"id": "100", "label": "Buck deer", "points": True},
            {"id": "200", "label": "Elk", "points": True},
            {"id": "400", "label": "Pronghorn", "points": True},
            {"id": "500", "label": "Bighorn sheep", "points": False},
            {"id": "600", "label": "Antlerless deer", "points": True},
            {"id": "700", "label": "Spring black bear", "points": True},
            {"id": "900", "label": "Rocky Mountain goat", "points": False},
            {"id": "L", "label": "Premium deer", "points": False},
            {"id": "M", "label": "Premium elk", "points": False},
            {"id": "N", "label": "Premium pronghorn", "points": False},
        ],
        "preferencePoints": [
            "Points are kept on your ODFW ID number, by hunt series, not by a single hunt number. A point earned on one 100-series deer hunt applies to a different 100-series first choice next year.",
            "Each year you do not draw your first choice, you receive one preference point for that series. If you draw the first choice, points return to zero even if you never buy the tag. Pioneer license holders, and resident disabled-veteran license holders age 65 or older, reset to one instead of zero.",
            "You may apply for up to five hunt choices in a series. Only the first choice uses preference points and the 25% random pool.",
            "A point-saver application earns a point when you will not hunt that series. You need a hunting license, and you cannot list other choices in that series. An LOP tag may be added as a sixth choice by May 15. Youth point-savers cannot also take a First Time Youth tag in the same series that year.",
            "Party applications average the members' points (0.51 and above rounds up). Everyone draws or nobody does. No party applications for bighorn sheep, Rocky Mountain goat, or premium hunts.",
            "Sheep and goat tags are once in a lifetime for rams and goats. Ewe hunts are exempt. There are no preference points for sheep, goat, or premium hunts.",
            "Nonresidents may receive at most 5% of controlled deer, elk, and bear tags and 3% of pronghorn tags. Sheep and goat nonresident tags are at least 5% and at most 10%.",
            "Mentored youth earn a separate banked point for each year they register. Redeemed points convert into the regular preference-point system.",
            "If you already bought a general-season deer or elk tag, you cannot apply in the 100 or 200 series for that species.",
        ],
        "fees": [
            {"item": "Resident hunting license", "resident": "$39", "nonresident": "$193"},
            {"item": "Resident Sports Pac", "resident": "$253", "nonresident": "Not offered"},
            {"item": "Resident combination hunting and angling", "resident": "$86", "nonresident": "Not offered"},
            {"item": "Youth combination license (12–17)", "resident": "$10", "nonresident": ""},
            {"item": "Deer tag", "resident": "$33", "nonresident": "$500"},
            {"item": "Elk tag", "resident": "$56", "nonresident": "$660"},
            {"item": "Pronghorn tag", "resident": "$58", "nonresident": "$443"},
            {"item": "Bighorn sheep or Rocky Mountain goat tag", "resident": "$159", "nonresident": "$1,695"},
            {"item": "Bear or cougar tag, including an additional tag", "resident": "$16.50", "nonresident": "$16.50"},
            {"item": "Controlled-hunt application", "resident": "$8 plus a $2 agent fee ($10)", "nonresident": "$8 plus a $2 agent fee ($10)"},
            {"item": "Upland game bird validation (18+)", "resident": "$11", "nonresident": "Included in the nonresident game bird license"},
            {"item": "Waterfowl validation (18+)", "resident": "$15", "nonresident": ""},
            {"item": "Nonresident game bird license (18+)", "resident": "", "nonresident": "$50"},
        ],
        "sources": [
            {"name": "MyODFW license purchase", "url": BUY_URL},
            {"name": "Controlled hunt draw", "url": DRAW_URL},
            {"name": "2026 big game seasons", "url": SEASONS_URL},
            {"name": "2026 big game regulations", "url": REGS_URL},
        ],
    }


def regulations() -> dict:
    return {
        "title": "Methods, restrictions, and what a unit allows",
        "methods": [
            {
                "id": "any_legal",
                "label": "Any legal weapon",
                "summary": "Centerfire rifle, handgun, or shotgun, muzzleloader, or bow, each meeting the species minimums. This is the firearm season in the regulations. Archery-only and muzzleloader-only hunts do not allow a centerfire rifle.",
            },
            {
                "id": "archery",
                "label": "Archery",
                "summary": "Long bow, recurve, or compound bow, at least 40 pounds draw weight for big game. Broadheads must be unbarbed and at least 7/8 inch wide. Scopes and devices that hold the bow at full draw are prohibited. Lighted nocks and image-only cameras are allowed. Traditional hunts allow long bow or recurve only.",
            },
            {
                "id": "muzzleloader",
                "label": "Muzzleloader",
                "summary": "During muzzleloader-only seasons: at least .40 caliber for deer, pronghorn, bear, and cougar, and .50 for elk, sheep, and goat. Matchlock and revolving-action muzzleloaders are not legal on those hunts. During any-legal-weapon seasons, a muzzleloader may use any ignition except matchlock if it meets the caliber rule.",
            },
            {
                "id": "shotgun",
                "label": "Shotgun",
                "summary": "For deer, bear, and cougar: slugs or #1 or larger buckshot. For elk: slugs only. Shotguns are not legal for bighorn sheep or Rocky Mountain goat. Game birds are shotgun and archery; waterfowl require non-toxic shot.",
            },
            {
                "id": "firearm",
                "label": "Centerfire firearm",
                "summary": "Rifles and handguns must be at least .22 centerfire for deer, pronghorn, bear, and cougar, and .24 for elk, sheep, and goat. Rimfire is legal for western gray squirrel, not for big game. Fully automatic firearms, semiautomatic rifles with a magazine over five rounds, tracer and full-metal-jacket bullets are unlawful for big game.",
            },
        ],
        "prohibited": [
            "Hunting or shooting from or across a public road or railroad right-of-way, except on roads closed to public motor vehicles.",
            "Hunting big game with dogs, except western gray squirrel.",
            "Artificial light, laser sights, and sights that project a beam, including scopes that receive electronic rangefinder data. Battery sights that only light the reticle are allowed.",
            "Infrared or thermal sights, and night vision, including while scouting to hunt. Trail cameras are the stated exception.",
            "Commercial cervid urine scents. Do not import brain or spinal tissue from out-of-state deer or elk.",
            "Hunting game mammals within 500 feet of a designated highway wildlife crossing.",
            "Traps, snares, poison, or tranquilizing drugs for game mammals.",
            "More than one of the mutually exclusive deer tags (general archery, general any-legal-weapon, or a 100-series controlled tag). A 600-series antlerless tag may be held in addition to one 100-series tag.",
        ],
        "unitRules": [
            "A species is legal on a unit only when a general season or a controlled hunt lists that unit or deer hunt area.",
            "Eastern Oregon deer in 2026 uses deer hunt areas, not wildlife management units. Elk and most other big game still use wildlife management units.",
            "An asterisk on a controlled hunt means the open area is not the entire unit. Read the boundary description in the regulations before you apply.",
            "White-tailed deer are illegal in western Oregon except controlled hunts in the Melrose unit that name them in the bag limit.",
            "Highlighted controlled hunts in the printed book are mostly private land. Do not apply without access.",
            "National parks and tribal reservations inside a mapped unit are not open hunting seasons.",
        ],
        "sources": [
            {"name": "2026 Oregon big game regulations", "url": REGS_URL},
            {"name": "2026–27 game bird seasons", "url": GAME_BIRD_URL},
            {"name": "2026–27 migratory game birds", "url": MIGRATORY_URL},
            {"name": "Eastern Oregon deer hunt areas", "url": EAST_DEER_URL},
        ],
    }


def load_units() -> tuple[list[dict], dict, dict]:
    wmu_path = CACHE / "wmu.geojson"
    dha_path = CACHE / "deer-areas.geojson"
    fetch(WMU_QUERY, wmu_path)
    fetch(DHA_QUERY, dha_path)
    wmu = json.loads(wmu_path.read_text())
    dha = json.loads(dha_path.read_text())
    units = []
    wmu_features = []
    dha_features = []
    for feature in wmu["features"]:
        props_in = feature["properties"]
        num = int(props_in["UNIT_NUM"])
        region = {"WEST": "Western", "EAST": "Eastern"}.get(props_in.get("REGION") or "", "Other")
        uid = f"wmu:{num}"
        props = {
            "id": uid,
            "kind": "wmu",
            "code": str(num),
            "name": title_name(str(props_in.get("UNIT_NAME") or f"Unit {num}")),
            "region": region,
            "acres": round(float(props_in["Acres"])) if props_in.get("Acres") else None,
        }
        units.append(props)
        wmu_features.append(simplify_feature(feature, props))
    for feature in dha["features"]:
        props_in = feature["properties"]
        code = str(props_in.get("HuntArea") or "").strip()
        herd = str(props_in.get("HerdRange") or "").strip()
        uid = f"dha:{code}"
        props = {
            "id": uid,
            "kind": "deer_hunt_area",
            "code": code,
            "name": f"{herd} {code}",
            "region": "Eastern",
            "acres": None,
            "herdRange": herd,
        }
        units.append(props)
        dha_features.append(simplify_feature(feature, props))
    return units, {"type": "FeatureCollection", "features": wmu_features}, {"type": "FeatureCollection", "features": dha_features}


def trim_game_birds(rows: list[dict], units: list[dict]) -> None:
    by_region = {
        "Western": [u["id"] for u in units if u["kind"] == "wmu" and u["region"] == "Western"],
        "Eastern": [u["id"] for u in units if u["kind"] == "wmu" and u["region"] == "Eastern"],
    }
    for row in rows:
        if row["scope"] == "western":
            row["unitIds"] = by_region["Western"]
        elif row["scope"] == "eastern":
            row["unitIds"] = by_region["Eastern"]
        elif row["scope"] == "statewide":
            row["unitIds"] = by_region["Western"] + by_region["Eastern"]
        elif row["scope"].startswith("migratory_"):
            row["unitIds"] = []


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, separators=(",", ":")))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", type=Path, help="Extracted big-game regulations text")
    args = parser.parse_args()
    units, wmu_geo, dha_geo = load_units()
    wmu_ids = {u["id"] for u in units if u["kind"] == "wmu"}
    area_ids = {u["id"] for u in units if u["kind"] == "deer_hunt_area"}
    text = ""
    if args.text and args.text.exists():
        text = args.text.read_text(encoding="utf-8", errors="replace")
    else:
        pdf = CACHE / "big-game-2026.pdf"
        try:
            fetch(BIG_GAME_PDF, pdf)
            import fitz

            doc = fitz.open(pdf)
            text = "\n".join(page.get_text() for page in doc)
        except Exception as exc:
            print(f"warning: could not read regulations PDF ({exc})")
    controlled = parse_controlled(text) if text else []
    for hunt in controlled:
        link_units(hunt, wmu_ids, area_ids)
    birds = game_birds(wmu_ids)
    trim_game_birds(birds, units)
    hunts = general_seasons(wmu_ids) + controlled + birds
    species = []
    seen = set()
    for hunt in hunts:
        if hunt["species"] not in seen:
            seen.add(hunt["species"])
            species.append({"id": hunt["species"], "label": hunt["speciesLabel"]})
    meta = {
        "seasonYear": "2026",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "unitCount": len(units),
        "wmuCount": len(wmu_ids),
        "deerHuntAreaCount": len(area_ids),
        "huntCount": len(hunts),
        "controlledCount": len(controlled),
        "disclaimer": (
            "Admin beta. Unofficial planning aid compiled from Oregon Department of Fish and Wildlife "
            "public maps and the 2026 big-game and 2026–27 game-bird regulations. Dates, bag limits, "
            "tag quotas, and boundaries change. Confirm every hunt in the current regulations before you apply or hunt."
        ),
        "species": species,
        "methods": [
            {"id": "any_legal", "label": "Any legal weapon"},
            {"id": "firearm", "label": "Centerfire firearm"},
            {"id": "archery", "label": "Archery"},
            {"id": "muzzleloader", "label": "Muzzleloader"},
            {"id": "shotgun", "label": "Shotgun"},
        ],
        "access": [
            {"id": "general_otc", "label": "Over the counter"},
            {"id": "controlled_draw", "label": "Controlled draw"},
            {"id": "youth_draw", "label": "Youth draw"},
            {"id": "youth", "label": "Youth season"},
            {"id": "premium", "label": "Premium draw"},
            {"id": "additional", "label": "Additional tag"},
            {"id": "no_tag", "label": "No tag"},
            {"id": "validation", "label": "Validation or stamp"},
        ],
        "sources": [
            {"name": "ODFW wildlife management units", "url": "https://nrimp.dfw.state.or.us/DataClearinghouse/default.aspx?p=202&XMLname=805.xml"},
            {"name": "2026 eastern deer hunt areas", "url": EAST_DEER_URL},
            {"name": "2026 big game regulations", "url": REGS_URL},
            {"name": "2026 big game seasons", "url": SEASONS_URL},
            {"name": "2026–27 game bird seasons", "url": GAME_BIRD_URL},
        ],
    }
    payloads = {
        "units.json": units,
        "hunts.json": hunts,
        "wmu.geojson": wmu_geo,
        "deer-areas.geojson": dha_geo,
        "meta.json": meta,
        "licenses.json": licenses(),
        "regulations.json": regulations(),
    }
    for folder in (DATA, WEB):
        for name, payload in payloads.items():
            write_json(folder / name, payload)
    linked = sum(1 for h in controlled if h["unitIds"])
    print(
        f"oregon: {len(units)} areas, {len(hunts)} hunts, "
        f"{len(controlled)} controlled ({linked} linked to a polygon)"
    )


if __name__ == "__main__":
    main()
