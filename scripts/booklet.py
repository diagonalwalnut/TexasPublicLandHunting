"""Parse unit page numbers from the Public Hunting Lands Map Booklet PDF."""

from __future__ import annotations

import re
from pathlib import Path

BOOKLET_URL = "https://tpwd.texas.gov/publications/pwdpubs/media/pwd_bk_w7000_0112a.pdf"
BOOKLET_FILENAME = "pwd_bk_w7000_0112a.pdf"

UNIT_ID_ONLY = re.compile(r"^(\d{3,4}[A-Za-z]?)(?:\s*/\s*(\d{3,4}[A-Za-z]?))?\s*$")
UNIT_ID_PREFIX = re.compile(
    r"^(\d{3,4}[A-Za-z]?)(?:\s*/\s*(\d{3,4}[A-Za-z]?))?(?:\s+|$)(.*)$"
)
PAGE_AT_END = re.compile(r"(\d{1,3})(?:\s*[–\-]\s*(\d{1,3}))?\s*$")
ROMAN_PAGE = re.compile(r"^(x{0,3}v?i{0,3}|ix|iv|vi{0,3}|x[ivxlc]*)$", re.I)


def _norm_name(text: str) -> str:
    s = text.lower()
    s = s.replace("state park", "sp").replace("wildlife management area", "wma")
    s = s.replace("national wildlife refuge", "nwr")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def _ids_from_match(m: re.Match[str]) -> list[str]:
    ids = [m.group(1)]
    if m.group(2):
        ids.append(m.group(2))
    return ids


def _open_pdf(path: Path):
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz  # type: ignore
    return fitz.open(path)


def printed_page_index(doc) -> dict[str, int]:
    """Map printed page label (e.g. '5' or 'xxiv') to 1-based PDF page number."""
    index: dict[str, int] = {}
    for i, page in enumerate(doc):
        text = page.get_text("text")
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            continue
        first = lines[0]
        if re.fullmatch(r"\d{1,3}", first) or ROMAN_PAGE.fullmatch(first):
            index.setdefault(first.lower(), i + 1)
    return index


def parse_toc(doc) -> dict[str, dict]:
    """Unit id -> {page, pageEnd} from the booklet table of contents."""
    lines: list[str] = []
    for i in range(min(12, doc.page_count)):
        text = doc[i].get_text("text")
        if "TABLE OF CONTENTS" in text or lines:
            lines.extend(text.splitlines())
            if i >= 7 and "Schedule of Recreational Use" in text:
                break

    started = False
    pending: list[str] = []
    current: int | None = None
    current_end: int | None = None
    pages: dict[str, dict] = {}

    def assign(page: int, page_end: int | None) -> None:
        nonlocal pending
        for uid in pending:
            pages[uid] = {"page": page, "pageEnd": page_end or page}
        pending = []

    for raw in lines:
        line = raw.replace("\t", " ").replace("♿", " ").strip()
        line = re.sub(r"\s+", " ", line)
        if not line:
            continue
        if not started:
            if line.upper().startswith("MAP LEGEND") or line.startswith("PUBLIC HUNT REGION"):
                started = True
            else:
                continue
        if line.upper() == "AREA CLOSED":
            pending = []
            continue
        if line.startswith("Get the Texas Hunt"):
            break

        only = UNIT_ID_ONLY.match(line)
        if only:
            pending.extend(_ids_from_match(only))
            continue

        prefix = UNIT_ID_PREFIX.match(line)
        rest = line
        if prefix and prefix.group(1) and (prefix.group(3) or prefix.group(2)):
            # Avoid treating year-like numbers in prose; require a unit-id shaped start.
            pending.extend(_ids_from_match(prefix))
            rest = (prefix.group(3) or "").strip()
            if not rest:
                continue

        page_m = PAGE_AT_END.search(rest.replace("…", "."))
        looks_like_entry = bool(re.search(r"\.{3,}", rest))
        if looks_like_entry and page_m:
            page = int(page_m.group(1))
            page_end = int(page_m.group(2)) if page_m.group(2) else page
            if page > 200:
                continue
            current, current_end = page, page_end
            if pending:
                assign(page, page_end)
            continue

        if pending and current is not None and "PUBLIC HUNT REGION" not in rest:
            assign(current, current_end)

    if pending and current is not None:
        assign(current, current_end)
    return pages


