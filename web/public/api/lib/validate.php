<?php
declare(strict_types=1);

const TPLH_USERNAME_MIN = 3;
const TPLH_USERNAME_MAX = 20;
const TPLH_USERNAME_PATTERN = '/^[a-z][a-z0-9_]+$/';
const TPLH_EMAIL_MAX = 254;
const TPLH_PASSWORD_MIN = 12;
const TPLH_PASSWORD_MAX_BYTES = 128;
const TPLH_UNIT_ID_PATTERN = '/^[A-Za-z0-9._-]{1,64}$/';
const TPLH_GENERIC_LOGIN = 'Username, email, or password is incorrect.';

function tplh_load_json_list(string $filename): array
{
    $path = __DIR__ . '/' . $filename;
    $raw = file_get_contents($path);
    if ($raw === false) {
        throw new RuntimeException('Missing ' . $filename);
    }
    $data = json_decode($raw, true);
    if (!is_array($data)) {
        throw new RuntimeException('Invalid ' . $filename);
    }
    return $data;
}

function tplh_reserved_usernames(): array
{
    static $set = null;
    if ($set === null) {
        $set = array_fill_keys(tplh_load_json_list('reserved-usernames.json'), true);
    }
    return $set;
}

function tplh_common_passwords(): array
{
    static $set = null;
    if ($set === null) {
        $set = array_fill_keys(tplh_load_json_list('common-passwords.json'), true);
    }
    return $set;
}

function tplh_normalize_username(string $raw): string
{
    return strtolower(trim($raw));
}

function tplh_normalize_email(string $raw): string
{
    return strtolower(trim($raw));
}

function tplh_utf8_bytes(string $value): int
{
    return strlen($value);
}

function tplh_validate_username(string $raw): ?string
{
    $username = tplh_normalize_username($raw);
    $len = strlen($username);
    if ($len < TPLH_USERNAME_MIN || $len > TPLH_USERNAME_MAX) {
        return 'Username must be ' . TPLH_USERNAME_MIN . '–' . TPLH_USERNAME_MAX . ' characters.';
    }
    if (preg_match(TPLH_USERNAME_PATTERN, $username) !== 1) {
        return 'Username must start with a letter and use only lowercase letters, numbers, and underscores.';
    }
    if (isset(tplh_reserved_usernames()[$username])) {
        return 'That username is reserved. Choose another.';
    }
    return null;
}

function tplh_validate_email(string $raw): ?string
{
    $email = tplh_normalize_email($raw);
    if ($email === '') {
        return 'Enter an email address.';
    }
    if (strlen($email) > TPLH_EMAIL_MAX) {
        return 'Email is too long.';
    }
    $at = strpos($email, '@');
    if ($at === false || $at < 1 || $at > 64) {
        return 'Enter a valid email address.';
    }
    if (filter_var($email, FILTER_VALIDATE_EMAIL) === false) {
        return 'Enter a valid email address.';
    }
    return null;
}

function tplh_validate_password(string $password, string $email, string $username): ?string
{
    if (strlen($password) < TPLH_PASSWORD_MIN) {
        return 'Password must be at least ' . TPLH_PASSWORD_MIN . ' characters.';
    }
    if (tplh_utf8_bytes($password) > TPLH_PASSWORD_MAX_BYTES) {
        return 'Password is too long.';
    }
    $lower = strtolower($password);
    if (isset(tplh_common_passwords()[$lower])) {
        return 'Choose a less common password.';
    }
    $emailNorm = tplh_normalize_email($email);
    $userNorm = tplh_normalize_username($username);
    if ($emailNorm !== '' && $lower === $emailNorm) {
        return 'Password cannot be the same as your email.';
    }
    $local = explode('@', $emailNorm, 2)[0] ?? '';
    if (strlen($local) >= 3 && $lower === $local) {
        return 'Password cannot be the same as your email.';
    }
    if (strlen($userNorm) >= 3 && $lower === $userNorm) {
        return 'Password cannot be the same as your username.';
    }
    return null;
}

function tplh_is_valid_unit_id(string $unitId): bool
{
    return preg_match(TPLH_UNIT_ID_PATTERN, $unitId) === 1;
}
