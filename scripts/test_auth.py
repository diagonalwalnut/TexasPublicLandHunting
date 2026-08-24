#!/usr/bin/env python3
"""Exercise the PHP accounts API and assert passwords are stored as Argon2id."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROUTER = ROOT / "web" / "api-dev-router.php"
PASSWORD = "correct-horse-battery-staple-9"


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = ""

    def call(self, path: str, *, method: str = "GET", body: dict | None = None, csrf: bool = False) -> tuple[int, dict]:
        data = None
        headers = {"Accept": "application/json", "Origin": "http://localhost:5173"}
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        if csrf:
            headers["X-CSRF-Token"] = self.csrf
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=20) as res:
                payload = json.loads(res.read().decode())
                status = res.status
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"error": raw}
            status = exc.code
        if isinstance(payload, dict) and payload.get("csrf"):
            self.csrf = str(payload["csrf"])
        return status, payload


def wait_health(api: Api) -> dict:
    last = ""
    for _ in range(40):
        try:
            status, payload = api.call("/api/health")
            if status == 200 and payload.get("ok"):
                return payload
            last = repr(payload)
        except OSError as exc:
            last = str(exc)
        time.sleep(0.1)
    raise AssertionError(f"API did not become ready: {last}")


def main() -> int:
    data_dir = Path(tempfile.mkdtemp(prefix="tplh-auth-"))
    env = os.environ.copy()
    env["AUTH_DATA_DIR"] = str(data_dir)
    proc = subprocess.Popen(
        ["php", "-S", "127.0.0.1:18088", str(ROUTER)],
        cwd=str(ROOT / "web"),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    api = Api("http://127.0.0.1:18088")
    try:
        health = wait_health(api)
        assert health.get("hasher") == "argon2id", health

        status, created = api.call(
            "/api/signup",
            method="POST",
            body={
                "username": "trailwalker",
                "email": "trailwalker@example.com",
                "password": PASSWORD,
            },
        )
        assert status == 201, created
        assert created["user"]["username"] == "trailwalker"
        assert created.get("csrf")

        db_path = data_dir / "accounts.sqlite"
        assert db_path.is_file(), db_path
        for path in data_dir.iterdir():
            if path.is_file():
                blob = path.read_bytes()
                assert PASSWORD.encode() not in blob, path.name

        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("SELECT username, email, password_hash FROM users").fetchone()
        finally:
            conn.close()
        assert row is not None
        username, email, password_hash = row
        assert username == "trailwalker"
        assert email == "trailwalker@example.com"
        assert password_hash.startswith("$argon2id$"), password_hash
        assert PASSWORD not in password_hash
        info = subprocess.check_output(
            [
                "php",
                "-r",
                "echo password_verify(json_decode($argv[1]), json_decode($argv[2])) ? 'ok' : 'no';",
                json.dumps(PASSWORD),
                json.dumps(password_hash),
            ],
            text=True,
        ).strip()
        assert info == "ok", info

        api2 = Api("http://127.0.0.1:18088")
        status, failed = api2.call(
            "/api/signin",
            method="POST",
            body={"login": "trailwalker", "password": "definitely-not-the-password"},
        )
        assert status == 401, failed
        assert "incorrect" in failed.get("error", "").lower()

        status, signed = api2.call(
            "/api/signin",
            method="POST",
            body={"login": "trailwalker@example.com", "password": PASSWORD},
        )
        assert status == 200, signed
        assert signed["user"]["username"] == "trailwalker"

        status, blocked = api2.call("/api/favorites", method="POST", body={"unit_id": "901S"})
        assert status == 403, blocked

        status, added = api2.call(
            "/api/favorites",
            method="POST",
            body={"unit_id": "901S"},
            csrf=True,
        )
        assert status == 200, added
        assert "901S" in added["favorites"]

        status, me = api2.call("/api/me")
        assert status == 200, me
        assert me["user"]["username"] == "trailwalker"
        assert "901S" in me["favorites"]
        print("auth tests ok (argon2id)")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
