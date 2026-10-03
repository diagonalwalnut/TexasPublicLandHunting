<?php
declare(strict_types=1);

function tplh_json_input(): array
{
    $raw = file_get_contents('php://input');
    if ($raw === false || $raw === '') {
        return [];
    }
    if (strlen($raw) > 8192) {
        tplh_fail(413, 'Request is too large.');
    }
    $data = json_decode($raw, true);
    if (!is_array($data)) {
        tplh_fail(400, 'Invalid JSON.');
    }
    return $data;
}

function tplh_str(array $data, string $key, int $max = 512): string
{
    $value = $data[$key] ?? '';
    if (!is_string($value)) {
        return '';
    }
    if (strlen($value) > $max) {
        return substr($value, 0, $max);
    }
    return $value;
}

function tplh_fail(int $status, string $message): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode(['error' => $message], JSON_UNESCAPED_SLASHES);
    exit;
}

function tplh_ok(array $payload, int $status = 200): void
{
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode($payload, JSON_UNESCAPED_SLASHES);
    exit;
}

function tplh_host_only(string $hostPort): string
{
    return strtolower(explode(':', $hostPort, 2)[0]);
}

function tplh_is_loopback(string $host): bool
{
    $h = tplh_host_only($host);
    return $h === 'localhost' || $h === '127.0.0.1' || $h === '::1';
}

/**
 * Allowed browser origins (CSRF defense). Behind CloudFront + a Lambda Function
 * URL the request Host is the Function URL domain (OAC signs it), so we cannot
 * compare Origin against HTTP_HOST like the EC2 build did. Instead we match the
 * viewer Origin/Referer host against an explicit allowlist from the environment.
 */
function tplh_allowed_origin_hosts(): array
{
    static $hosts = null;
    if (is_array($hosts)) {
        return $hosts;
    }
    $hosts = [];
    $env = getenv('AUTH_ALLOWED_ORIGINS');
    if (is_string($env) && $env !== '') {
        foreach (preg_split('/[\s,]+/', $env) ?: [] as $entry) {
            $entry = strtolower(trim($entry));
            if ($entry === '') {
                continue;
            }
            $parsed = parse_url($entry, PHP_URL_HOST);
            $host = is_string($parsed) && $parsed !== '' ? $parsed : $entry;
            $hosts[$host] = true;
        }
    }
    return $hosts;
}

function tplh_origin_allowed(): bool
{
    $origin = $_SERVER['HTTP_ORIGIN'] ?? '';
    $referer = $_SERVER['HTTP_REFERER'] ?? '';
    $source = is_string($origin) && $origin !== '' ? $origin : (is_string($referer) ? $referer : '');
    if ($source === '') {
        // No cross-origin indicator (same-origin GET or non-browser client).
        return true;
    }
    $host = parse_url($source, PHP_URL_HOST);
    if (!is_string($host) || $host === '') {
        return false;
    }
    $host = strtolower($host);
    if (tplh_is_loopback($host)) {
        return true;
    }
    return isset(tplh_allowed_origin_hosts()[$host]);
}

/**
 * Hashed client IP for rate-limit keys. Behind CloudFront the viewer address is
 * the first entry of X-Forwarded-For (or the CloudFront-Viewer-Address header);
 * REMOTE_ADDR would be the CloudFront edge, not the user.
 */
function tplh_client_ip(): string
{
    $ip = '';
    $xff = $_SERVER['HTTP_X_FORWARDED_FOR'] ?? '';
    if (is_string($xff) && $xff !== '') {
        $ip = trim(explode(',', $xff)[0]);
    }
    if ($ip === '') {
        $cf = $_SERVER['HTTP_CLOUDFRONT_VIEWER_ADDRESS'] ?? '';
        if (is_string($cf) && $cf !== '') {
            $ip = trim(preg_replace('/:\d+$/', '', $cf) ?? '', '[]');
        }
    }
    if ($ip === '') {
        $ip = $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
    }
    return hash('sha256', $ip);
}

function tplh_request_path(): string
{
    $uri = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
    if (!is_string($uri) || $uri === '') {
        $uri = '/';
    }
    $uri = rawurldecode($uri);
    if (preg_match('#/api(?:/index\\.php)?(/.*)?$#', $uri, $m)) {
        $rest = $m[1] ?? '';
        if ($rest === '' || $rest === '/') {
            $action = $_GET['action'] ?? '';
            return is_string($action) && $action !== '' ? '/' . $action : '/';
        }
        return rtrim($rest, '/') ?: '/';
    }
    $info = $_SERVER['PATH_INFO'] ?? '';
    if (is_string($info) && $info !== '') {
        return rtrim($info, '/') ?: '/';
    }
    $action = $_GET['action'] ?? '';
    if (is_string($action) && $action !== '') {
        return '/' . $action;
    }
    return '/';
}

function tplh_require_json_post(): void
{
    $type = strtolower($_SERVER['CONTENT_TYPE'] ?? '');
    if ($type !== '' && strncmp($type, 'application/json', 16) !== 0) {
        tplh_fail(415, 'Send JSON.');
    }
}
