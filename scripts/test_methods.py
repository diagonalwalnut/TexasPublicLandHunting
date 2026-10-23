#!/usr/bin/env python3
"""Firearm/rifle must stay distinct from muzzleloader and shotgun."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from pdfs import (  # noqa: E402
    apply_general_means,
    apply_means_restriction,
    deer_methods_from_pdf_text,
    exclusive_methods,
    general_season_methods,
    methods_from_pdf_text,
    methods_named,
    muzzleloaders_prohibited,
    parse_pdf,
    prohibited_methods,
    rifles_prohibited,
)
from species import methods_from_tag  # noqa: E402

LADONIA_DEER = """
White-tailed Deer: Bag limit - 2 deer no more than 1 buck all seasons combined.
Archery Only Season: Oct. 3-Nov. 6 (either sex).
General Season: Nov. 7-Jan. 3 (buck only unless in possession of a USFS Antlerless Deer
Permit. See USFS Additional Restrictions section for more information on antlerless deer permits).
Archery, shotguns with buckshot or slugs, and muzzleloaders only.
Feral Hog: (no bag limit).
"""

BOIS_DARC_DEER = """
White-tailed Deer: Bag limit- 2 deer no more than 1 buck all seasons combined.
Archery Only Season: Oct. 3-Nov. 6 (either sex).
General Season: Nov. 7-Jan. 3 (buck only unless in possession of a USFS Antlerless Deer Permit).
All legal firearms including shotguns with buckshot or slugs.
"""


def main() -> int:
    assert "firearm" not in methods_from_tag("Deer - Muzzle loader", "white_tailed_deer")
    assert methods_from_tag("Deer - Muzzle loader", "white_tailed_deer") == ["muzzleloader"]
    assert methods_from_tag("Deer- General", "white_tailed_deer") == ["firearm"]
    assert methods_from_tag("Deer - Archery", "white_tailed_deer") == ["archery"]
    assert "firearm" not in methods_from_tag("Shotgun", "squirrel")
    assert methods_named("shotguns with buckshot or slugs, and muzzleloaders") == [
        "shotgun",
        "muzzleloader",
    ]
    assert "firearm" not in methods_named("shotguns with buckshot or slugs, and muzzleloaders")

    ladonia = exclusive_methods(
        "Archery, shotguns with buckshot or slugs, and muzzleloaders only."
    )
    assert ladonia == ["archery", "shotgun", "muzzleloader"], ladonia
    assert "firearm" not in ladonia

    general = general_season_methods(LADONIA_DEER)
    assert general == ["archery", "shotgun", "muzzleloader"], general

    bois = general_season_methods(BOIS_DARC_DEER)
    assert bois is not None and "firearm" in bois, bois

    methods, use_general = apply_general_means(
        ["firearm"], "Deer- General", ["archery", "shotgun", "muzzleloader"]
    )
    assert methods == ["shotgun", "muzzleloader"], methods
    assert use_general is True

    archery, archery_general = apply_general_means(
        ["archery"], "Deer - Archery", ["archery", "shotgun", "muzzleloader"]
    )
    assert archery == ["archery"]
    assert archery_general is False

    muzzle, muzzle_general = apply_general_means(
        ["muzzleloader"], "Deer - Muzzle loader", ["archery", "shotgun", "muzzleloader"]
    )
    assert muzzle == ["muzzleloader"]
    assert muzzle_general is False

    # Bois d'Arc allows rifles during general season.
    keep, keep_general = apply_general_means(["firearm"], "Deer- General", bois)
    assert keep == ["firearm"]
    assert keep_general is False

    pdf_path = Path("/tmp/pdfs/901S.pdf")
    if pdf_path.exists():
        sections = parse_pdf(pdf_path)
        text = sections.get("LEGAL GAME") or ""
        assert "muzzleloaders only" in text.lower(), text[:400]
        assert general_season_methods(text) == ["archery", "shotgun", "muzzleloader"]
        assert "firearm" not in methods_from_pdf_text(text)

    # Air rifles are not centerfire rifles.
    assert "firearm" not in methods_named(
        "pre-charged pneumatic air rifles/arrow guns are the only legal means"
    )
    assert methods_named(
        "Shotguns with slugs, muzzleloaders, archery equipment, and pre-charged "
        "pneumatic air rifles/arrow guns are the only legal means allowed"
    ) == ["archery", "shotgun", "muzzleloader"]

    ban = (
        "Means Restriction: Centerfire/rimfire rifles, pistols, and "
        "muzzle-loading firearms are PROHIBITED."
    )
    assert rifles_prohibited(ban)
    assert muzzleloaders_prohibited(ban)
    assert prohibited_methods(ban) == ["firearm", "muzzleloader"]
    assert "firearm" not in methods_named(ban)
    assert "firearm" not in methods_from_pdf_text(ban)
    assert apply_means_restriction(
        ["archery", "firearm", "any_legal", "muzzleloader"], prohibited_methods(ban)
    ) == ["archery"]
    marlin_box = (
        "White-tailed Deer: Archery Only; each day of the Archery and General seasons. "
        "Feral Hog: Archery Only. "
        + ban
    )
    assert deer_methods_from_pdf_text(marlin_box) == ["archery"]
    assert "firearm" not in methods_from_pdf_text(marlin_box)

    marlin = Path("/tmp/pdfs/2547.pdf")
    twin = Path("/tmp/pdfs/502.pdf")
    if marlin.exists():
        text = parse_pdf(marlin).get("LEGAL GAME") or ""
        assert deer_methods_from_pdf_text(text) == ["archery"], text[:300]
        assert "firearm" not in deer_methods_from_pdf_text(text)
    if twin.exists():
        text = parse_pdf(twin).get("LEGAL GAME") or ""
        means = deer_methods_from_pdf_text(text)
        assert means == ["archery", "shotgun", "muzzleloader"], means
        assert "firearm" not in means

    print("ok: firearm stays distinct from muzzleloader and shotgun")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
