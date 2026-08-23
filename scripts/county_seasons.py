"""Parse Outdoor Annual county pages into species, methods, and date windows."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

SPECIES_FROM_ID = {
    "white-tailed-deer": "white_tailed_deer",
    "mule-deer": "mule_deer",
    "javelina": "javelina",
    "pronghorn": "pronghorn",
    "turkey": "turkey",
    "wild-turkey": "turkey",
    "dove": "dove",
    "quail": "quail",
    "pheasant": "pheasant",
    "chachalaca": "chachalaca",
    "squirrel": "squirrel",
    "rabbits-and-hares": "rabbit",
    "rabbit": "rabbit",
    "blue-winged-green-winged-and-cinnamon-teal": "teal",
    "teal": "teal",
    "duck": "waterfowl",
    "goose": "waterfowl",
    "king-and-clapper-rails": "other_migratory",
    "rails-gallinules-and-moorhens": "other_migratory",
    "wilsons-snipe-common-snipe-or-jacksnipe": "other_migratory",
    "woodcock": "other_migratory",
    "sandhill-crane": "sandhill_crane",
}

MIGRATORY = {"dove", "waterfowl", "teal", "sandhill_crane", "other_migratory", "chachalaca"}
GUN_GAME = {"white_tailed_deer", "mule_deer", "turkey", "javelina", "pronghorn"}

COUNTY_URL = "https://tpwd.texas.gov/regulations/outdoor-annual/regs/counties/{slug}"

TOKEN = re.compile(
    r"(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sept?(?:ember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\.?\s+"
    r"(\d{1,2})(?:\s*,\s*(\d{4}))?",
    re.I,
)


def split_counties(raw: str) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"\s*(?:,|/|&|;|\band\b)\s*", raw.strip())
    out: list[str] = []
    for part in parts:
        name = re.sub(r"\s+County$", "", part.strip(), flags=re.I)
        name = re.sub(r"\s+", " ", name)
        if not name or name.lower() in {"none", "&ensp;"}:
            continue
        if name.lower() in {"lasalle", "la salle"}:
            name = "La Salle"
        out.append(name)
    return list(dict.fromkeys(out))


def county_slugs(name: str) -> list[str]:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    compact = base.replace("-", "")
    slugs = [base]
    if compact != base:
        slugs.append(compact)
    aliases = {
        "la-salle": "lasalle",
        "de-witt": "dewitt",
    }
    if base in aliases:
        slugs.insert(0, aliases[base])
    return list(dict.fromkeys(slugs))


def _ymd(year: int, month: int, day: int) -> str:
    return date(year, month, day).isoformat()


def parse_date_ranges(text: str) -> list[dict[str, str]]:
    raw = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    raw = BeautifulSoup(raw, "lxml").get_text("\n")
    raw = raw.replace("–", "-").replace("—", "-")
    if re.search(r"no closed season", raw, re.I):
        return [{"start": "2026-09-01", "end": "2027-08-31"}]
    windows: list[dict[str, str]] = []
    for chunk in re.split(r"[\n;]+", raw):
        chunk = chunk.strip()
        if not chunk or not TOKEN.search(chunk):
            continue
        if "-" not in chunk:
            toks = list(TOKEN.finditer(chunk))
            if len(toks) == 1:
                month, day, year = toks[0].groups()
                if year:
                    iso = _ymd(int(year), MONTHS[month[:3].lower() if month[:3].lower() != "sep" else "sep"], int(day))
                    # sept -> sep
                    m = MONTHS.get(re.sub(r"[^a-z]", "", month.lower())[:4], MONTHS.get(month[:3].lower()))
                    if m:
                        iso = _ymd(int(year), m, int(day))
                        windows.append({"start": iso, "end": iso})
            continue
        left, right = re.split(r"\s*-\s*", chunk, maxsplit=1)
        left_m = TOKEN.search(left)
        right_m = TOKEN.search(right) or re.search(r"(\d{1,2})(?:\s*,\s*(\d{4}))?", right)
        if not left_m:
            continue
        sm_name, sd, sy = left_m.groups()
        sm = _month(sm_name)
        sd_i = int(sd)
        sy_i = int(sy) if sy else None

        if hasattr(right_m, "groups") and right_m and right_m.lastindex and right_m.lastindex >= 2 and not str(right_m.group(1)).isdigit():
            em_name, ed, ey = right_m.groups()
            em = _month(em_name)
            ed_i = int(ed)
            ey_i = int(ey) if ey else None
        else:
            # "4 - 17, 2027" or "17, 2027"
            day_year = re.search(r"(\d{1,2})(?:\s*,\s*(\d{4}))?", right)
            if not day_year:
                continue
            em = sm
            ed_i = int(day_year.group(1))
            ey_i = int(day_year.group(2)) if day_year.group(2) else None

        if sy_i is None and ey_i is None:
            continue
        if sy_i is None and ey_i is not None:
            sy_i = ey_i if sm <= em else ey_i - 1
        if ey_i is None and sy_i is not None:
            ey_i = sy_i if em >= sm else sy_i + 1
        try:
            windows.append({"start": _ymd(sy_i, sm, sd_i), "end": _ymd(ey_i, em, ed_i)})
        except ValueError:
            continue
    return windows


def _month(name: str) -> int:
    key = re.sub(r"[^a-z]", "", name.lower())
    if key.startswith("sept"):
        return 9
    return MONTHS[key[:3]]


def methods_from_title(title: str, species: str) -> list[str] | None:
    t = title.lower()
    if "falcon" in t:
        return None
    if "archery" in t:
        return ["archery"]
    if "muzzle" in t:
        return ["muzzleloader"]
    if species in MIGRATORY:
        return ["shotgun"]
    if species in GUN_GAME and ("general" in t or "regular" in t):
        return ["firearm"]
    return ["any_legal"]


def access_from_title(title: str) -> str:
    if "youth" in title.lower():
        return "youth"
    return "aph_walk_in"


def species_from_animal(animal_id: str, label: str) -> str | None:
    if animal_id in SPECIES_FROM_ID:
        return SPECIES_FROM_ID[animal_id]
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    if slug in SPECIES_FROM_ID:
        return SPECIES_FROM_ID[slug]
    if "deer" in slug and "mule" in slug:
        return "mule_deer"
    if "deer" in slug:
        return "white_tailed_deer"
    if "turkey" in slug:
        return "turkey"
    if "hog" in slug:
        return "feral_hog"
    return None


def _bag_props(node) -> dict[str, str]:
    out: dict[str, str] = {}
    msgs = node.select(".baglimit-msg")
    vals = node.select(".baglimit-value")
    for msg, val in zip(msgs, vals):
        key = msg.get_text(" ", strip=True)
        out[key] = val.get_text(" ", strip=True)
    return out


def _season_blocks(season_dd) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    headers = season_dd.select(".seasonheader")
    if headers:
        for header in headers:
            title_el = header.select_one(".seasontitle")
            date_el = header.select_one(".seasondate")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            raw = date_el.decode_contents() if date_el else ""
            blocks.append({"title": title, "raw": raw})
        return blocks
    labels = season_dd.select(".seasondatelabel")
    if labels:
        for lab in labels:
            title_el = lab.select_one(".seasonlabel") or season_dd.select_one(".seasontitle")
            date_el = lab.select_one(".seasondate")
            title = title_el.get_text(" ", strip=True) if title_el else ""
            raw = date_el.decode_contents() if date_el else ""
            blocks.append({"title": title, "raw": raw})
        return blocks
    title_el = season_dd.select_one(".seasontitle")
    date_el = season_dd.select_one(".seasondate")
    if title_el or date_el:
        blocks.append(
            {
                "title": title_el.get_text(" ", strip=True) if title_el else "",
                "raw": date_el.decode_contents() if date_el else "",
            }
        )
    return blocks


def parse_county_html(html: str, slug: str = "") -> dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.h1.get_text(" ", strip=True) if soup.h1 else slug
    name = re.sub(r"\s+20\d{2}.*", "", h1).strip()
    animals: list[dict[str, Any]] = []
    for animal in soup.select(".animal.accordion"):
        label_el = animal.select_one("h2")
        label = label_el.get_text(" ", strip=True) if label_el else ""
        animal_id = animal.get("id") or ""
        species = species_from_animal(animal_id, label)
        if not species:
            continue
        zone_el = animal.select_one(".zonename")
        zone = zone_el.get_text(" ", strip=True) if zone_el else ""
        zone_bags = {}
        for zone_dd in animal.select("dd.zone"):
            zone_bags.update(_bag_props(zone_dd))
        seasons: list[dict[str, Any]] = []
        for season_dd in animal.select("dd.season"):
            props = _bag_props(season_dd)
            for block in _season_blocks(season_dd):
                title = block["title"]
                methods = methods_from_title(title, species)
                if methods is None:
                    continue
                windows = parse_date_ranges(block["raw"])
                if not windows:
                    continue
                seasons.append(
                    {
                        "title": title,
                        "methods": methods,
                        "access": access_from_title(title),
                        "windows": windows,
                        "rawDates": BeautifulSoup(block["raw"], "lxml").get_text(" ", strip=True),
                        "notes": props.get("Bag Limit") or props.get("Daily Bag Limit") or "",
                    }
                )
        animals.append(
            {
                "species": species,
                "label": label,
                "zone": zone,
                "bagLimit": zone_bags.get("Bag Limit", ""),
                "antlerRestrictions": zone_bags.get("Antler Restrictions", ""),
                "seasons": seasons,
            }
        )
    return {
        "county": name,
        "slug": slug,
        "url": COUNTY_URL.format(slug=slug) if slug else "",
        "animals": animals,
    }


def windows_from_county(
    county: dict[str, Any],
    species: str,
    method: str,
    access: str,
) -> list[dict[str, str]]:
    """Pick Outdoor Annual date windows for a unit's legal game/method/access."""
    hits: list[dict[str, str]] = []
    youth = access in {"youth", "youth_adult"}
    for animal in county.get("animals", []):
        if animal["species"] != species:
            continue
        for season in animal.get("seasons", []):
            season_youth = season["access"] == "youth"
            if youth != season_youth:
                continue
            if re.search(r"dusky|veteran|falcon", season["title"], re.I):
                continue
            if method == "any_legal" or method in season["methods"] or "any_legal" in season["methods"]:
                hits.extend(season["windows"])
            elif method == "firearm" and season["methods"] == ["firearm"]:
                hits.extend(season["windows"])
    # de-dupe
    seen = set()
    out = []
    for win in hits:
        key = (win["start"], win["end"])
        if key in seen:
            continue
        seen.add(key)
        out.append(win)
    return out


def load_counties(cache_dir: Path) -> dict[str, dict[str, Any]]:
    """Map canonical and APH county names to parsed Outdoor Annual data."""
    by_name: dict[str, dict[str, Any]] = {}
    for path in sorted(cache_dir.glob("*.html")):
        parsed = parse_county_html(path.read_text(encoding="utf-8", errors="ignore"), slug=path.stem)
        if not parsed.get("animals"):
            continue
        by_name[parsed["county"].lower()] = parsed
        by_name[path.stem.replace("-", " ")] = parsed
        by_name[path.stem.replace("-", "")] = parsed
    return by_name


def lookup_county(index: dict[str, dict[str, Any]], name: str) -> dict[str, Any] | None:
    key = name.lower().strip()
    if key in index:
        return index[key]
    compact = key.replace(" ", "").replace("-", "")
    if compact in index:
        return index[compact]
    if key in {"lasalle", "la salle"}:
        return index.get("la salle") or index.get("lasalle")
    return None