def parse_epostcard_headers(doc) -> list[tuple[str, str]]:
    """(normalized header, roman page) from E-Postcard hunt listing pages."""
    headers: list[tuple[str, str]] = []
    for page in doc:
        text = page.get_text("text")
        if "For specific information regarding E-Postcard" not in text:
            continue
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            continue
        roman = lines[0].lower() if ROMAN_PAGE.fullmatch(lines[0]) else ""
        if not roman:
            continue
        for ln in lines[1:]:
            compact = re.sub(r"\s+", " ", ln).strip()
            letters = re.sub(r"[^A-Za-z]", "", compact)
            if len(compact) < 8 or len(letters) < 8:
                continue
            if compact != compact.upper():
                continue
            if compact.startswith("FOR SPECIFIC") or compact.startswith("E-POSTCARD"):
                continue
            if compact.startswith("REGULAR PERMIT") or compact.startswith("MENTORED"):
                continue
            headers.append((_norm_name(compact), roman))
    return headers


def _name_tokens(text: str) -> set[str]:
    stop = {"unit", "the", "and", "of", "a"}
    return {t for t in _norm_name(text).split() if t not in stop}


def match_epostcard(name: str, headers: list[tuple[str, str]]) -> str | None:
    needle = _name_tokens(name)
    if len(needle) < 2:
        return None
    best: tuple[float, str] | None = None
    for header, roman in headers:
        tokens = set(header.split()) - {"unit", "the", "and", "of", "a"}
        if not tokens:
            continue
        if needle == tokens or needle <= tokens or tokens <= needle:
            score = len(needle & tokens) / max(len(needle | tokens), 1)
            if best is None or score > best[0]:
                best = (score, roman)
    return best[1] if best and best[0] >= 0.7 else None


def parse_regional_tables(doc) -> dict[str, dict]:
    """Unit id -> map page from regional 'Hunts Offered' tables."""
    pages: dict[str, dict] = {}
    unit_re = re.compile(r"^\d{3,4}[A-Za-z]?$")
    page_re = re.compile(r"^(\d{1,3})(?:-(\d{1,3}))?$")
    for page in doc:
        words = page.get_text("words")
        if not words:
            continue
        headers = [w for w in words if w[4] == "Page"]
        unit_hdrs = [w for w in words if w[4] == "Unit"]
        if not headers or not unit_hdrs:
            continue
        blob = page.get_text("text")
        if "Unit #" not in blob and "Unit Number" not in blob:
            # Many tables still use "Unit #" split across words.
            if not any(w[4] == "#" for w in words):
                continue
        page_hdr = headers[0]
        # Prefer the Unit header nearest the Page header (the Unit # column).
        unit_hdr = min(unit_hdrs, key=lambda w: abs(w[0] - page_hdr[0]) + abs(w[1] - page_hdr[1]))
        rotated = abs(page_hdr[0] - unit_hdr[0]) < abs(page_hdr[1] - unit_hdr[1])
        unit_words = [w for w in words if unit_re.match(w[4])]
        page_words = [w for w in words if page_re.match(w[4])]
        ep = next((w for w in words if w[4] == "E-Postcard"), None)
        if rotated:
            unit_row_y = unit_hdr[1]
            page_row_y = page_hdr[1]
            units = [w for w in unit_words if abs(w[1] - unit_row_y) < 25]
            if ep:
                units = [w for w in units if w[0] < ep[0] - 4]
            nums = [w for w in page_words if abs(w[1] - page_row_y) < 25 and 1 <= int(page_re.match(w[4]).group(1)) <= 150]
            nums = sorted(nums, key=lambda w: w[0])
            for i, pw in enumerate(nums):
                x0 = pw[0] - 10
                x1 = nums[i + 1][0] - 10 if i + 1 < len(nums) else pw[0] + 40
                m = page_re.match(pw[4])
                rec = {"page": int(m.group(1)), "pageEnd": int(m.group(2) or m.group(1))}
                for uw in units:
                    if x0 <= uw[0] < x1:
                        pages[uw[4]] = rec
        else:
            unit_col_x = unit_hdr[0]
            page_col_x = page_hdr[0]
            units = [w for w in unit_words if abs(w[0] - unit_col_x) < 30]
            if ep:
                units = [w for w in units if w[1] < ep[1] - 4]
            nums = [
                w
                for w in page_words
                if abs(w[0] - page_col_x) < 30 and 1 <= int(page_re.match(w[4]).group(1)) <= 150
            ]
            nums = sorted(nums, key=lambda w: w[1])
            for i, pw in enumerate(nums):
                y0 = pw[1] - 6
                y1 = nums[i + 1][1] - 6 if i + 1 < len(nums) else pw[1] + 16
                m = page_re.match(pw[4])
                rec = {"page": int(m.group(1)), "pageEnd": int(m.group(2) or m.group(1))}
                for uw in units:
                    if y0 <= uw[1] < y1:
                        pages[uw[4]] = rec
    return pages


