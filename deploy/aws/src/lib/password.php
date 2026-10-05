<?php
declare(strict_types=1);

/**
 * Password hashing for the Lambda accounts API.
 *
 * Prefers Argon2id via libsodium (sodium_crypto_pwhash_str), which the Bref PHP
 * runtime ships. libsodium and PHP's password_hash() both emit the standard
 * "$argon2id$v=19$m=..,t=..,p=.." PHC string, so hashes created by the local SQLite API
 * SQLite build verify here unchanged (and vice versa). Falls back to PHP
 * PASSWORD_ARGON2ID, then bcrypt, if libsodium is unavailable.
 */

/** OWASP 2023 Argon2id minimum (19 MiB). Threads stay at 1 for predictability. */
const TPLH_ARGON2_OPTS = [
    'memory_cost' => 19456,
    'time_cost' => 3,
    'threads' => 1,
];

const TPLH_BCRYPT_OPTS = ['cost' => 12];

/** libsodium equivalents of the OWASP params: t=3 ops, m=19456 KiB (19 MiB). */
const TPLH_SODIUM_OPSLIMIT = 3;
const TPLH_SODIUM_MEMLIMIT = 19456 * 1024;

/**
 * Dummy Argon2id hash used only when the login id does not exist, so a verify
 * still runs and response timing stays close to a real miss.
 */
const TPLH_DUMMY_ARGON2ID =
    '$argon2id$v=19$m=19456,t=3,p=1$eVQvZEtmUFlZMmpYN3FMZQ$Ye19uebPxzH1QzIICcHMBRaLUlcG/0r9iDuL/JRA/qc';

function tplh_sodium_argon2_available(): bool
{
    return function_exists('sodium_crypto_pwhash_str')
        && function_exists('sodium_crypto_pwhash_str_verify');
}

function tplh_password_algo(): string
{
    if (tplh_sodium_argon2_available() || defined('PASSWORD_ARGON2ID')) {
        return 'argon2id';
    }
    return 'bcrypt';
}

function tplh_hash_password(string $password): string
{
    if (tplh_sodium_argon2_available()) {
        $hash = sodium_crypto_pwhash_str($password, TPLH_SODIUM_OPSLIMIT, TPLH_SODIUM_MEMLIMIT);
    } elseif (defined('PASSWORD_ARGON2ID')) {
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
    if (strncmp($hash, '$argon2', 7) === 0) {
        if (tplh_sodium_argon2_available()) {
            return sodium_crypto_pwhash_str_verify($hash, $password);
        }
        if (defined('PASSWORD_ARGON2ID')) {
            return password_verify($password, $hash);
        }
        return false;
    }
    return password_verify($password, $hash);
}

function tplh_password_needs_rehash(string $hash): bool
{
    if (tplh_sodium_argon2_available()) {
        if (strncmp($hash, '$argon2id$', 10) !== 0) {
            return true;
        }
        return sodium_crypto_pwhash_str_needs_rehash($hash, TPLH_SODIUM_OPSLIMIT, TPLH_SODIUM_MEMLIMIT);
    }
    if (defined('PASSWORD_ARGON2ID')) {
        return password_needs_rehash($hash, PASSWORD_ARGON2ID, TPLH_ARGON2_OPTS);
    }
    return password_needs_rehash($hash, PASSWORD_BCRYPT, TPLH_BCRYPT_OPTS);
}

function tplh_verify_unknown_login(string $password): void
{
    if (tplh_sodium_argon2_available()) {
        sodium_crypto_pwhash_str_verify(TPLH_DUMMY_ARGON2ID, $password);
        return;
    }
    $dummy = defined('PASSWORD_ARGON2ID')
        ? TPLH_DUMMY_ARGON2ID
        : '$2y$12$abcdefghijklmnopqrstuvuuYW5rbm93bi11c2VyLWRlbGF5';
    password_verify($password, $dummy);
}
