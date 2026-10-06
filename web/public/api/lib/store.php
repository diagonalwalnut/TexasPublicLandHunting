<?php
declare(strict_types=1);

const TPLH_SESSION_TTL = 14 * 24 * 3600;
const TPLH_COOKIE = 'tplh_sid';

function tplh_data_dir(): string
{
    $env = getenv('AUTH_DATA_DIR');
    if (is_string($env) && $env !== '') {
        return rtrim($env, '/');
    }
    return dirname(__DIR__) . '/data';
}

function tplh_ensure_data_dir(): string
{
    $dir = tplh_data_dir();
    if (!is_dir($dir) && !mkdir($dir, 0700, true) && !is_dir($dir)) {
        throw new RuntimeException('Account storage is not writable.');
    }
    $ht = $dir . '/.htaccess';
    if (!is_file($ht)) {
        file_put_contents($ht, "Require all denied\nDeny from all\n");
    }
    return $dir;
}

function tplh_app_key(): string
{
    $path = tplh_ensure_data_dir() . '/app.key';
    if (!is_file($path)) {
        $key = bin2hex(random_bytes(32));
        if (file_put_contents($path, $key, LOCK_EX) === false) {
            throw new RuntimeException('Could not write app key.');
        }
        chmod($path, 0600);
        return $key;
    }
    $key = trim((string) file_get_contents($path));
    if (strlen($key) < 32) {
        throw new RuntimeException('App key is invalid.');
    }
    return $key;
}

function tplh_hash_token(string $token): string
{
    return hash_hmac('sha256', $token, tplh_app_key());
}

function tplh_db(): PDO
{
    static $pdo = null;
    if ($pdo instanceof PDO) {
        return $pdo;
    }
    $dir = tplh_ensure_data_dir();
    $path = $dir . '/accounts.sqlite';
    $exists = is_file($path);
    $pdo = new PDO('sqlite:' . $path, null, null, [
        PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        PDO::ATTR_EMULATE_PREPARES => false,
    ]);
    if (!$exists) {
        chmod($path, 0600);
    }
    $pdo->exec('PRAGMA foreign_keys = ON');
    $pdo->exec('PRAGMA journal_mode = WAL');
    $pdo->exec('PRAGMA busy_timeout = 5000');
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )'
    );
    $userCols = [];
    foreach ($pdo->query('PRAGMA table_info(users)') as $col) {
        $userCols[] = $col['name'];
    }
    if (!in_array('role', $userCols, true)) {
        $pdo->exec("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'");
    }
    if (!in_array('betas', $userCols, true)) {
        $pdo->exec("ALTER TABLE users ADD COLUMN betas TEXT NOT NULL DEFAULT '[]'");
    }
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            csrf_hash TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )'
    );
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS favorites (
            user_id TEXT NOT NULL,
            unit_id TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            PRIMARY KEY (user_id, unit_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )'
    );
    $pdo->exec(
        'CREATE TABLE IF NOT EXISTS rate_limits (
            key TEXT PRIMARY KEY,
            window_start INTEGER NOT NULL,
            count INTEGER NOT NULL,
            locked_until INTEGER NOT NULL DEFAULT 0
        )'
    );
    return $pdo;
}

function tplh_rate_limit(string $key, int $limit, int $windowSeconds): bool
{
    $db = tplh_db();
    $now = time();
    $db->beginTransaction();
    try {
        $stmt = $db->prepare('SELECT window_start, count, locked_until FROM rate_limits WHERE key = :k');
        $stmt->execute([':k' => $key]);
        $row = $stmt->fetch();
        if ($row && (int) $row['locked_until'] > $now) {
            $db->commit();
            return false;
        }
        if (!$row || (int) $row['window_start'] + $windowSeconds < $now) {
            $upsert = $db->prepare(
                'INSERT INTO rate_limits (key, window_start, count, locked_until)
                 VALUES (:k, :w, 1, 0)
                 ON CONFLICT(key) DO UPDATE SET window_start = :w2, count = 1, locked_until = 0'
            );
            $upsert->execute([':k' => $key, ':w' => $now, ':w2' => $now]);
            $db->commit();
            return true;
        }
        $count = (int) $row['count'] + 1;
        if ($count > $limit) {
            $lock = $db->prepare('UPDATE rate_limits SET count = :c, locked_until = :u WHERE key = :k');
            $lock->execute([':c' => $count, ':u' => $now + $windowSeconds, ':k' => $key]);
            $db->commit();
            return false;
        }
        $upd = $db->prepare('UPDATE rate_limits SET count = :c WHERE key = :k');
        $upd->execute([':c' => $count, ':k' => $key]);
        $db->commit();
        return true;
    } catch (Throwable $e) {
        if ($db->inTransaction()) {
            $db->rollBack();
        }
        throw $e;
    }
}

