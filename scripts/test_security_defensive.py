#!/usr/bin/env python3
"""
Defensive security checks for the accounts API and static sink inventory.

These assert secure *rejection* / safe configuration. They do not send exploit
payload corpora or attempt to break out of the application.
"""

from __future__ import annotations

import json
import os
import re
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
    def __init__(self, base: str, origin: str = "http://localhost:5173") -> None:
        self.base = base.rstrip("/")
        self.origin = origin
        self.jar = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = ""

    def call(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict | bytes | None = None,
        csrf: bool = False,
        origin: str | None = None,
        content_type: str | None = "application/json",
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, dict | str]:
        data = None
        headers = {"Accept": "application/json"}
        use_origin = self.origin if origin is None else origin
        if use_origin != "":
            headers["Origin"] = use_origin
        if body is not None:
            if isinstance(body, (bytes, bytearray)):
                data = bytes(body)
            else:
                data = json.dumps(body).encode()
            if content_type:
                headers["Content-Type"] = content_type
        if csrf:
            headers["X-CSRF-Token"] = self.csrf
        if extra_headers:
            headers.update(extra_headers)
        req = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=20) as res:
                raw = res.read().decode()
                status = res.status
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode()
            status = exc.code
        try:
            payload: dict | str = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw
        if isinstance(payload, dict) and payload.get("csrf"):
            self.csrf = str(payload["csrf"])
        return status, payload


def wait_health(api: Api) -> None:
    last = ""
    for _ in range(40):
        try:
            status, payload = api.call("/api/index.php?action=health")
            if status == 200 and isinstance(payload, dict) and payload.get("ok"):
                return
            last = repr(payload)
        except OSError as exc:
            last = str(exc)
        time.sleep(0.1)
    raise AssertionError(f"API did not become ready: {last}")


def assert_error(status: int, payload: dict | str, code: int, *needles: str) -> None:
    assert status == code, (status, payload)
    text = payload.get("error", "") if isinstance(payload, dict) else str(payload)
    for needle in needles:
        assert needle.lower() in text.lower(), (needle, text)


