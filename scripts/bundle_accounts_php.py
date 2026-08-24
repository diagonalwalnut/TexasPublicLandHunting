#!/usr/bin/env python3
"""Embed web/public/api into web/public/accounts.php for HostGator restore."""

from __future__ import annotations

import base64
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "web" / "public" / "api"
OUT = ROOT / "web" / "public" / "accounts.php"

SKIP_SUFFIXES = (".sqlite", ".sqlite-journal", ".sqlite-wal", ".sqlite-shm", ".key")

TEMPLATE = '''<?php
declare(strict_types=1);

/**
 * Accounts front controller. Also restores api/*.php when a failed FTP
 * upload left those files missing or 0 bytes.
 */
const TPLH_API_BLOB = '{blob}';

function tplh_api_root(): string
{{
    return __DIR__ . '/api';
}}

function tplh_api_missing(): bool
{{
    $need = [
        'index.php',
        'lib/http.php',
        'lib/store.php',
        'lib/password.php',
        'lib/validate.php',
        'lib/common-passwords.json',
        'lib/reserved-usernames.json',
    ];
    foreach ($need as $rel) {{
        $path = tplh_api_root() . '/' . $rel;
        if (!is_file($path) || filesize($path) < 32) {{
            return true;
        }}
    }}
    return false;
}}

function tplh_restore_api(): void
{{
    $raw = base64_decode(TPLH_API_BLOB, true);
    if ($raw === false) {{
        throw new RuntimeException('Accounts package is corrupt.');
    }}
    if (function_exists('gzdecode')) {{
        $decoded = @gzdecode($raw);
        if (is_string($decoded) && $decoded !== '') {{
            $raw = $decoded;
        }}
    }}
    $files = json_decode($raw, true);
    if (!is_array($files)) {{
        throw new RuntimeException('Accounts package is invalid.');
    }}
    $root = tplh_api_root();
    if (!is_dir($root) && !mkdir($root, 0755, true) && !is_dir($root)) {{
        throw new RuntimeException('Could not create the accounts directory.');
    }}
    foreach ($files as $rel => $contents) {{
        if (!is_string($rel) || !is_string($contents)) {{
            continue;
        }}
        $rel = str_replace('\\\\', '/', $rel);
        if ($rel === '' || strpos($rel, '..') !== false || isset($rel[0]) && $rel[0] === '/') {{
            continue;
        }}
        $dest = $root . '/' . $rel;
        if (is_file($dest) && filesize($dest) > 0) {{
            continue;
        }}
        $dir = dirname($dest);
        if (!is_dir($dir) && !mkdir($dir, 0755, true) && !is_dir($dir)) {{
            throw new RuntimeException('Could not create ' . $rel);
        }}
        if (file_put_contents($dest, $contents, LOCK_EX) === false) {{
            throw new RuntimeException('Could not write ' . $rel);
        }}
    }}
}}

try {{
    if (tplh_api_missing()) {{
        tplh_restore_api();
    }}
}} catch (Throwable $e) {{
    error_log('tplh-auth-restore: ' . $e->getMessage());
    http_response_code(500);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode(['error' => 'Accounts are temporarily unavailable.']);
    exit;
}}

$action = $_GET['action'] ?? '';
$method = strtoupper($_SERVER['REQUEST_METHOD'] ?? 'GET');
$script = $_SERVER['SCRIPT_NAME'] ?? '';
if ($action === '' && $method === 'GET' && substr($script, -13) === 'accounts.php') {{
    header('Location: /', true, 302);
    exit;
}}

require tplh_api_root() . '/index.php';
'''


def collect_files() -> dict[str, str]:
    files: dict[str, str] = {}
    for path in sorted(API.rglob("*")):
        if not path.is_file():
            continue
        if path.name.endswith(SKIP_SUFFIXES):
            continue
        rel = path.relative_to(API).as_posix()
        files[rel] = path.read_text(encoding="utf-8")
    if "index.php" not in files:
        raise SystemExit(f"missing {API / 'index.php'}")
    return files


def main() -> int:
    payload = json.dumps(collect_files(), separators=(",", ":")).encode("utf-8")
    blob = base64.b64encode(gzip.compress(payload, compresslevel=9)).decode("ascii")
    OUT.write_text(TEMPLATE.format(blob=blob), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(collect_files())} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
