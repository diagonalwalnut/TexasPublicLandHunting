"""Trace hatched hunting areas from the Fort Worth District 2025 map PDFs.

The Corps hunting GIS is not public. Whitney and Aquilla publish a one-page
scan instead. Town labels on those scans are control points, so the green
hatch can be turned into polygons. Numbered Whitney access labels (B1-B9)
become entry points. The scans are not surveyed; hunters still confirm the
official map.
"""

from __future__ import annotations

import urllib.request
from collections import deque
from pathlib import Path

import numpy as np
import pymupdf
from shapely.geometry import box
from shapely.ops import unary_union
from shapely.validation import make_valid

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "corps-maps"

# Pixel positions are on a 2x render of the PDF page.
# lon/lat are the labeled towns, used as control points.
WHITNEY = {
    "id": "usace-whitney",
    "url": "https://www.swf-wc.usace.army.mil/whitney/maps/WH_2025_Map.pdf",
    "controls": [
        (714, 52, -97.3972382, 32.1426501),  # Blum
        (248, 448, -97.5039076, 32.0698734),  # Kopperl
        (897, 623, -97.3600142, 32.0398757),  # Huron
        (1079, 1059, -97.3214012, 31.9518230),  # Whitney
        (824, 1547, -97.3797357, 31.8593247),  # Laguna Park
    ],
    # Bottom-left disclaimer box, in 2x pixels (x0, y0, x1, y1).
    "ignore": (0, 1450, 700, 1584),
    "entries": [
        ("Access B1", 284, 206),
        ("Access B2", 290, 335),
        ("Access B3", 276, 406),
        ("Access B4", 242, 514),
        ("Access B5", 456, 834),
        ("Access B6", 670, 922),
        ("Access B7", 565, 993),
        ("Access B8", 550, 1261),
        ("Access B9", 670, 1480),
    ],
}
AQUILLA = {
    "id": "usace-aquilla",
    "url": "https://www.swf-wc.usace.army.mil/whitney/maps/AQ_2025_Map.pdf",
    "controls": [
        (562, 354, -97.2219538, 31.9782120),  # Peoria
        (1027, 891, -97.1736179, 31.9146023),  # Vaughan
        (1296, 46, -97.1303744, 32.0108506),  # Hillsboro
    ],
    "ignore": (1100, 900, 1584, 1224),
    "entries": [],
}
MAPS = (WHITNEY, AQUILLA)


def _download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 10000:
        return
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    dest.write_bytes(urllib.request.urlopen(req, timeout=60).read())


def _render(pdf_path: Path):
    doc = pymupdf.open(pdf_path)
    pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
    return arr


def _fit(controls: list[tuple[float, float, float, float]]):
    pts = np.array(controls, dtype=float)
    design = np.column_stack([pts[:, 0], pts[:, 1], np.ones(len(pts))])
    lon_c, *_ = np.linalg.lstsq(design, pts[:, 2], rcond=None)
    lat_c, *_ = np.linalg.lstsq(design, pts[:, 3], rcond=None)

    def pix_to_ll(x: float, y: float) -> tuple[float, float]:
        lon = float(lon_c[0] * x + lon_c[1] * y + lon_c[2])
        lat = float(lat_c[0] * x + lat_c[1] * y + lat_c[2])
        return lon, lat

    return pix_to_ll


def _dilate(mask: np.ndarray, radius: int) -> np.ndarray:
    out = mask.copy()
    for k in range(1, radius + 1):
        out[k:] |= mask[:-k]
        out[:-k] |= mask[k:]
        out[:, k:] |= mask[:, :-k]
        out[:, :-k] |= mask[:, k:]
        out[k:, k:] |= mask[:-k, :-k]
        out[:-k, :-k] |= mask[k:, k:]
        out[k:, :-k] |= mask[:-k, k:]
        out[:-k, k:] |= mask[k:, :-k]
    return out


def _close(mask: np.ndarray, radius: int) -> np.ndarray:
    return ~_dilate(~_dilate(mask, radius), radius)


def _green_mask(arr: np.ndarray, ignore: tuple[int, int, int, int]) -> np.ndarray:
    red = arr[:, :, 0].astype(np.int16)
    green = arr[:, :, 1].astype(np.int16)
    blue = arr[:, :, 2].astype(np.int16)
    mask = (green > 115) & (green > red + 35) & (green > blue + 25) & (red < 180) & (green > 90)
    x0, y0, x1, y1 = ignore
    mask[y0:y1, x0:x1] = False
    mask[:20, :] = False
    mask[-20:, :] = False
    mask[:, :20] = False
    mask[:, -20:] = False
    return mask


def _components(mask: np.ndarray, min_cells: int) -> list[list[tuple[int, int]]]:
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    found: list[list[tuple[int, int]]] = []
    ys, xs = np.where(mask)
    for y, x in zip(ys.tolist(), xs.tolist()):
        if seen[y, x]:
            continue
        queue: deque[tuple[int, int]] = deque([(y, x)])
        seen[y, x] = True
        cells: list[tuple[int, int]] = []
        while queue:
            cy, cx = queue.pop()
            cells.append((cx, cy))
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        if len(cells) >= min_cells:
            found.append(cells)
    return found


def _cell_box(px: int, py: int, step: int, pix_to_ll) -> object:
    corners = [
        pix_to_ll(px, py),
        pix_to_ll(px + step, py),
        pix_to_ll(px + step, py + step),
        pix_to_ll(px, py + step),
    ]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    return box(min(xs), min(ys), max(xs), max(ys))


def extract_map(spec: dict) -> tuple[object, list[dict]]:
    """Return (hunt polygon, entry-point records) for one scanned map."""
    pdf_path = CACHE / f"{spec['id']}.pdf"
    _download(spec["url"], pdf_path)
    arr = _render(pdf_path)
    pix_to_ll = _fit(spec["controls"])
    closed = _close(_green_mask(arr, spec["ignore"]), 4)
    step = 4
    small = closed[::step, ::step]
    parts = []
    for cells in _components(small, min_cells=40):
        geoms = [_cell_box(x * step, y * step, step, pix_to_ll) for x, y in cells]
        merged = make_valid(unary_union(geoms)).simplify(0.00035, preserve_topology=True)
        if merged.is_empty or merged.geom_type not in {"Polygon", "MultiPolygon"}:
            continue
        parts.append(merged)
    if not parts:
        raise RuntimeError(f"no hunt polygons traced from {spec['id']}")
    hunt = make_valid(unary_union(parts))
    entries = []
    for name, x, y in spec["entries"]:
        lon, lat = pix_to_ll(x, y)
        entries.append(
            {
                "unitId": spec["id"],
                "name": name,
                "kind": "entry",
                "lon": round(lon, 5),
                "lat": round(lat, 5),
            }
        )
    return hunt, entries


def extract_all() -> dict[str, tuple[object, list[dict]]]:
    return {spec["id"]: extract_map(spec) for spec in MAPS}
