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
    "(" + "|".join(re.escape(h) for h in sorted(HEADINGS, key=len, reverse=True)) + ")",
    re.I,
)


def parse_pdf(path: Path) -> dict[str, str]:
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return {}
    if not path.exists() or path.stat().st_size < 500:
        return {}
    try:
        doc = fitz.open(path)
    except Exception:
        return {}
    chunks: list[str] = []
    try:
        for page in doc:
            for block in page.get_text("blocks"):
                if len(block) < 5:
                    continue
                text = str(block[4]).strip()
                if text:
                    chunks.append(re.sub(r"\s+", " ", text))
    finally:
        doc.close()
    blob = " \n ".join(chunks)
    parts = HEADING_RE.split(blob)
    sections: dict[str, str] = {}
    i = 0
    while i < len(parts):
        piece = parts[i].strip()
        if HEADING_RE.fullmatch(piece):
            key = piece.upper()
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            body = HEADING_RE.split(body, maxsplit=1)[0].strip()
            if len(body) > 20:
                sections[key] = body[:4000]
            i += 2
            continue
        i += 1
    return sections


def methods_from_pdf_text(text: str) -> list[str]:
    t = text.lower()
    methods: list[str] = []
    if re.search(r"archery only|bow only", t):
        methods.append("archery")
    if re.search(r"muzzleloader only|muzzle-loader only", t):
        methods.append("muzzleloader")
    if re.search(r"shotgun only|no rifles|shotguns only", t):
        methods.append("shotgun")
    if re.search(r"centerfire|rifle|firearm", t) and "no rifle" not in t:
        methods.append("firearm")
    return methods
