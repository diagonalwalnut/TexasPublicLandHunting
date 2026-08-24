"""Extract LEGAL GAME / means / special-season text from unit map PDFs."""

from __future__ import annotations

import re
from pathlib import Path

HEADINGS = [
    "SPECIAL REGULATIONS",
    "LEGAL GAME",
    "Means Restriction",
    "MEANS RESTRICTION",
    "ENTIRE AREA CLOSED",
    "SPECIAL SEASON",
    "GENERAL USE & VISITATION INFORMATION",
    "YOUTH HUNTS",
    "E-POSTCARD SELECTION HUNTS",
]

HEADING_RE = re.compile(
    r"(?<![A-Za-z])("
    + "|".join(re.escape(h) for h in sorted(HEADINGS, key=len, reverse=True))
    + r")(?!\s+Legend)(?![A-Za-z])",
    re.I,
)

# Main Legal Game box on unit maps: "LEGAL GAME • 2026-2027" ... until Special Regulations.
LEGAL_GAME_BOX_RE = re.compile(
    r"LEGAL GAME\s*[•·.\-:]?\s*20\d{2}[\s\S]{20,8000}?(?=SPECIAL REGULATIONS|SPECIAL SEASONS?\b|$)",
    re.I,
)

ONLY_CLAUSE_SKIP = re.compile(
    r"youth only|night hunting only|daylight hunting only|permit required|aph permit|"
    r"no usfs|legend for|see tpwd",
    re.I,
)


def _pdf_text(path: Path) -> str:
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz  # PyMuPDF
        except ImportError:
            return ""
    if not path.exists() or path.stat().st_size < 500:
        return ""
    try:
        doc = fitz.open(path)
    except Exception:
        return ""
    chunks: list[str] = []
    try:
        for page in doc:
            text = page.get_text() or ""
            if text.strip():
                chunks.append(text)
            else:
                for block in page.get_text("blocks"):
                    if len(block) < 5:
                        continue
                    piece = str(block[4]).strip()
                    if piece:
                        chunks.append(piece)
    finally:
        doc.close()
    return "\n".join(chunks)


def parse_pdf(path: Path) -> dict[str, str]:
    raw = _pdf_text(path)
    if not raw:
        return {}
    blob = re.sub(r"[ \t]+", " ", raw)
    sections: dict[str, str] = {}
    box = LEGAL_GAME_BOX_RE.search(blob)
    if box:
        sections["LEGAL GAME"] = re.sub(r"\s+", " ", box.group(0)).strip()[:8000]
    parts = HEADING_RE.split(blob)
    i = 0
    while i < len(parts):
        piece = parts[i].strip()
        if HEADING_RE.fullmatch(piece):
            key = re.sub(r"\s+", " ", piece).upper()
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            body = HEADING_RE.split(body, maxsplit=1)[0].strip()
            body = re.sub(r"\s+", " ", body)
            if len(body) > 20:
                prev = sections.get(key, "")
                if len(body) > len(prev):
                    sections[key] = body[:8000]
            i += 2
            continue
        i += 1
    return sections


def methods_named(text: str) -> list[str]:
    """Means named in a clause. Rifle/firearm is distinct from shotgun and muzzleloader."""
    t = text.lower()
    found: list[str] = []
    if re.search(r"archery|\bbows?\b", t):
        found.append("archery")
    if re.search(r"shotguns?", t):
        found.append("shotgun")
    if re.search(r"muzzle-?loaders?", t):
        found.append("muzzleloader")
    no_rifle = bool(re.search(r"no (?:rifles?|centerfire)|rifles? (?:are )?not|centerfire (?:is |are )?not", t))
    if not no_rifle and re.search(r"all legal firearms|centerfire|\brifles?\b", t):
        found.append("firearm")
    return list(dict.fromkeys(found))


def exclusive_methods(text: str) -> list[str] | None:
    """If a clause lists allowed means '... only', return those methods."""
    t = re.sub(r"\s+", " ", text.lower())
    best: list[str] | None = None
    best_len = 0
    for match in re.finditer(r"(.{0,200}\bonly\b)", t):
        clause = match.group(1)
        if ONLY_CLAUSE_SKIP.search(clause):
            continue
        if not re.search(r"archery|shotgun|muzzle|rifle|firearm|centerfire|\bbow", clause):
            continue
        named = methods_named(clause)
        if named and len(named) >= best_len:
            best = named
            best_len = len(named)
    return best


def general_season_methods(text: str) -> list[str] | None:
    """Means allowed during General Season, from the unit Legal Game box.

    Example (Ladonia): "General Season: Nov. 7-Jan. 3 ... Archery, shotguns with
    buckshot or slugs, and muzzleloaders only."
    """
    t = re.sub(r"\s+", " ", text.lower())
    for match in re.finditer(r"general season:\s*", t):
        window = t[match.end() : match.end() + 450]
        exclusive = exclusive_methods(window)
        if exclusive:
            return exclusive
        if re.search(r"all legal firearms", window):
            named = methods_named(window)
            return named or ["firearm"]
    return exclusive_methods(t)


def apply_general_means(methods: list[str], tag: str, general_means: list[str] | None) -> tuple[list[str], bool]:
    """Replace rifle/firearm on General-season tags when the unit forbids centerfire.

    Returns (methods, used_general_dates) where used_general_dates means county
    General / firearm windows should be used even if the method is shotgun or
    muzzleloader.
    """
    if not general_means:
        return list(methods), False
    if "firearm" in general_means:
        return list(methods), False
    t = tag.lower()
    if "archery" in t and "general" not in t:
        return ["archery"] if "archery" in methods or not methods else list(methods), False
    if "muzzle" in t and "general" not in t:
        return ["muzzleloader"], False
    if re.search(r"\bgeneral\b", t) or "firearm" in methods or (
        "any_legal" in methods and "youth" in t
    ):
        # Archery already has its own APH tag/season. General-season rows
        # should carry shotgun/muzzleloader (or other non-bow means), using
        # General dates — not the January muzzleloader-only season.
        if re.search(r"\bgeneral\b", t) or "firearm" in methods:
            gun = [m for m in general_means if m != "archery"]
            return (gun or list(general_means)), True
        return list(general_means), True
    return list(methods), False


def methods_from_pdf_text(text: str) -> list[str]:
    t = text.lower()
    exclusive = exclusive_methods(text)
    if exclusive:
        return exclusive
    general = general_season_methods(text)
    if general:
        return general
    methods: list[str] = []
    if re.search(r"archery only|bow only", t):
        methods.append("archery")
    if re.search(r"muzzle-?loaders? only", t):
        methods.append("muzzleloader")
    if re.search(r"shotguns? only|no rifles?", t):
        methods.append("shotgun")
    if re.search(r"all legal firearms|centerfire|\brifles?\b", t) and not re.search(r"no rifles?", t):
        methods.append("firearm")
    return methods
