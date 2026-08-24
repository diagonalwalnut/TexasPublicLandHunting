"""Fetch and compile TPWD 2026-27 drawn hunt catalog into data/ and web/public/data/."""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from safe import tpwd_url
from species import SPECIES, methods_from_tag, species_from_tag

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "drawn"
DATA = ROOT / "data"
WEB_DATA = ROOT / "web" / "public" / "data"

BASE = "https://tpwd.texas.gov/huntwild/hunt/public/public_hunt_drawing/"
HEADERS = {
    "User-Agent": "TexasPublicLandHunting/0.1 (unofficial planning aid; github.com/diagonalwalnut/TexasPublicLandHunting)"
}

APPLY_HOSTS = {"txfgsales.com", "www.txfgsales.com"}

SPECIES_COLORS: dict[str, str] = {
    "white_tailed_deer": "#2f6b4f",
    "mule_deer": "#8b5a2b",
    "pronghorn": "#d4a017",
    "alligator": "#1a6b5a",
    "exotic_mammals": "#7b2d8e",
    "feral_hog": "#6b4f3a",
    "javelina": "#c45c26",
    "turkey": "#b45309",
    "dove": "#5b7c99",
    "quail": "#4f7c4a",
    "squirrel": "#a16207",
    "waterfowl": "#1d4e89",
    "pheasant": "#b91c1c",
    "teal": "#0e7490",
    "rabbit": "#78716c",
    "bighorn_sheep": "#44403c",
}

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def get(url: str) -> str:
    if not tpwd_url(url):
        raise ValueError(f"blocked URL: {url}")
    r = requests.get(url, headers=HEADERS, timeout=120)
    r.raise_for_status()
    return r.text


