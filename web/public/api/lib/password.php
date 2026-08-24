<?php
declare(strict_types=1);

/** OWASP 2023 Argon2id minimum (19 MiB). Threads stay at 1 for shared hosting. */
const TPLH_ARGON2_OPTS = [
    'memory_cost' => 19456,
    'time_cost' => 3,
    'threads' => 1,
];

const TPLH_BCRYPT_OPTS = ['cost' => 12];

/**
 * Dummy Argon2id hash used only when the login id does not exist, so
 * password_verify still runs and response timing stays close to a real miss.
 */
const TPLH_DUMMY_ARGON2ID =
    '$argon2id$v=19$m=19456,t=3,p=1$eVQvZEtmUFlZMmpYN3FMZQ$Ye19uebPxzH1QzIICcHMBRaLUlcG/0r9iDuL/JRA/qc';

function tplh_password_algo(): string
{
    return defined('PASSWORD_ARGON2ID') ? 'argon2id' : 'bcrypt';
}

function tplh_hash_password(string $password): string
{
    if (defined('PASSWORD_ARGON2ID')) {
        $hash = password_hash($password, PASSWORD_ARGON2ID, TPLH_ARGON2_OPTS);
    } else {
        $hash = password_hash($password, PASSWORD_BCRYPT, TPLH_BCRYPT_OPTS);
    }
    if (!is_string($hash) || $hash === '') {
        throw new RuntimeException('Could not hash password.');
    }
    return $hash;
}

function tplh_verify_password(string $password, string $hash): bool
{
    if ($hash === '') {
        return false;
    }
    return password_verify($password, $hash);
}

function tplh_password_needs_rehash(string $hash): bool
{
    if (defined('PASSWORD_ARGON2ID')) {
        return password_needs_rehash($hash, PASSWORD_ARGON2ID, TPLH_ARGON2_OPTS);
    }
    return password_needs_rehash($hash, PASSWORD_BCRYPT, TPLH_BCRYPT_OPTS);
}

function tplh_verify_unknown_login(string $password): void
{
    $dummy = defined('PASSWORD_ARGON2ID')
        ? TPLH_DUMMY_ARGON2ID
        : '$2y$12$abcdefghijklmnopqrstuvuuYW5rbm93bi11c2VyLWRlbGF5';
    password_verify($password, $dummy);
}