function tplh_client_ip(): string
{
    $ip = $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
    return hash('sha256', $ip);
}

function tplh_admin_emails(): array
{
    $emails = [];
    $env = getenv('AUTH_ADMIN_EMAILS');
    if (is_string($env) && $env !== '') {
        foreach (explode(',', $env) as $part) {
            $email = strtolower(trim($part));
            if ($email !== '') {
                $emails[$email] = true;
            }
        }
    }
    $file = tplh_data_dir() . '/admins.txt';
    if (is_file($file)) {
        $lines = file($file, FILE_IGNORE_NEW_LINES);
        if (is_array($lines)) {
            foreach ($lines as $line) {
                $line = trim((string) $line);
                if ($line === '' || $line[0] === '#') {
                    continue;
                }
                $emails[strtolower($line)] = true;
            }
        }
    }
    return $emails;
}

function tplh_beta_catalog(): array
{
    return [
        ['id' => 'oregon', 'label' => 'Oregon beta'],
    ];
}

function tplh_beta_ids(): array
{
    $ids = [];
    foreach (tplh_beta_catalog() as $beta) {
        $ids[] = (string) $beta['id'];
    }
    return $ids;
}

/** Keep only known beta ids. Accepts a JSON string or a list. */
function tplh_parse_betas(mixed $raw): array
{
    if (is_string($raw)) {
        $decoded = json_decode($raw, true);
        $raw = is_array($decoded) ? $decoded : [];
    }
    if (!is_array($raw)) {
        return [];
    }
    $known = array_fill_keys(tplh_beta_ids(), true);
    $out = [];
    foreach ($raw as $id) {
        if (is_string($id) && isset($known[$id])) {
            $out[$id] = true;
        }
    }
    $ids = array_keys($out);
    sort($ids);
    return $ids;
}

function tplh_user_betas(array $row): array
{
    return tplh_parse_betas($row['betas'] ?? []);
}

/**
 * The email allowlist promotes. It does not demote, so an admin granted in the
 * Users screen stays an admin after the next sign-in.
 */
function tplh_sync_role(array $row): array
{
    $current = isset($row['role']) && $row['role'] === 'admin' ? 'admin' : 'user';
    $allowlisted = isset(tplh_admin_emails()[strtolower((string) ($row['email'] ?? ''))]);
    if ($allowlisted && $current !== 'admin') {
        tplh_update_user_access((string) $row['id'], 'admin', null);
        $row['role'] = 'admin';
    }
    return $row;
}

function tplh_is_admin(array $row): bool
{
    $row = tplh_sync_role($row);
    return ($row['role'] ?? '') === 'admin';
}

function tplh_public_user(array $row): array
{
    $summary = tplh_admin_user_row($row);
    return [
        'id' => $summary['id'],
        'username' => $summary['username'],
        'email' => $summary['email'],
        'role' => $summary['role'],
        'betas' => $summary['role'] === 'admin' ? tplh_beta_ids() : $summary['betas'],
    ];
}

function tplh_admin_user_row(array $row): array
{
    $row = tplh_sync_role($row);
    $role = ($row['role'] ?? 'user') === 'admin' ? 'admin' : 'user';
    return [
        'id' => (string) $row['id'],
        'username' => (string) $row['username'],
        'email' => (string) $row['email'],
        'role' => $role,
        'betas' => tplh_user_betas($row),
        'created_at' => (int) ($row['created_at'] ?? 0),
    ];
}