def static_sink_inventory() -> None:
    """Fail if high-risk browser/PHP sinks appear in app source."""
    roots = [
        ROOT / "web" / "src",
        ROOT / "web" / "public" / "api",
        ROOT / "deploy" / "aws" / "src",
    ]
    banned = [
        (re.compile(r"dangerouslySetInnerHTML"), "dangerouslySetInnerHTML"),
        (re.compile(r"\beval\s*\("), "eval("),
        (re.compile(r"document\.write\s*\("), "document.write"),
        (re.compile(r"\bshell_exec\s*\("), "shell_exec"),
        (re.compile(r"\bpassthru\s*\("), "passthru"),
        (re.compile(r"\bproc_open\s*\("), "proc_open"),
    ]
    for root in roots:
        for path in root.rglob("*"):
            if path.suffix not in {".ts", ".tsx", ".js", ".jsx", ".php"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern, label in banned:
                if pattern.search(text):
                    raise AssertionError(f"Banned sink {label} in {path.relative_to(ROOT)}")

    # Search filters must stay client-side (no /api usage in filters modules).
    for rel in (
        "web/src/filters.ts",
        "web/src/profiles/unitGrid/filters.ts",
        "web/src/oregon/filters.ts",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "/api" not in text, rel
        assert "fetch(" not in text, rel


def main() -> int:
    static_sink_inventory()

    data_dir = Path(tempfile.mkdtemp(prefix="tplh-sec-"))
    env = os.environ.copy()
    env["AUTH_DATA_DIR"] = str(data_dir)
    env["AUTH_ADMIN_EMAILS"] = "rangeboss@example.com"
    proc = subprocess.Popen(
        ["php", "-S", "127.0.0.1:18089", str(ROUTER)],
        cwd=str(ROOT / "web"),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    api = Api("http://127.0.0.1:18089")
    try:
        wait_health(api)

        # --- Origin allowlist ---
        bad_origin = Api("http://127.0.0.1:18089", origin="https://evil.example")
        status, payload = bad_origin.call("/api/index.php?action=me")
        assert_error(status, payload, 403, "origin")

        # Empty Origin still allowed (same-origin / non-browser).
        no_origin = Api("http://127.0.0.1:18089", origin="")
        status, payload = no_origin.call("/api/index.php?action=health")
        assert status == 200, payload

        # --- Signup validation rejects unexpected characters ---
        status, payload = api.call(
            "/api/index.php?action=signup",
            method="POST",
            body={
                "username": "bad;drop",
                "email": "ok@example.com",
                "password": PASSWORD,
            },
        )
        assert_error(status, payload, 400, "username")

        status, payload = api.call(
            "/api/index.php?action=signup",
            method="POST",
            body={
                "username": "okuser",
                "email": "not-an-email",
                "password": PASSWORD,
            },
        )
        assert_error(status, payload, 400, "email")

        status, payload = api.call(
            "/api/index.php?action=signup",
            method="POST",
            body={
                "username": "okuser",
                "email": "okuser@example.com",
                "password": "short",
            },
        )
        assert_error(status, payload, 400, "password")

        # --- Malformed / oversized JSON ---
        status, payload = api.call(
            "/api/index.php?action=signup",
            method="POST",
            body=b"{not-json",
        )
        assert_error(status, payload, 400, "json")

        status, payload = api.call(
            "/api/index.php?action=signup",
            method="POST",
            body=b'{"username":"' + (b"a" * 9000) + b'"}',
        )
        assert status == 413, payload

        # --- Happy path user + CSRF gate ---
        status, created = api.call(
            "/api/index.php?action=signup",
            method="POST",
            body={
                "username": "secwalker",
                "email": "secwalker@example.com",
                "password": PASSWORD,
            },
        )
        assert status == 201 and isinstance(created, dict), created
        assert created["user"]["role"] == "user"

        status, payload = api.call(
            "/api/index.php?action=favorites",
            method="POST",
            body={"unit_id": "901S"},
            csrf=False,
        )
        assert_error(status, payload, 403, "session")

        status, payload = api.call(
            "/api/index.php?action=favorites",
            method="POST",
            body={"unit_id": "../../../etc/passwd"},
            csrf=True,
        )
        assert_error(status, payload, 400, "unit")

        status, payload = api.call(
            "/api/index.php?action=favorites",
            method="POST",
            body={"unit_id": "901S"},
            csrf=True,
        )
        assert status == 200, payload

        # Non-admin cannot hit admin list or mutate corrections.
        status, payload = api.call("/api/index.php?action=admin/users")
        assert_error(status, payload, 403, "admin")

        status, payload = api.call(
            "/api/index.php?action=corrections",
            method="POST",
            body={"unitId": "2547", "note": "nope"},
            csrf=True,
        )
        assert_error(status, payload, 403, "admin")

        # Anonymous cannot mutate; can read corrections.
        anon = Api("http://127.0.0.1:18089")
        status, payload = anon.call("/api/index.php?action=corrections")
        assert status == 200, payload
        status, payload = anon.call(
            "/api/index.php?action=corrections",
            method="POST",
            body={"unitId": "2547", "note": "nope"},
        )
        assert_error(status, payload, 401, "sign in")

        # Admin bootstrap via allowlisted email (documented design risk).
        admin = Api("http://127.0.0.1:18089")
        status, created = admin.call(
            "/api/index.php?action=signup",
            method="POST",
            body={
                "username": "rangeboss",
                "email": "rangeboss@example.com",
                "password": PASSWORD,
            },
        )
        assert status == 201 and isinstance(created, dict), created
        assert created["user"]["role"] == "admin"

        status, payload = admin.call("/api/index.php?action=admin/users")
        assert status == 200 and isinstance(payload, dict), payload
        emails = {u["email"] for u in payload["users"]}
        assert "secwalker@example.com" in emails

        # Path-style action cannot escape the API router.
        status, payload = api.call("/api/index.php?action=../../health")
        assert status in (404, 403), payload

        # Local data dir must keep .htaccess deny for Apache-style hosts.
        htaccess = ROOT / "web" / "public" / "api" / "data" / ".htaccess"
        assert htaccess.is_file()
        assert "Deny from all" in htaccess.read_text(encoding="utf-8") or "Require all denied" in htaccess.read_text(
            encoding="utf-8"
        )

        print("security defensive checks ok")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