def format_page(page: int | str, page_end: int | str | None = None) -> str:
    if isinstance(page, str) and not str(page).isdigit():
        return str(page)
    start = int(page)
    end = int(page_end) if page_end not in (None, "") else start
    if end and end != start:
        return f"{start}–{end}"
    return str(start)


def booklet_url_for(pdf_page: int | None) -> str:
    if not pdf_page:
        return BOOKLET_URL
    return f"{BOOKLET_URL}#page={pdf_page}"


def load_booklet_pages(pdf_path: Path) -> dict[str, dict]:
    """Return unit-id keyed records plus a '_pdf_index' map of printed label -> PDF page."""
    if not pdf_path.exists() or pdf_path.stat().st_size < 1000:
        return {}
    doc = _open_pdf(pdf_path)
    try:
        toc = parse_toc(doc)
        regional = parse_regional_tables(doc)
        merged = {**regional, **toc}
        eheaders = parse_epostcard_headers(doc)
        pdf_index = printed_page_index(doc)
        if "747" not in merged and "747E" in merged and "747W" in merged:
            merged["747"] = {
                "page": min(merged["747E"]["page"], merged["747W"]["page"]),
                "pageEnd": max(merged["747E"]["pageEnd"], merged["747W"]["pageEnd"]),
            }
        return {
            "_toc": merged,
            "_epostcard": eheaders,
            "_pdf_index": pdf_index,
        }
    finally:
        doc.close()


def lookup_unit(
    booklet: dict,
    unit_ids: list[str],
    name: str,
) -> dict | None:
    if not booklet:
        return None
    toc: dict[str, dict] = booklet.get("_toc") or {}
    pdf_index: dict[str, int] = booklet.get("_pdf_index") or {}
    rec = None
    for uid in unit_ids:
        if uid in toc:
            rec = toc[uid]
            break
        # 901N vs 901, 783N vs 783
        if uid and any(k.startswith(uid) and k != uid for k in toc):
            kids = [toc[k] for k in toc if k.startswith(uid) and k[len(uid) : len(uid) + 1].isalpha()]
            if kids:
                rec = {
                    "page": min(k["page"] for k in kids),
                    "pageEnd": max(k["pageEnd"] for k in kids),
                }
                break
    source = "toc"
    label = None
    if rec:
        label = format_page(rec["page"], rec.get("pageEnd"))
        pdf_page = pdf_index.get(str(rec["page"]))
    else:
        roman = match_epostcard(name, booklet.get("_epostcard") or [])
        if not roman:
            return None
        label = roman
        pdf_page = pdf_index.get(roman)
        source = "epostcard"
    return {
        "bookletPage": label,
        "bookletPdfPage": pdf_page,
        "bookletUrl": booklet_url_for(pdf_page),
        "bookletSource": source,
    }