function tplh_find_user_by_login(string $login): ?array
{
    $db = tplh_db();
    if (strpos($login, '@') !== false) {
        $stmt = $db->prepare('SELECT * FROM users WHERE email = :v');
        $stmt->execute([':v' => tplh_normalize_email($login)]);
    } else {
        $stmt = $db->prepare('SELECT * FROM users WHERE username = :v');
        $stmt->execute([':v' => tplh_normalize_username($login)]);
    }
    $row = $stmt->fetch();
    return $row ?: null;
}

function tplh_user_by_id(string $id): ?array
{
    $stmt = tplh_db()->prepare('SELECT * FROM users WHERE id = :id');
    $stmt->execute([':id' => $id]);
    $row = $stmt->fetch();
    return $row ?: null;
}

function tplh_create_user(string $username, string $email, string $passwordHash): array
{
    $db = tplh_db();
    $now = time();
    $id = bin2hex(random_bytes(16));
    $stmt = $db->prepare(
        'INSERT INTO users (id, username, email, password_hash, created_at, updated_at)
         VALUES (:id, :u, :e, :p, :c, :t)'
    );
    $stmt->execute([
        ':id' => $id,
        ':u' => $username,
        ':e' => $email,
        ':p' => $passwordHash,
        ':c' => $now,
        ':t' => $now,
    ]);
    return tplh_user_by_id($id) ?? [];
}

function tplh_list_users(): array
{
    $loaded = tplh_db()->query('SELECT * FROM users ORDER BY username COLLATE NOCASE')->fetchAll();
    $rows = [];
    foreach ($loaded as $row) {
        $rows[] = tplh_admin_user_row($row);
    }
    return $rows;
}

function tplh_update_user_access(string $userId, ?string $role, ?array $betas): void
{
    $sets = ['updated_at = :t'];
    $params = [':t' => time(), ':id' => $userId];
    if ($role !== null) {
        $sets[] = 'role = :r';
        $params[':r'] = $role;
    }
    if ($betas !== null) {
        $sets[] = 'betas = :b';
        $params[':b'] = json_encode(tplh_parse_betas($betas));
    }
    $sql = 'UPDATE users SET ' . implode(', ', $sets) . ' WHERE id = :id';
    $stmt = tplh_db()->prepare($sql);
    $stmt->execute($params);
}

function tplh_update_password_hash(string $userId, string $hash): void
{
    $stmt = tplh_db()->prepare(
        'UPDATE users SET password_hash = :p, updated_at = :t WHERE id = :id'
    );
    $stmt->execute([':p' => $hash, ':t' => time(), ':id' => $userId]);
}

function tplh_username_taken(string $username, ?string $exceptUserId = null): bool
{
    if ($exceptUserId) {
        $stmt = tplh_db()->prepare('SELECT 1 FROM users WHERE username = :u AND id != :id');
        $stmt->execute([':u' => $username, ':id' => $exceptUserId]);
    } else {
        $stmt = tplh_db()->prepare('SELECT 1 FROM users WHERE username = :u');
        $stmt->execute([':u' => $username]);
    }
    return (bool) $stmt->fetchColumn();
}

function tplh_email_taken(string $email): bool
{
    $stmt = tplh_db()->prepare('SELECT 1 FROM users WHERE email = :e');
    $stmt->execute([':e' => $email]);
    return (bool) $stmt->fetchColumn();
}

function tplh_set_username(string $userId, string $username): void
{
    $stmt = tplh_db()->prepare(
        'UPDATE users SET username = :u, updated_at = :t WHERE id = :id'
    );
    $stmt->execute([':u' => $username, ':t' => time(), ':id' => $userId]);
}

