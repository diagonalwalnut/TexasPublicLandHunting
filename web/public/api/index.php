<?php
declare(strict_types=1);

require_once __DIR__ . '/lib/http.php';
require_once __DIR__ . '/lib/password.php';
require_once __DIR__ . '/lib/validate.php';
require_once __DIR__ . '/lib/store.php';

header('X-Content-Type-Options: nosniff');
header('Referrer-Policy: strict-origin-when-cross-origin');
header('X-Frame-Options: DENY');
header('Cache-Control: no-store');

if (($_SERVER['REQUEST_METHOD'] ?? '') === 'OPTIONS') {
    http_response_code(204);
    exit;
}

$method = strtoupper($_SERVER['REQUEST_METHOD'] ?? 'GET');
$path = tplh_request_path();

try {
    if ($path === '/health' && $method === 'GET') {
        tplh_db();
        tplh_ok(['ok' => true, 'hasher' => tplh_password_algo()]);
    }

    if (!tplh_origin_allowed()) {
        tplh_fail(403, 'Invalid origin.');
    }

    $token = tplh_request_token();
    $session = tplh_session_row($token);
    $current = $session ? tplh_user_by_id($session['user_id']) : null;
    if ($session && !$current) {
        tplh_delete_session($token);
        $session = null;
    }

    if ($path === '/me' && $method === 'GET') {
        if (!$current || !$session) {
            tplh_ok(['user' => null, 'favorites' => [], 'csrf' => null]);
        }
        tplh_touch_session($session['token_hash']);
        tplh_ok([
            'user' => tplh_public_user($current),
            'favorites' => tplh_favorite_ids($current['id']),
            'csrf' => tplh_rotate_csrf($session['token_hash']),
        ]);
    }

    if ($path === '/signup' && $method === 'POST') {
        tplh_require_json_post();
        if (!tplh_rate_limit('signup:' . tplh_client_ip(), 8, 3600)) {
            tplh_fail(429, 'Too many attempts. Try again later.');
        }
        $body = tplh_json_input();
        $username = tplh_normalize_username(tplh_str($body, 'username', TPLH_USERNAME_MAX + 8));
        $email = tplh_normalize_email(tplh_str($body, 'email', TPLH_EMAIL_MAX + 8));
        $password = tplh_str($body, 'password', TPLH_PASSWORD_MAX_BYTES + 8);
        $err = tplh_validate_username($username)
            ?? tplh_validate_email($email)
            ?? tplh_validate_password($password, $email, $username);
        if ($err) {
            tplh_fail(400, $err);
        }
        if (tplh_username_taken($username)) {
            tplh_fail(409, 'That username is already taken.');
        }
        if (tplh_email_taken($email)) {
            tplh_fail(400, 'Could not create that account. Try signing in, or use a different email.');
        }
        $user = tplh_create_user($username, $email, tplh_hash_password($password));
        $sess = tplh_create_session($user['id']);
        tplh_set_session_cookie($sess['token']);
        tplh_ok([
            'user' => tplh_public_user($user),
            'favorites' => [],
            'csrf' => $sess['csrf'],
        ], 201);
    }

    if ($path === '/signin' && $method === 'POST') {
        tplh_require_json_post();
        if (!tplh_rate_limit('signin-ip:' . tplh_client_ip(), 30, 900)) {
            tplh_fail(429, 'Too many attempts. Try again later.');
        }
        $body = tplh_json_input();
        $login = trim(tplh_str($body, 'login', TPLH_EMAIL_MAX + 8));
        if ($login === '') {
            $login = trim(tplh_str($body, 'email', TPLH_EMAIL_MAX + 8));
        }
        $password = tplh_str($body, 'password', TPLH_PASSWORD_MAX_BYTES + 8);
        $idKey = 'signin-id:' . hash('sha256', strtolower($login));
        if (!tplh_rate_limit($idKey, 10, 900)) {
            tplh_verify_unknown_login($password);
            tplh_fail(429, 'Too many attempts. Try again later.');
        }
        $user = $login === '' ? null : tplh_find_user_by_login($login);
        if (!$user) {
            tplh_verify_unknown_login($password);
            tplh_fail(401, TPLH_GENERIC_LOGIN);
        }
        if (!tplh_verify_password($password, $user['password_hash'])) {
            tplh_fail(401, TPLH_GENERIC_LOGIN);
        }
        if (tplh_password_needs_rehash($user['password_hash'])) {
            tplh_update_password_hash($user['id'], tplh_hash_password($password));
        }
        if ($token) {
            tplh_delete_session($token);
        }
        $sess = tplh_create_session($user['id']);
        tplh_set_session_cookie($sess['token']);
        tplh_ok([
            'user' => tplh_public_user($user),
            'favorites' => tplh_favorite_ids($user['id']),
            'csrf' => $sess['csrf'],
        ]);
    }

    if ($path === '/signout' && $method === 'POST') {
        tplh_delete_session($token);
        tplh_clear_session_cookie();
        tplh_ok(['ok' => true]);
    }

    if (!$current || !$session) {
        if (in_array($path, ['/username', '/favorites', '/favorites/delete', '/beta', '/users', '/users/role'], true)) {
            tplh_fail(401, 'Sign in to continue.');
        }
        tplh_fail(404, 'Not found.');
    }

    $csrf = $_SERVER['HTTP_X_CSRF_TOKEN'] ?? '';
    if ($method !== 'GET' && $method !== 'HEAD' && !tplh_csrf_ok($session, is_string($csrf) ? $csrf : '')) {
        tplh_fail(403, 'Session expired. Sign in again.');
    }

    if ($path === '/username' && $method === 'POST') {
        tplh_require_json_post();
        $body = tplh_json_input();
        $username = tplh_normalize_username(tplh_str($body, 'username', TPLH_USERNAME_MAX + 8));
        $err = tplh_validate_username($username);
        if ($err) {
            tplh_fail(400, $err);
        }
        if (tplh_username_taken($username, $current['id'])) {
            tplh_fail(409, 'That username is already taken.');
        }
        tplh_set_username($current['id'], $username);
        $fresh = tplh_user_by_id($current['id']);
        tplh_ok(['user' => tplh_public_user($fresh ?? $current)]);
    }

    if ($path === '/favorites' && $method === 'POST') {
        tplh_require_json_post();
        $unitId = tplh_str(tplh_json_input(), 'unit_id', 64);
        if (!tplh_is_valid_unit_id($unitId)) {
            tplh_fail(400, 'That unit cannot be saved.');
        }
        tplh_add_favorite($current['id'], $unitId);
        tplh_ok(['favorites' => tplh_favorite_ids($current['id'])]);
    }

    if ($path === '/favorites/delete' && $method === 'POST') {
        tplh_require_json_post();
        $unitId = tplh_str(tplh_json_input(), 'unit_id', 64);
        if (!tplh_is_valid_unit_id($unitId)) {
            tplh_fail(400, 'That unit cannot be saved.');
        }
        tplh_remove_favorite($current['id'], $unitId);
        tplh_ok(['favorites' => tplh_favorite_ids($current['id'])]);
    }

    if ($path === '/beta' && $method === 'POST') {
        tplh_require_json_post();
        if (!tplh_is_admin($current)) {
            tplh_fail(403, 'Only administrators can use beta features.');
        }
        $enabled = (bool) (tplh_json_input()['enabled'] ?? false);
        tplh_set_beta($current['id'], $enabled);
        $fresh = tplh_user_by_id($current['id']);
        tplh_ok(['user' => tplh_public_user($fresh ?? $current)]);
    }

    if ($path === '/users' && $method === 'GET') {
        if (!tplh_is_admin($current)) {
            tplh_fail(403, 'Only administrators can manage users.');
        }
        tplh_ok(['users' => tplh_list_users()]);
    }

    if ($path === '/users/role' && $method === 'POST') {
        tplh_require_json_post();
        if (!tplh_is_admin($current)) {
            tplh_fail(403, 'Only administrators can manage users.');
        }
        if (!tplh_rate_limit('role:' . $current['id'], 30, 900)) {
            tplh_fail(429, 'Too many attempts. Try again later.');
        }
        $body = tplh_json_input();
        $targetId = tplh_str($body, 'user_id', 64);
        $role = tplh_str($body, 'role', 16);
        if (!preg_match('/^[a-f0-9]{32}$/', $targetId)) {
            tplh_fail(400, 'That account cannot be updated.');
        }
        if ($role !== 'admin' && $role !== 'user') {
            tplh_fail(400, 'Role must be administrator or standard user.');
        }
        $target = tplh_user_by_id($targetId);
        if (!$target) {
            tplh_fail(404, 'That account was not found.');
        }
        if ($role === 'user' && tplh_is_admin($target) && tplh_admin_count() <= 1) {
            tplh_fail(400, 'Keep at least one administrator.');
        }
        tplh_set_role($targetId, $role);
        $fresh = tplh_user_by_id($targetId);
        tplh_ok(['users' => tplh_list_users(), 'user' => tplh_public_user($fresh ?? $target)]);
    }

    tplh_fail(404, 'Not found.');
} catch (Throwable $e) {
    error_log('tplh-auth: ' . $e->getMessage());
    tplh_fail(500, 'Accounts are temporarily unavailable.');
}
