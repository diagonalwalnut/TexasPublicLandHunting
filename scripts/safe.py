"""Host and path guards for TPWD downloads and outbound links."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile, ZipInfo

ALLOWED_HOSTS = {"tpwd.texas.gov", "www.tpwd.texas.gov"}
ALLOWED_PREFIXES = (
    "https://tpwd.texas.gov/",
    "https://www.tpwd.texas.gov/",
)
RESOURCE_STEM = re.compile(r"^[A-Za-z0-9._-]+$")


def is_tpwd_url(url: str) -> bool:
    raw = (url or "").strip()
    if not raw or any(ch in raw for ch in "\n\r\\"):
        return False
    try:
        parsed = urlparse(raw)
    except ValueError:
        return False
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        return False
    return raw.startswith(ALLOWED_PREFIXES)


def tpwd_url(url: str) -> str:
    raw = (url or "").strip()
    return raw if is_tpwd_url(raw) else ""


def resource_stem(name: str) -> str:
    raw = str(name).strip().replace("\\", "/")
    if not raw or "/" in raw or raw in {".", ".."}:
        return ""
    return raw if RESOURCE_STEM.fullmatch(raw) else ""


def _safe_zip_target(dest_dir: Path, member: ZipInfo) -> Path | None:
    name = member.filename.replace("\\", "/")
    if name.startswith("/") or name.startswith("../") or "/../" in f"/{name}/":
        return None
    parts = [p for p in name.split("/") if p and p != "."]
    if any(p == ".." for p in parts):
        return None
    target = (dest_dir / Path(*parts)).resolve()
    dest_root = dest_dir.resolve()
    try:
        target.relative_to(dest_root)
    except ValueError:
        return None
    return target


def safe_extract(zip_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_root = dest_dir.resolve()
    with ZipFile(zip_path) as zf:
        for info in zf.infolist():
            target = _safe_zip_target(dest_root, info)
            if target is None:
                continue
            if info.is_dir() or info.filename.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as out:
                out.write(src.read())