function tplh_create_session(string $userId): array
{
    $token = bin2hex(random_bytes(32));
    $csrf = bin2hex(random_bytes(32));
    $now = time();
    $stmt = tplh_db()->prepare(
        'INSERT INTO sessions (token_hash, user_id, csrf_hash, created_at, expires_at)
         VALUES (:th, :uid, :ch, :c, :e)'
    );
    $stmt->execute([
        ':th' => tplh_hash_token($token),
        ':uid' => $userId,
        ':ch' => tplh_hash_token($csrf),
        ':c' => $now,
        ':e' => $now + TPLH_SESSION_TTL,
    ]);
    return ['token' => $token, 'csrf' => $csrf];
}

function tplh_session_row(?string $token): ?array
{
    if (!$token) {
        return null;
    }
    $stmt = tplh_db()->prepare(
        'SELECT * FROM sessions WHERE token_hash = :h AND expires_at > :now'
    );
    $stmt->execute([':h' => tplh_hash_token($token), ':now' => time()]);
    $row = $stmt->fetch();
    return $row ?: null;
}

function tplh_delete_session(?string $token): void
{
    if (!$token) {
        return;
    }
    $stmt = tplh_db()->prepare('DELETE FROM sessions WHERE token_hash = :h');
    $stmt->execute([':h' => tplh_hash_token($token)]);
}

function tplh_touch_session(string $tokenHash): void
{
    $stmt = tplh_db()->prepare('UPDATE sessions SET expires_at = :e WHERE token_hash = :h');
    $stmt->execute([':e' => time() + TPLH_SESSION_TTL, ':h' => $tokenHash]);
}

function tplh_rotate_csrf(string $tokenHash): string
{
    $csrf = bin2hex(random_bytes(32));
    $stmt = tplh_db()->prepare('UPDATE sessions SET csrf_hash = :c WHERE token_hash = :h');
    $stmt->execute([':c' => tplh_hash_token($csrf), ':h' => $tokenHash]);
    return $csrf;
}

function tplh_csrf_ok(array $session, string $provided): bool
{
    if ($provided === '') {
        return false;
    }
    return hash_equals($session['csrf_hash'], tplh_hash_token($provided));
}

function tplh_favorite_ids(string $userId): array
{
    $stmt = tplh_db()->prepare('SELECT unit_id FROM favorites WHERE user_id = :id ORDER BY created_at');
    $stmt->execute([':id' => $userId]);
    $ids = [];
    foreach ($stmt as $row) {
        if (tplh_is_valid_unit_id($row['unit_id'])) {
            $ids[] = $row['unit_id'];
        }
    }
    return $ids;
}

function tplh_add_favorite(string $userId, string $unitId): void
{
    $stmt = tplh_db()->prepare(
        'INSERT OR IGNORE INTO favorites (user_id, unit_id, created_at) VALUES (:u, :i, :c)'
    );
    $stmt->execute([':u' => $userId, ':i' => $unitId, ':c' => time()]);
}

function tplh_remove_favorite(string $userId, string $unitId): void
{
    $stmt = tplh_db()->prepare('DELETE FROM favorites WHERE user_id = :u AND unit_id = :i');
    $stmt->execute([':u' => $userId, ':i' => $unitId]);
}

function tplh_is_https(): bool
{
    if (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') {
        return true;
    }
    return (($_SERVER['SERVER_PORT'] ?? '') === '443');
}

function tplh_set_session_cookie(string $token): void
{
    setcookie(TPLH_COOKIE, $token, [
        'expires' => time() + TPLH_SESSION_TTL,
        'path' => '/',
        'secure' => tplh_is_https(),
        'httponly' => true,
        'samesite' => 'Lax',
    ]);
}

function tplh_clear_session_cookie(): void
{
    setcookie(TPLH_COOKIE, '', [
        'expires' => time() - 3600,
        'path' => '/',
        'secure' => tplh_is_https(),
        'httponly' => true,
        'samesite' => 'Lax',
    ]);
}

function tplh_request_token(): ?string
{
    $cookie = $_COOKIE[TPLH_COOKIE] ?? '';
    if (!is_string($cookie) || !preg_match('/^[a-f0-9]{64}$/', $cookie)) {
        return null;
    }
    return $cookie;
}
