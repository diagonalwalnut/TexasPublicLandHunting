<?php
declare(strict_types=1);

$uri = parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH);
if (!is_string($uri)) {
    $uri = '/';
}
if (strncmp($uri, '/api', 4) === 0 || preg_match('#/accounts\\.php$#', $uri) === 1) {
    require __DIR__ . '/public/api/index.php';
    return true;
}

http_response_code(404);
header('Content-Type: application/json; charset=utf-8');
echo json_encode(['error' => 'Not found.']);
return true;