def cached_html(name: str, url: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / name
    if dest.exists() and dest.stat().st_size > 200:
        return dest.read_text(encoding="utf-8", errors="replace")
    html = get(url)
    dest.write_text(html, encoding="utf-8")
    time.sleep(0.2)
    return html


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").replace("\xa0", " ")).strip()


def parse_iso_date(raw: str) -> str | None:
    text = clean(raw)
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", text)
    if not m:
        return None
    month = MONTHS.get(m.group(1).lower())
    if not month:
        return None
    return f"{int(m.group(3)):04d}-{month:02d}-{int(m.group(2)):02d}"


def parse_date_range(raw: str) -> dict[str, str] | None:
    text = clean(raw).replace("–", "-").replace("—", "-")
    parts = re.split(r"\s*-\s*", text)
    if len(parts) == 1:
        start = parse_iso_date(parts[0])
        return {"start": start, "end": start} if start else None
    if len(parts) >= 2:
        end = parse_iso_date(parts[-1])
        start = parse_iso_date(parts[0])
        if start and not end:
            # "Nov 30 - Dec 03, 2026"
            year = parts[-1][-4:] if re.search(r"\d{4}$", parts[-1]) else ""
            start = parse_iso_date(parts[0] + (f", {year}" if year and "," not in parts[0] else ""))
        if not start:
            start = parse_iso_date(parts[0] + ", " + (end[:4] if end else "2026"))
        if start and end:
            return {"start": start, "end": end}
    return None


def apply_url(href: str) -> str:
    raw = (href or "").strip()
    try:
        parsed = urlparse(raw)
    except ValueError:
        return ""
    if parsed.scheme != "https":
        return ""
    if (parsed.hostname or "").lower() not in APPLY_HOSTS:
        return ""
    return parsed.geturl()


def catalog_url(path: str) -> str:
    return urljoin(BASE, path)


def parse_ocat(href: str) -> str | None:
    q = parse_qs(urlparse(href).query)
    code = (q.get("OCat") or [None])[0]
    return code if code and re.fullmatch(r"[A-Z0-9]{2,8}", code) else None


def parse_oarea(href: str) -> str | None:
    q = parse_qs(urlparse(href).query)
    code = (q.get("OArea") or [None])[0]
    return code if code and re.fullmatch(r"[A-Z0-9]{1,8}", code) else None


def program_from_heading(text: str) -> str:
    t = text.lower()
    if "e-postcard" in t or "epostcard" in t:
        return "e_postcard"
    if "forest service" in t or t.startswith("usfs"):
        return "usfs"
    if "national wildlife refuge" in t or " nwr" in t:
        return "nwr"
    return "special_permit"


def access_from(program: str, group: str, category_name: str) -> str:
    blob = f"{program} {group} {category_name}".lower()
    if "guided" in blob:
        return "guided"
    if "private" in blob:
        return "private_lands"
    if program == "e_postcard":
        return "e_postcard"
    if program == "usfs":
        return "usfs"
    if program == "nwr":
        return "nwr"
    if "youth/adult" in blob or "youth / adult" in blob:
        return "youth_adult"
    if "youth" in blob:
        return "youth"
    return "drawn"


def species_from_category(name: str, group: str) -> list[str]:
    blob = f"{name} {group}"
    keys: list[str] = []
    primary = species_from_tag(blob)
    if primary:
        keys.append(primary)
    t = blob.lower()
    if "multi" in t and "species" in t:
        for extra in ("dove", "quail", "rabbit", "squirrel", "feral_hog"):
            if extra not in keys:
                keys.append(extra)
    if "waterfowl" in t and "pheasant" in t and "pheasant" not in keys:
        keys.append("pheasant")
    return keys


def methods_from_category(name: str, group: str, means: list[str]) -> list[str]:
    blob = " ".join([name, group, *means])
    methods = methods_from_tag(blob, species_from_tag(blob) or "white_tailed_deer")
    t = blob.lower()
    if "muzzle" in t and "muzzleloader" not in methods:
        methods.append("muzzleloader")
    if ("gun" in t or "rifle" in t or "centerfire" in t) and "firearm" not in methods:
        methods.insert(0, "firearm")
    return list(dict.fromkeys(methods)) or ["any_legal"]


def parse_categories(html: str) -> list[dict]:
    page = soup(html)
    main = page.select_one("#lampwrapper") or page
    categories: list[dict] = []
    program = "special_permit"
    group = "General"
    for el in main.find_all(["h2", "h3", "a"]):
        if el.name == "h2":
            program = program_from_heading(el.get_text(" ", strip=True))
            group = "General"
            continue
        if el.name == "h3":
            group = clean(el.get_text(" ", strip=True)) or "General"
            continue
        href = el.get("href") or ""
        code = parse_ocat(href)
        if not code:
            continue
        name = clean(el.get_text(" ", strip=True))
        if not name:
            continue
        categories.append(
            {
                "code": code,
                "name": name,
                "program": program,
                "group": group,
                "url": catalog_url(href),
            }
        )
    # de-dupe by code, first heading wins
    seen: dict[str, dict] = {}
    for row in categories:
        seen.setdefault(row["code"], row)
    return list(seen.values())


def parse_areas_index(html: str) -> list[dict]:
    page = soup(html)
    areas: list[dict] = []
    for a in page.select('a[href*="OArea="]'):
        code = parse_oarea(a.get("href") or "")
        name = clean(a.get_text(" ", strip=True))
        if code and name:
            areas.append({"code": code, "name": name, "url": catalog_url(a["href"])})
    seen: dict[str, dict] = {}
    for row in areas:
        seen.setdefault(row["code"], row)
    return list(seen.values())


def parse_area_coords(html: str) -> tuple[float, float] | None:
    m = re.search(r"initMap\(\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\)", html)
    if not m:
        return None
    lat, lon = float(m.group(1)), float(m.group(2))
    if not (25.0 <= lat <= 37.0 and -107.5 <= lon <= -93.0):
        return None
    return lon, lat


def header_cells(wrapper) -> list[str]:
    return [clean(c.get_text(" ", strip=True)) for c in wrapper.select(".data-cell") if clean(c.get_text(" ", strip=True))]


def parse_hunt_section(section, *, category: dict, area_code: str, area_name: str) -> dict | None:
    title_el = section.select_one(".title")
    if not title_el:
        return None
    # Category pages put the area name in .title and the area code in section id.
    name = clean(title_el.get_text(" ", strip=True)) or area_name
    cat_name = category["name"]
    cat_code = category["code"]
    section_id = (section.get("id") or "").upper()
    if re.fullmatch(r"[A-Z0-9]{1,8}", section_id):
        area_code = section_id

    deadline = None
    people = ""
    for strong in section.select(".limits strong"):
        text = clean(strong.get_text(" ", strip=True))
        lower = text.lower()
        if "deadline" in lower:
            deadline = parse_iso_date(text)
        elif "people" in lower:
            people = text

    notes = [clean(s.get_text(" ", strip=True)) for s in section.select(".notices span")]
    notes = [n for n in notes if n]

    hunt_dates: list[dict[str, str]] = []
    bag_limit = ""
    means_allowed: list[str] = []
    means_not: list[str] = []
    hunt_method = ""
    baiting = ""
    restrictions = ""
    permits_available = None
    fee_adult = None
    fee_youth = None
    last_apps = None
    last_permits = None
    last_success = ""
    age = ""

    for wrapper in section.select(".data-wrapper"):
        header = clean((wrapper.select_one(".data-header") or wrapper).get_text(" ", strip=True) if wrapper.select_one(".data-header") else "")
        if wrapper.select_one(".data-header"):
            header = clean(wrapper.select_one(".data-header").get_text(" ", strip=True))
        cells = header_cells(wrapper)
        blob = " ".join(cells)
        key = header.lower()
        if key == "hunt dates":
            for cell in cells:
                rng = parse_date_range(cell)
                if rng:
                    hunt_dates.append(rng)
        elif key == "bag limit":
            bag_limit = re.sub(r"\s+", " ", blob.replace(" hr ", " / ")).strip()
        elif "only means allowed" in key:
            means_allowed = cells
        elif "means not allowed" in key:
            means_not = cells
        elif key == "hunt method":
            hunt_method = blob
        elif key == "baiting":
            baiting = blob
        elif key == "hunt restrictions":
            restrictions = blob
        elif key == "permits":
            for cell in cells:
                if cell.lower().startswith("available:"):
                    nums = re.findall(r"\d+", cell)
                    if nums:
                        permits_available = int(nums[0])
                elif "adult" in cell.lower():
                    nums = re.findall(r"\d+(?:\.\d+)?", cell.replace(",", ""))
                    if nums:
                        fee_adult = float(nums[0])
                elif "youth" in cell.lower():
                    nums = re.findall(r"\d+(?:\.\d+)?", cell.replace(",", ""))
                    if nums:
                        fee_youth = float(nums[0])
        elif key == "age requirements":
            age = blob
        elif key == "last year":
            for cell in cells:
                cl = cell.lower()
                nums = re.findall(r"[\d,]+%?", cell)
                if cl.startswith("applications:") and nums:
                    last_apps = int(nums[0].replace(",", "").replace("%", ""))
                elif ("permits" in cl or "groups" in cl) and nums:
                    last_permits = int(re.sub(r"[^\d]", "", nums[0]) or 0)
                elif "success" in cl:
                    last_success = nums[0] if nums else cell.split(":", 1)[-1].strip()

    brochure = ""
    apply = ""
    for a in section.select("a[href]"):
        href = a.get("href") or ""
        if "/brochures/" in href:
            brochure = tpwd_url(urljoin(BASE, href))
        if "oAction=APPLY" in href or "txfgsales.com" in href:
            apply = apply_url(href) or apply_url(urljoin("https://www.txfgsales.com/", href))

    if not apply:
        apply = (
            "https://www.txfgsales.com/PHS/InterfaceLanding.aspx"
            f"?oCat={cat_code}&oArea={area_code}&oAction=APPLY&GDSID=NONE"
        )

    species = species_from_category(cat_name, category["group"])
    methods = methods_from_category(cat_name, category["group"], means_allowed)
    color = SPECIES_COLORS.get(species[0], "#5c675f") if species else "#5c675f"
    hunt_id = f"{area_code}-{cat_code}"
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", hunt_id):
        return None

    return {
        "id": hunt_id,
        "areaCode": area_code,
        "areaName": name,
        "categoryCode": cat_code,
        "categoryName": cat_name,
        "program": category["program"],
        "group": category["group"],
        "species": species,
        "speciesLabel": ", ".join(SPECIES.get(s, s) for s in species) or cat_name,
        "methods": methods,
        "access": access_from(category["program"], category["group"], cat_name),
        "applicationDeadline": deadline or category.get("deadline"),
        "huntDates": hunt_dates,
        "bagLimit": bag_limit,
        "meansAllowed": means_allowed,
        "meansNotAllowed": means_not,
        "huntMethod": hunt_method,
        "baiting": baiting,
        "restrictions": restrictions,
        "permitsAvailable": permits_available,
        "feeAdult": fee_adult,
        "feeYouth": fee_youth,
        "peoplePerApplication": people,
        "ageRequirements": age,
        "lastYearApplications": last_apps,
        "lastYearPermits": last_permits,
        "lastYearSuccess": last_success,
        "notes": notes,
        "brochureUrl": brochure,
        "applyUrl": apply,
        "lon": None,
        "lat": None,
        "color": color,
        "counties": [],
        "region": "",
    }


def parse_category_deadline(html: str) -> str | None:
    page = soup(html)
    el = page.select_one(".deadline")
    if not el:
        return None
    return parse_iso_date(el.get_text(" ", strip=True))


def parse_category_hunts(html: str, category: dict) -> list[dict]:
    page = soup(html)
    hunts: list[dict] = []
    deadline = parse_category_deadline(html)
    if deadline:
        category = {**category, "deadline": deadline}
    for section in page.select("section[id]"):
        sid = (section.get("id") or "").upper()
        if not re.fullmatch(r"[A-Z0-9]{1,8}", sid):
            continue
        if not section.select_one(".title"):
            continue
        hunt = parse_hunt_section(section, category=category, area_code=sid, area_name="")
        if hunt:
            hunts.append(hunt)
    return hunts


def match_aph_unit(name: str, units: list[dict]) -> dict | None:
    key = re.sub(r"[^a-z0-9]+", "", name.lower())
    for unit in units:
        ukey = re.sub(r"[^a-z0-9]+", "", (unit.get("name") or "").lower())
        if key and (key == ukey or key in ukey or ukey in key):
            return unit
    return None


def compile_drawn(hunts: list[dict], areas: dict[str, dict], units: list[dict]) -> tuple[list[dict], dict]:
    out: list[dict] = []
    for hunt in hunts:
        area = areas.get(hunt["areaCode"], {})
        coords = area.get("coords")
        if coords:
            hunt["lon"], hunt["lat"] = coords
        if not hunt["areaName"]:
            hunt["areaName"] = area.get("name") or hunt["areaName"]
        aph = match_aph_unit(hunt["areaName"], units)
        if aph:
            hunt["counties"] = list(aph.get("counties") or [])
            hunt["region"] = aph.get("region") or ""
            if hunt["lon"] is None:
                hunt["lon"] = aph.get("lon")
                hunt["lat"] = aph.get("lat")
        start = min((d["start"] for d in hunt["huntDates"]), default="")
        end = max((d["end"] for d in hunt["huntDates"]), default="")
        hunt["start"] = start
        hunt["end"] = end
        if not hunt.get("applyUrl"):
            hunt["applyUrl"] = (
                "https://www.txfgsales.com/PHS/InterfaceLanding.aspx"
                f"?oCat={hunt['categoryCode']}&oArea={hunt['areaCode']}&oAction=APPLY&GDSID=NONE"
            )
        out.append(hunt)

    used_ids: set[str] = set()
    for hunt in out:
        base = hunt["id"]
        hunt_id = base
        n = 2
        while hunt_id in used_ids:
            hunt_id = f"{base}-{n}"
            n += 1
        hunt["id"] = hunt_id
        used_ids.add(hunt_id)

    species_ids = sorted({s for h in out for s in h["species"]})
    method_ids = sorted({m for h in out for m in h["methods"]})
    access_ids = sorted({h["access"] for h in out})
    regions = sorted({h["region"] for h in out if h["region"]})
    counties = sorted({c for h in out for c in h["counties"]})
    meta = {
        "seasonYear": "2026-27",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "huntCount": len(out),
        "areaCount": len({h["areaCode"] for h in out}),
        "disclaimer": (
            "Unofficial planning aid compiled from Texas Parks and Wildlife Department drawn hunt catalog pages. "
            "Deadlines, means, bag limits, and hunt dates change. Confirm every hunt on the official TPWD catalog "
            "and apply through the Texas Public Hunt System."
        ),
        "sources": [
            {
                "name": "Drawn Hunt Catalog (2026-27)",
                "url": "https://tpwd.texas.gov/huntwild/hunt/public/public_hunt_drawing/hunt-categories.phtml",
            },
            {
                "name": "Drawn Hunt Deadlines (2026-27)",
                "url": "https://tpwd.texas.gov/huntwild/hunt/public/public_hunt_drawing/deadlines.phtml",
            },
        ],
        "species": [{"id": s, "label": SPECIES.get(s, s)} for s in species_ids],
        "methods": [
            {"id": m, "label": {"archery": "Archery", "firearm": "Firearm / rifle", "muzzleloader": "Muzzleloader", "shotgun": "Shotgun", "any_legal": "Any legal means"}.get(m, m)}
            for m in method_ids
        ],
        "access": [
            {
                "id": a,
                "label": {
                    "drawn": "Special permit",
                    "e_postcard": "E-Postcard",
                    "usfs": "U.S. Forest Service",
                    "nwr": "National Wildlife Refuge",
                    "youth": "Youth",
                    "youth_adult": "Youth/adult",
                    "private_lands": "Private lands",
                    "guided": "Guided package",
                }.get(a, a),
            }
            for a in access_ids
        ],
        "regions": regions,
        "counties": counties,
        "catalogUrl": "https://tpwd.texas.gov/huntwild/hunt/public/public_hunt_drawing/",
    }
    return out, meta


def hunts_geojson(hunts: list[dict]) -> dict:
    features = []
    for hunt in hunts:
        if hunt.get("lon") is None or hunt.get("lat") is None:
            continue
        features.append(
            {
                "type": "Feature",
                "id": hunt["id"],
                "properties": {
                    "id": hunt["id"],
                    "name": hunt["areaName"],
                    "category": hunt["categoryName"],
                    "species": hunt["speciesLabel"],
                    "color": hunt["color"],
                    "deadline": hunt.get("applicationDeadline"),
                    "lon": hunt["lon"],
                    "lat": hunt["lat"],
                },
                "geometry": {"type": "Point", "coordinates": [hunt["lon"], hunt["lat"]]},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main() -> int:
    print("fetch drawn hunt catalog index")
    cat_html = cached_html("hunt-categories.html", catalog_url("hunt-categories.phtml"))
    areas_html = cached_html("hunt-areas.html", catalog_url("hunt-areas.phtml"))
    categories = parse_categories(cat_html)
    area_rows = parse_areas_index(areas_html)
    print(f"  {len(categories)} categories, {len(area_rows)} areas")

    areas: dict[str, dict] = {}
    for row in area_rows:
        html = cached_html(f"area-{row['code']}.html", row["url"])
        coords = parse_area_coords(html)
        areas[row["code"]] = {**row, "coords": coords}
        print(f"  area {row['code']} {row['name']} {'coords' if coords else 'no-map'}")

    hunts: list[dict] = []
    for cat in categories:
        html = cached_html(f"cat-{cat['code']}.html", cat["url"])
        parsed = parse_category_hunts(html, cat)
        print(f"  category {cat['code']} {cat['name']}: {len(parsed)} hunts")
        hunts.extend(parsed)

    units_path = DATA / "units.json"
    units = json.loads(units_path.read_text()) if units_path.exists() else []
    hunts, meta = compile_drawn(hunts, areas, units)
    geo = hunts_geojson(hunts)
    for dest in (DATA, WEB_DATA):
        write_json(dest / "drawn_hunts.json", hunts)
        write_json(dest / "drawn_meta.json", meta)
        write_json(dest / "drawn_hunts.geojson", geo)
    located = sum(1 for h in hunts if h.get("lon") is not None)
    print(f"wrote {len(hunts)} drawn hunts ({located} with coordinates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
