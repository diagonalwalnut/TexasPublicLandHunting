#!/usr/bin/env python3
"""County zone parsing and South Zone split geometry."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from shapely.geometry import shape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from county_seasons import parse_county_html, windows_from_county  # noqa: E402

DATA = ROOT / "data"
WEB = ROOT / "web" / "public" / "data"
SPLIT_SLUGS = {
    "austin",
    "bexar",
    "caldwell",
    "chambers",
    "colorado",
    "fayette",
    "gonzales",
    "guadalupe",
    "harris",
    "jefferson",
    "kinney",
    "medina",
    "orange",
    "uvalde",
    "val-verde",
    "waller",
}


def general_ends(page: dict) -> set[str]:
    ends: set[str] = set()
    for animal in page["animals"]:
        if animal["species"] != "white_tailed_deer":
            continue
        for season in animal["seasons"]:
            if season["title"] == "General Season":
                ends.update(window["end"] for window in season["windows"])
    return ends


def main() -> int:
    html = (ROOT / "scripts" / "fixtures" / "kinney-deer.html").read_text(encoding="utf-8")
    page = parse_county_html(html, slug="kinney")
    deer = [animal for animal in page["animals"] if animal["species"] == "white_tailed_deer"]
    assert len(deer) == 2, deer
    assert {animal["zone"] for animal in deer} == {"North Zone", "South Zone"}
    assert all(animal["portion"] for animal in deer)
    assert general_ends(page) == {"2027-01-03", "2027-01-17"}, general_ends(page)
    windows = windows_from_county(page, "white_tailed_deer", "firearm", "public")
    ends = {window["end"] for window in windows}
    assert {"2027-01-03", "2027-01-17"} <= ends, windows

    counties = json.loads((DATA / "counties.geojson").read_text())
    splits = json.loads((DATA / "county-splits.geojson").read_text())
    assert len(counties["features"]) == 254, len(counties["features"])
    by_slug = {feature["properties"]["slug"]: feature for feature in counties["features"]}
    assert len(by_slug) == 254
    split_by_slug = {feature["properties"]["slug"]: feature for feature in splits["features"]}
    assert set(split_by_slug) == SPLIT_SLUGS, set(split_by_slug) ^ SPLIT_SLUGS

    for slug, feature in split_by_slug.items():
        county = shape(by_slug[slug]["geometry"])
        line = shape(feature["geometry"])
        assert county.buffer(0.02).covers(line), slug
        assert line.length > 0.05, (slug, line.length)

    assert by_slug["kinney"]["properties"]["deerZone"] == "split"
    assert by_slug["medina"]["properties"]["deerZone"] == "split"
    assert by_slug["uvalde"]["properties"]["deerZone"] == "split"
    assert by_slug["val-verde"]["properties"]["deerZone"] == "split"
    assert by_slug["bexar"]["properties"]["deerZone"] == "north"
    assert by_slug["austin"]["properties"]["deerZone"] == "north"
    assert by_slug["starr"]["properties"]["deerZone"] == "south"
    assert by_slug["el-paso"]["properties"]["deerZone"] == "none"
    assert by_slug["travis"]["properties"]["deerZone"] == "north"
    assert by_slug["williamson"]["properties"]["deerZone"] == "north"

    web_counties = json.loads((WEB / "counties.geojson").read_text())
    web_splits = json.loads((WEB / "county-splits.geojson").read_text())
    assert len(web_counties["features"]) == 254
    assert {feature["properties"]["slug"] for feature in web_splits["features"]} == SPLIT_SLUGS

    pages = json.loads((DATA / "counties.json").read_text())
    kinney = pages["kinney"]
    assert general_ends(kinney) == {"2027-01-03", "2027-01-17"}
    travis_deer = [animal for animal in pages["travis"]["animals"] if animal["species"] == "white_tailed_deer"]
    assert {animal["zone"] for animal in travis_deer} == {"North Zone"}
    assert {animal["portion"] for animal in travis_deer} == {"East of IH 35", "West of IH 35"}
    print("county checks ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
