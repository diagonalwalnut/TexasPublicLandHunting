#!/usr/bin/env python3
"""Sanity checks on compiled TPWD drawn hunt catalog data."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WEB = ROOT / "web" / "public" / "data"
ALLOWED_HOSTS = {"tpwd.texas.gov", "www.tpwd.texas.gov", "txfgsales.com", "www.txfgsales.com"}


def main() -> int:
    hunts = json.loads((DATA / "drawn_hunts.json").read_text())
    meta = json.loads((DATA / "drawn_meta.json").read_text())
    geo = json.loads((DATA / "drawn_hunts.geojson").read_text())
    web_hunts = json.loads((WEB / "drawn_hunts.json").read_text())
    assert hunts == web_hunts
    assert len(hunts) >= 300, len(hunts)
    ids = [h["id"] for h in hunts]
    assert len(ids) == len(set(ids)), "duplicate drawn hunt ids"
    assert all(h.get("lon") is not None and h.get("lat") is not None for h in hunts)
    assert len(geo["features"]) == len(hunts)
    assert meta["seasonYear"] == "2026-27"
    assert meta["huntCount"] == len(hunts)
    assert any(h["applicationDeadline"] for h in hunts)
    assert any(h["huntDates"] for h in hunts)
    assert any(h["meansAllowed"] for h in hunts)
    species = {s for h in hunts for s in h["species"]}
    assert "white_tailed_deer" in species
    assert "alligator" in species
    for hunt in hunts:
        for field in ("brochureUrl", "applyUrl"):
            url = hunt.get(field) or ""
            if not url:
                continue
            parsed = urlparse(url)
            assert parsed.scheme == "https", (hunt["id"], field, url)
            assert parsed.hostname in ALLOWED_HOSTS, (hunt["id"], field, url)
        assert hunt["color"].startswith("#")
    print(f"ok: {len(hunts)} drawn hunts, {len(species)} species, {len(geo['features'])} map pins")
    return 0


if __name__ == "__main__":
    sys.exit(main())
