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

function tplh_origin_allowed(): bool
{
    $host = $_SERVER['HTTP_HOST'] ?? '';
    $origin = $_SERVER['HTTP_ORIGIN'] ?? '';
    if ($origin === '') {
        $referer = $_SERVER['HTTP_REFERER'] ?? '';
        if ($referer === '') {
            return true;
        }
        $refHost = parse_url($referer, PHP_URL_HOST);
        $refPort = parse_url($referer, PHP_URL_PORT);
        if (!is_string($refHost)) {
            return false;
        }
        $expect = $refPort ? $refHost . ':' . $refPort : $refHost;
        return strcasecmp($expect, $host) === 0 || (tplh_is_loopback($expect) && tplh_is_loopback($host));
    }
    $oHost = parse_url($origin, PHP_URL_HOST);
    $oPort = parse_url($origin, PHP_URL_PORT);
    if (!is_string($oHost)) {
        return false;
    }
    $expect = $oPort ? $oHost . ':' . $oPort : $oHost;
    if (strcasecmp($expect, $host) === 0) {
        return true;
    }
    return tplh_is_loopback($expect) && tplh_is_loopback($host);
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
