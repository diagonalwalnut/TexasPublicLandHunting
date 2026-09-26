#!/usr/bin/env python3
"""Restore missing drawn hunt JSON via drawn_payload.php and serve it."""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAYLOAD = ROOT / "web" / "public" / "drawn_payload.php"
EXPECTED = ROOT / "web" / "public" / "data" / "drawn_hunts.json"


def main() -> int:
    if not PAYLOAD.is_file():
        raise SystemExit(f"missing {PAYLOAD}; run scripts/bundle_drawn_payload.py")

    staging = Path(tempfile.mkdtemp(prefix="tplh-drawn-"))
    (staging / "drawn_payload.php").write_bytes(PAYLOAD.read_bytes())
    proc = subprocess.Popen(
        ["php", "-S", "127.0.0.1:18091", "-t", str(staging)],
        cwd=str(staging),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        hunts = None
        last = ""
        for _ in range(40):
            try:
                with urllib.request.urlopen(
                    "http://127.0.0.1:18091/drawn_payload.php?name=hunts", timeout=20
                ) as res:
                    hunts = json.loads(res.read().decode())
                    if res.status == 200 and isinstance(hunts, list) and hunts:
                        break
            except Exception as exc:
                last = str(exc)
            time.sleep(0.1)
        else:
            raise AssertionError(f"drawn payload did not serve hunts: {last}")

        restored = staging / "data" / "drawn_hunts.json"
        assert restored.is_file() and restored.stat().st_size > 32, restored
        assert len(hunts) >= 300, len(hunts)
        expected = json.loads(EXPECTED.read_text())
        assert hunts[0]["id"] == expected[0]["id"]

        with urllib.request.urlopen(
            "http://127.0.0.1:18091/drawn_payload.php?name=meta", timeout=20
        ) as res:
            meta = json.loads(res.read().decode())
        assert meta.get("seasonYear") == "2026-27"
        assert meta.get("huntCount") == len(hunts)

        print(f"drawn payload tests ok ({len(hunts)} hunts)")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
