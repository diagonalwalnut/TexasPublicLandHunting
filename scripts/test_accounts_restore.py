#!/usr/bin/env python3
"""Restore missing/truncated HostGator API files via accounts.php, then sign in."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ACCOUNTS = ROOT / "web" / "public" / "accounts.php"
PASSWORD = "correct-horse-battery-staple-9"


def http_json(url: str, *, method: str = "GET", body: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {"Accept": "application/json", "Origin": "http://127.0.0.1:18089"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            return res.status, json.loads(res.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"error": raw}
        return exc.code, payload


def wait_health(base: str) -> dict:
    last = ""
    for _ in range(40):
        try:
            status, payload = http_json(base + "/accounts.php?action=health")
            if status == 200 and payload.get("ok"):
                return payload
            last = repr(payload)
        except OSError as exc:
            last = str(exc)
        time.sleep(0.1)
    raise AssertionError(f"accounts.php did not become ready: {last}")


def main() -> int:
    if not ACCOUNTS.is_file():
        raise SystemExit(f"missing {ACCOUNTS}; run scripts/bundle_accounts_php.py")

    staging = Path(tempfile.mkdtemp(prefix="tplh-restore-"))
    api = staging / "api"
    (api / "lib").mkdir(parents=True)
    (api / "data").mkdir()
    (api / "lib" / "http.php").write_text("", encoding="utf-8")
    (staging / "accounts.php").write_bytes(ACCOUNTS.read_bytes())

    env = os.environ.copy()
    env["AUTH_DATA_DIR"] = str(staging / "api" / "data")
    proc = subprocess.Popen(
        ["php", "-S", "127.0.0.1:18089", "-t", str(staging)],
        cwd=str(staging),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        health = wait_health("http://127.0.0.1:18089")
        assert health.get("hasher") == "argon2id", health

        index = api / "index.php"
        http_php = api / "lib" / "http.php"
        assert index.is_file() and index.stat().st_size > 32, index
        assert http_php.is_file() and http_php.stat().st_size > 32, http_php
        assert (api / "lib" / "store.php").is_file()
        assert (api / "lib" / "common-passwords.json").stat().st_size > 0

        status, created = http_json(
            "http://127.0.0.1:18089/accounts.php?action=signup",
            method="POST",
            body={
                "username": "trailwalker",
                "email": "trailwalker@example.com",
                "password": PASSWORD,
            },
        )
        assert status == 201, created
        assert created["user"]["username"] == "trailwalker"
        assert created["user"]["role"] == "admin"
        assert PASSWORD.encode() not in index.read_bytes()

        status, via_index = http_json("http://127.0.0.1:18089/api/index.php?action=health")
        assert status == 200 and via_index.get("ok") is True, via_index

        print("accounts restore tests ok")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
