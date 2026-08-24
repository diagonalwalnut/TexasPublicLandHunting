<?php
declare(strict_types=1);

/**
 * Accounts front controller. Also restores api/*.php when a failed FTP
 * upload left those files missing or 0 bytes.
 */
const TPLH_API_BLOB = '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';

function tplh_api_root(): string
{
    return __DIR__ . '/api';
}

function tplh_api_missing(): bool
{
    $need = [
        'index.php',
        'lib/http.php',
        'lib/store.php',
        'lib/password.php',
        'lib/validate.php',
        'lib/common-passwords.json',
        'lib/reserved-usernames.json',
    ];
    foreach ($need as $rel) {
        $path = tplh_api_root() . '/' . $rel;
        if (!is_file($path) || filesize($path) < 32) {
            return true;
        }
    }
    return false;
}

function tplh_restore_api(): void
{
    $raw = base64_decode(TPLH_API_BLOB, true);
    if ($raw === false) {
        throw new RuntimeException('Accounts package is corrupt.');
    }
    if (function_exists('gzdecode')) {
        $decoded = @gzdecode($raw);
        if (is_string($decoded) && $decoded !== '') {
            $raw = $decoded;
        }
    }
    $files = json_decode($raw, true);
    if (!is_array($files)) {
        throw new RuntimeException('Accounts package is invalid.');
    }
    $root = tplh_api_root();
    if (!is_dir($root) && !mkdir($root, 0755, true) && !is_dir($root)) {
        throw new RuntimeException('Could not create the accounts directory.');
    }
    foreach ($files as $rel => $contents) {
        if (!is_string($rel) || !is_string($contents)) {
            continue;
        }
        $rel = str_replace('\\', '/', $rel);
        if ($rel === '' || strpos($rel, '..') !== false || isset($rel[0]) && $rel[0] === '/') {
            continue;
        }
        $dest = $root . '/' . $rel;
        if (is_file($dest) && filesize($dest) > 0) {
            continue;
        }
        $dir = dirname($dest);
        if (!is_dir($dir) && !mkdir($dir, 0755, true) && !is_dir($dir)) {
            throw new RuntimeException('Could not create ' . $rel);
        }
        if (file_put_contents($dest, $contents, LOCK_EX) === false) {
            throw new RuntimeException('Could not write ' . $rel);
        }
    }
}

try {
    if (tplh_api_missing()) {
        tplh_restore_api();
    }
} catch (Throwable $e) {
    error_log('tplh-auth-restore: ' . $e->getMessage());
    http_response_code(500);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode(['error' => 'Accounts are temporarily unavailable.']);
    exit;
}

$action = $_GET['action'] ?? '';
$method = strtoupper($_SERVER['REQUEST_METHOD'] ?? 'GET');
$script = $_SERVER['SCRIPT_NAME'] ?? '';
if ($action === '' && $method === 'GET' && substr($script, -13) === 'accounts.php') {
    header('Location: /', true, 302);
    exit;
}

require tplh_api_root() . '/index.php';
