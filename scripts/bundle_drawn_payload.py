#!/usr/bin/env python3
"""Embed drawn hunt JSON into web/public/drawn_payload.php for HostGator restore."""

from __future__ import annotations

import base64
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "web" / "public" / "data"
OUT = ROOT / "web" / "public" / "drawn_payload.php"

FILES = {
    "hunts": "drawn_hunts.json",
    "meta": "drawn_meta.json",
    "geo": "drawn_hunts.geojson",
}

TEMPLATE = '''<?php
declare(strict_types=1);

/**
 * Serves / restores drawn hunt JSON when public_html/data/drawn_*.json
 * was never uploaded (beta then shows "Could not load drawn hunt data.").
 */
const TPLH_DRAWN_BLOB = '{blob}';

function tplh_drawn_dir(): string
{{
    return __DIR__ . '/data';
}}

function tplh_drawn_files(): array
{{
    return [
        'hunts' => ['drawn_hunts.json', 'application/json'],
        'meta' => ['drawn_meta.json', 'application/json'],
        'geo' => ['drawn_hunts.geojson', 'application/geo+json'],
    ];
}}

function tplh_drawn_decode(): array
{{
    $raw = base64_decode(TPLH_DRAWN_BLOB, true);
    if ($raw === false) {{
        throw new RuntimeException('Drawn hunt package is corrupt.');
    }}
    if (function_exists('gzdecode')) {{
        $decoded = @gzdecode($raw);
        if (is_string($decoded) && $decoded !== '') {{
            $raw = $decoded;
        }}
    }}
    $files = json_decode($raw, true);
    if (!is_array($files)) {{
        throw new RuntimeException('Drawn hunt package is invalid.');
    }}
    return $files;
}}

function tplh_drawn_restore(array $files): void
{{
    $dir = tplh_drawn_dir();
    if (!is_dir($dir) && !mkdir($dir, 0755, true) && !is_dir($dir)) {{
        throw new RuntimeException('Could not create the data directory.');
    }}
    foreach ($files as $name => $contents) {{
        if (!is_string($name) || !is_string($contents) || $contents === '') {{
            continue;
        }}
        if (strpos($name, '..') !== false || strpos($name, '/') !== false) {{
            continue;
        }}
        $dest = $dir . '/' . $name;
        if (is_file($dest) && filesize($dest) > 32) {{
            continue;
        }}
        if (file_put_contents($dest, $contents, LOCK_EX) === false) {{
            throw new RuntimeException('Could not write ' . $name);
        }}
    }}
}}

function tplh_drawn_serve(string $key): void
{{
    $map = tplh_drawn_files();
    if (!isset($map[$key])) {{
        http_response_code(404);
        header('Content-Type: application/json; charset=utf-8');
        echo json_encode(['error' => 'Not found.']);
        exit;
    }}
    [$filename, $type] = $map[$key];
    $path = tplh_drawn_dir() . '/' . $filename;
    $files = tplh_drawn_decode();
    if (!is_file($path) || filesize($path) < 32) {{
        tplh_drawn_restore($files);
    }}
    $body = is_file($path) ? (string) file_get_contents($path) : (string) ($files[$filename] ?? '');
    if ($body === '') {{
        throw new RuntimeException('Drawn hunt file is empty.');
    }}
    header('Content-Type: ' . $type . '; charset=utf-8');
    header('Cache-Control: public, max-age=86400');
    header('X-Content-Type-Options: nosniff');
    echo $body;
    exit;
}}

try {{
    $name = $_GET['name'] ?? '';
    if (!is_string($name) || $name === '') {{
        $files = tplh_drawn_decode();
        tplh_drawn_restore($files);
        header('Location: /', true, 302);
        exit;
    }}
    tplh_drawn_serve($name);
}} catch (Throwable $e) {{
    error_log('tplh-drawn: ' . $e->getMessage());
    http_response_code(500);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode(['error' => 'Could not load drawn hunt data.']);
    exit;
}}
'''


def main() -> int:
    payload = {
        filename: (DATA / filename).read_text(encoding="utf-8") for filename in FILES.values()
    }
    blob = base64.b64encode(
        gzip.compress(json.dumps(payload, separators=(",", ":")).encode("utf-8"), compresslevel=9)
    ).decode("ascii")
    OUT.write_text(TEMPLATE.format(blob=blob), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
