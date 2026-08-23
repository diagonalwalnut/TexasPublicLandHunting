"""Download TPWD sources into cache/. Be polite: sequential requests with a short pause."""

from __future__ import annotations

import json
import time
import zipfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"

HEADERS = {
    "User-Agent": "TexasPublicLandHunting/0.1 (unofficial planning aid; github.com/diagonalwalnut/TexasPublicLandHunting)"
}

BASE = "https://tpwd.texas.gov/huntwild/hunt/public/annual_public_hunting"
SOURCES = {
    "aph_202627.json": f"{BASE}/data/aph_202627.json",
    "search.phtml": f"{BASE}/search.phtml",
    "PublicHuntAreasDetailsKMZ2026-27.zip": f"{BASE}/resources/map/PublicHuntAreasDetailsKMZ2026-27.zip",
    "PublicHuntLocatorPointsGPX2026-27.zip": f"{BASE}/resources/map/PublicHuntLocatorPointsGPX2026-27.zip",
    "oa_dates.html": "https://tpwd.texas.gov/regulations/outdoor-annual/hunting/2026-2027-hunting-season-dates",
    "pwd_bk_w7000_0112a.pdf": "https://tpwd.texas.gov/publications/pwdpubs/media/pwd_bk_w7000_0112a.pdf",
}

ARCGIS_POINTS = (
    "https://tpwd.texas.gov/server/rest/services/Wildlife/TPWD_PublicHuntLocatorMap/MapServer/"
    "{layer}/query?where=1%3D1&outFields=*&f=geojson&outSR=4326&returnGeometry=true"
)


def get(url: str) -> bytes:
    r = requests.get(url, headers=HEADERS, timeout=120)
    r.raise_for_status()
    return r.content


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.write_bytes(get(url))
    time.sleep(0.25)


def unzip(zip_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)


def extract_kmz(kmz_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(kmz_path) as zf:
        zf.extractall(dest_dir)


def fetch_core() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        dest = CACHE / name
        print(f"fetch {name}")
        download_file(url, dest)

    kmz_zip = CACHE / "PublicHuntAreasDetailsKMZ2026-27.zip"
    gpx_zip = CACHE / "PublicHuntLocatorPointsGPX2026-27.zip"
    unzip(kmz_zip, CACHE)
    unzip(gpx_zip, CACHE)

    hunt_kmz = CACHE / "PublicHuntAreasDetailsKMZ2026-27" / "PublicHuntAreas.kmz"
    dove_kmz = CACHE / "PublicHuntAreasDetailsKMZ2026-27" / "DoveLeasePoly.kmz"
    extract_kmz(hunt_kmz, CACHE / "kmz_hunt")
    extract_kmz(dove_kmz, CACHE / "kmz_dove")

    for layer, name in ((1, "hunt_points.geojson"), (0, "dove_points.geojson")):
        dest = CACHE / name
        print(f"fetch {name}")
        download_file(ARCGIS_POINTS.format(layer=layer), dest)


def fetch_pdfs(limit: int | None = None) -> None:
    catalog = json.loads((CACHE / "aph_202627.json").read_text())
    pdf_dir = CACHE / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    names: list[str] = []
    for row in catalog:
        for key in ("areaPDF", "aerialPDFurl"):
            val = row.get(key)
            if val in (None, "", "&ensp;"):
                continue
            names.append(str(val))
        for i in range(1, 6):
            val = row.get(f"moreDetails{i}_url")
            if val:
                names.append(str(val))
    unique = list(dict.fromkeys(names))
    if limit:
        unique = unique[:limit]
    for i, name in enumerate(unique, 1):
        dest = pdf_dir / f"{name}.pdf"
        if dest.exists() and dest.stat().st_size > 1000:
            continue
        url = f"{BASE}/resources/{name}.pdf"
        print(f"[{i}/{len(unique)}] {name}.pdf")
        try:
            download_file(url, dest)
        except Exception as exc:
            print(f"  skip {name}: {exc}")


def fetch_counties() -> None:
    from county_seasons import county_slugs, split_counties

    catalog = json.loads((CACHE / "aph_202627.json").read_text())
    names: list[str] = []
    for row in catalog:
        names.extend(split_counties(str(row.get("county") or "")))
    unique = sorted(set(names), key=str.lower)
    dest_dir = CACHE / "counties"
    dest_dir.mkdir(parents=True, exist_ok=True)
    print(f"fetch {len(unique)} county Outdoor Annual pages")
    for i, name in enumerate(unique, 1):
        slugs = county_slugs(name)
        done = False
        for slug in slugs:
            dest = dest_dir / f"{slug}.html"
            if dest.exists() and dest.stat().st_size > 5000:
                done = True
                break
            url = f"https://tpwd.texas.gov/regulations/outdoor-annual/regs/counties/{slug}"
            try:
                print(f"[{i}/{len(unique)}] {name} ({slug})")
                download_file(url, dest)
                if dest.stat().st_size > 5000 and b"This page does not seem to exist" not in dest.read_bytes():
                    done = True
                    break
                dest.unlink(missing_ok=True)
            except Exception as exc:
                print(f"  skip {slug}: {exc}")
                dest.unlink(missing_ok=True)
        if not done:
            print(f"  missing county page for {name}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--pdfs", action="store_true")
    parser.add_argument("--counties", action="store_true")
    parser.add_argument("--pdf-limit", type=int, default=None)
    args = parser.parse_args()
    fetch_core()
    if args.pdfs:
        fetch_pdfs(args.pdf_limit)
    if args.counties:
        fetch_counties()
    print("done")
