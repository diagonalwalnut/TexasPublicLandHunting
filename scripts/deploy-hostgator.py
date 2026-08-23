#!/usr/bin/env python3
"""Upload web/dist to HostGator over FTP (TLS when the host supports it).

Required environment:
  FTP_HOST       e.g. ftp.yourdomain.com or your HostGator hostname
  FTP_USER       cPanel username
  FTP_PASSWORD   cPanel / FTP password

Optional:
  FTP_PORT       default 21
  FTP_REMOTE_DIR default public_html
  FTP_TIMEOUT    default 60

Does not print the password. Refuses to run without the three required vars.
"""

from __future__ import annotations

import os
import sys
from ftplib import FTP, FTP_TLS, error_perm
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "web" / "dist"


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"Missing {name}. Set HostGator FTP credentials as environment variables or GitHub secrets.", file=sys.stderr)
        sys.exit(2)
    return value


def connect(host: str, user: str, password: str, port: int, timeout: int):
    try:
        ftp = FTP_TLS()
        ftp.connect(host, port, timeout=timeout)
        ftp.login(user, password)
        ftp.prot_p()
        ftp.set_pasv(True)
        print(f"Connected with FTP TLS to {host}:{port}")
        return ftp
    except Exception as tls_err:
        print(f"FTP TLS failed ({tls_err}); trying plain FTP")
        ftp = FTP()
        ftp.connect(host, port, timeout=timeout)
        ftp.login(user, password)
        ftp.set_pasv(True)
        print(f"Connected with FTP to {host}:{port}")
        return ftp


def ensure_dir(ftp: FTP, path: str) -> None:
    try:
        ftp.mkd(path)
    except error_perm as exc:
        if "550" not in str(exc) and "521" not in str(exc):
            raise


def chdir_remote(ftp: FTP, remote_dir: str) -> None:
    parts = [p for p in remote_dir.replace("\\", "/").split("/") if p]
    if remote_dir.startswith("/"):
        ftp.cwd("/")
    for part in parts:
        try:
            ftp.cwd(part)
        except error_perm:
            ensure_dir(ftp, part)
            ftp.cwd(part)


def upload_tree(ftp: FTP, local_dir: Path) -> int:
    count = 0
    for path in sorted(local_dir.iterdir()):
        if path.is_dir():
            ensure_dir(ftp, path.name)
            ftp.cwd(path.name)
            count += upload_tree(ftp, path)
            ftp.cwd("..")
        else:
            with path.open("rb") as handle:
                ftp.storbinary(f"STOR {path.name}", handle)
            count += 1
            print(f"  uploaded {path.relative_to(DIST)}")
    return count


def main() -> int:
    host = require_env("FTP_HOST")
    user = require_env("FTP_USER")
    password = require_env("FTP_PASSWORD")
    port = int(os.environ.get("FTP_PORT") or "21")
    remote_dir = (os.environ.get("FTP_REMOTE_DIR") or "public_html").strip() or "public_html"
    timeout = int(os.environ.get("FTP_TIMEOUT") or "60")

    if not DIST.is_dir() or not (DIST / "index.html").is_file():
        print("web/dist/index.html missing. Run: cd web && npm run build", file=sys.stderr)
        return 1

    ftp = connect(host, user, password, port, timeout)
    try:
        chdir_remote(ftp, remote_dir)
        print(f"Remote directory: {ftp.pwd()}")
        n = upload_tree(ftp, DIST)
        print(f"Uploaded {n} files to {remote_dir}")
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
