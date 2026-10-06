<?php
declare(strict_types=1);

/**
 * Accounts data layer: DynamoDB single-table backend.
 *
 * The local dev server uses the SQLite store under web/public/api/lib/store.php.
 * Every tplh_* function keeps the same signature so index.php is reused verbatim.
 *
 * Single table (default name tplh_accounts), composite key PK + SK, TTL attr "ttl":
 *   USER#<id>        / PROFILE          -> username,email,password_hash,role,betas,created_at,updated_at
 *   USERNAME#<lower> / UNAME            -> user_id                (uniqueness reservation)
 *   EMAIL#<lower>    / EMAIL            -> user_id                (uniqueness reservation)
 *   SESSION#<hash>   / SESSION          -> user_id,csrf_hash,created_at,expires_at,ttl
 *   USER#<id>        / FAV#<unit_id>    -> unit_id,created_at
 *   RL#<key>         / RL               -> window_start,count,locked_until,ttl
 *
 * Local testing: set AUTH_DDB_ENDPOINT (e.g. http://127.0.0.1:8000) to point at
 * DynamoDB Local, and AUTH_APP_KEY to a fixed hex string instead of SSM.
 */

use Aws\DynamoDb\DynamoDbClient;
use Aws\DynamoDb\Marshaler;
use Aws\DynamoDb\Exception\DynamoDbException;
use Aws\Ssm\SsmClient;

const TPLH_SESSION_TTL = 14 * 24 * 3600;
const TPLH_COOKIE = 'tplh_sid';

function tplh_region(): string
{
    $r = getenv('AWS_REGION');
    if (!is_string($r) || $r === '') {
        $r = getenv('AUTH_DDB_REGION');
    }
    return is_string($r) && $r !== '' ? $r : 'us-east-1';
}

function tplh_table(): string
{
    $t = getenv('AUTH_TABLE');
    return is_string($t) && $t !== '' ? $t : 'tplh_accounts';
}

function tplh_ddb(): DynamoDbClient
{
    static $client = null;
    if ($client instanceof DynamoDbClient) {
        return $client;
    }
    $cfg = ['region' => tplh_region(), 'version' => '2012-08-10'];
    $endpoint = getenv('AUTH_DDB_ENDPOINT');
    if (is_string($endpoint) && $endpoint !== '') {
        $cfg['endpoint'] = $endpoint;
        $cfg['credentials'] = ['key' => 'local', 'secret' => 'local'];
    }
    $client = new DynamoDbClient($cfg);
    return $client;
}

function tplh_ssm(): SsmClient
{
    static $client = null;
    if ($client instanceof SsmClient) {
        return $client;
    }
    $client = new SsmClient(['region' => tplh_region(), 'version' => '2014-11-06']);
    return $client;
}

function tplh_marshaler(): Marshaler
{
    static $m = null;
    if ($m instanceof Marshaler) {
        return $m;
    }
    $m = new Marshaler();
    return $m;
}

/** Health/connectivity handle used by the /health endpoint. */
function tplh_db(): DynamoDbClient
{
    return tplh_ddb();
}

// ---- low-level item helpers -------------------------------------------------

function tplh_get_item(string $pk, string $sk): ?array
{
    $res = tplh_ddb()->getItem([
        'TableName' => tplh_table(),
        'Key' => ['PK' => ['S' => $pk], 'SK' => ['S' => $sk]],
        'ConsistentRead' => true,
    ]);
    $item = $res['Item'] ?? null;
    return $item ? tplh_marshaler()->unmarshalItem($item) : null;
}

function tplh_put_item(array $item, ?string $condition = null): void
{
    $args = [
        'TableName' => tplh_table(),
        'Item' => tplh_marshaler()->marshalItem($item),
    ];
    if ($condition !== null) {
        $args['ConditionExpression'] = $condition;
    }
    tplh_ddb()->putItem($args);
}

function tplh_delete_item(string $pk, string $sk): void
{
    tplh_ddb()->deleteItem([
        'TableName' => tplh_table(),
        'Key' => ['PK' => ['S' => $pk], 'SK' => ['S' => $sk]],
    ]);
}

/** @param list<array{PK:string,SK:string}> $keys */
function tplh_batch_delete_keys(array $keys): void
{
    $unique = [];
    foreach ($keys as $key) {
        $pk = (string) ($key['PK'] ?? '');
        $sk = (string) ($key['SK'] ?? '');
        if ($pk === '' || $sk === '') {
            continue;
        }
        $unique[$pk . "\0" . $sk] = ['PK' => $pk, 'SK' => $sk];
    }
    $pending = array_values($unique);
    $guard = 0;
    while ($pending !== [] && $guard < 8) {
        $guard++;
        $chunk = array_splice($pending, 0, 25);
        $requests = [];
        foreach ($chunk as $key) {
            $requests[] = ['DeleteRequest' => ['Key' => [
                'PK' => ['S' => $key['PK']],
                'SK' => ['S' => $key['SK']],
            ]]];
        }
        $res = tplh_ddb()->batchWriteItem([
            'RequestItems' => [tplh_table() => $requests],
        ]);
        foreach ($res['UnprocessedItems'][tplh_table()] ?? [] as $req) {
            $raw = $req['DeleteRequest']['Key'] ?? null;
            if (is_array($raw) && isset($raw['PK']['S'], $raw['SK']['S'])) {
                $pending[] = ['PK' => $raw['PK']['S'], 'SK' => $raw['SK']['S']];
            }
        }
    }
    if ($pending !== []) {
        throw new RuntimeException('Could not delete every account record.');
    }
}

/** @return list<array{PK:string,SK:string}> */
function tplh_query_keys(string $pk, string $skPrefix): array
{
    $keys = [];
    $params = [
        'TableName' => tplh_table(),
        'KeyConditionExpression' => 'PK = :pk AND begins_with(SK, :sk)',
        'ExpressionAttributeValues' => tplh_marshaler()->marshalItem([
            ':pk' => $pk,
            ':sk' => $skPrefix,
        ]),
        'ProjectionExpression' => 'PK, SK',
    ];
    do {
        $res = tplh_ddb()->query($params);
        foreach ($res['Items'] ?? [] as $item) {
            $row = tplh_marshaler()->unmarshalItem($item);
            $keys[] = ['PK' => (string) ($row['PK'] ?? ''), 'SK' => (string) ($row['SK'] ?? '')];
        }
        $params['ExclusiveStartKey'] = $res['LastEvaluatedKey'] ?? null;
    } while (!empty($params['ExclusiveStartKey']));
    return $keys;
}

/** @return list<array{PK:string,SK:string}> */
function tplh_session_keys_for_user(string $userId): array
{
    $keys = [];
    $params = [
        'TableName' => tplh_table(),
        'FilterExpression' => 'SK = :sk AND user_id = :uid',
        'ExpressionAttributeValues' => [
            ':sk' => ['S' => 'SESSION'],
            ':uid' => ['S' => $userId],
        ],
        'ProjectionExpression' => 'PK, SK',
    ];
    do {
        $res = tplh_ddb()->scan($params);
        foreach ($res['Items'] ?? [] as $item) {
            $row = tplh_marshaler()->unmarshalItem($item);
            $keys[] = ['PK' => (string) ($row['PK'] ?? ''), 'SK' => (string) ($row['SK'] ?? '')];
        }
        $params['ExclusiveStartKey'] = $res['LastEvaluatedKey'] ?? null;
    } while (!empty($params['ExclusiveStartKey']));
    return $keys;
}

// ---- app key + token hashing ------------------------------------------------

function tplh_app_key(): string
{
    static $key = null;
    if (is_string($key)) {
        return $key;
    }
    $direct = getenv('AUTH_APP_KEY');
    if (is_string($direct) && strlen(trim($direct)) >= 32) {
        return $key = trim($direct);
    }
    $param = getenv('AUTH_APP_KEY_SSM');
    if (is_string($param) && $param !== '') {
        $res = tplh_ssm()->getParameter(['Name' => $param, 'WithDecryption' => true]);
        $val = trim((string) ($res['Parameter']['Value'] ?? ''));
        if (strlen($val) >= 32) {
            return $key = $val;
        }
        throw new RuntimeException('App key is invalid.');
    }
    throw new RuntimeException('App key is not configured (set AUTH_APP_KEY or AUTH_APP_KEY_SSM).');
}

function tplh_hash_token(string $token): string
{
    return hash_hmac('sha256', $token, tplh_app_key());
}

// ---- rate limiting ----------------------------------------------------------

/**
 * Best-effort fixed-window limiter. Read-modify-write (not strictly atomic across
 * concurrent invocations, which rate limiting tolerates). Items self-expire via TTL.
 */
function tplh_rate_limit(string $key, int $limit, int $windowSeconds): bool
{
    $now = time();
    $pk = 'RL#' . $key;
    $row = tplh_get_item($pk, 'RL');
    $ttl = $now + $windowSeconds * 2;

    if ($row && (int) ($row['locked_until'] ?? 0) > $now) {
        return false;
    }
    if (!$row || (int) ($row['window_start'] ?? 0) + $windowSeconds < $now) {
        tplh_put_item([
            'PK' => $pk, 'SK' => 'RL',
            'window_start' => $now, 'count' => 1, 'locked_until' => 0, 'ttl' => $ttl,
        ]);
        return true;
    }
    $count = (int) ($row['count'] ?? 0) + 1;
    if ($count > $limit) {
        $lockedUntil = $now + $windowSeconds;
        tplh_put_item([
            'PK' => $pk, 'SK' => 'RL',
            'window_start' => (int) $row['window_start'], 'count' => $count,
            'locked_until' => $lockedUntil, 'ttl' => $lockedUntil + $windowSeconds,
        ]);
        return false;
    }
    tplh_put_item([
        'PK' => $pk, 'SK' => 'RL',
        'window_start' => (int) $row['window_start'], 'count' => $count,
        'locked_until' => 0, 'ttl' => $ttl,
    ]);
    return true;
}

// ---- admin role allowlist ---------------------------------------------------

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

// ---- users ------------------------------------------------------------------

/** Normalize a DynamoDB profile item to the row shape index.php expects. */
function tplh_profile_row(?array $item): ?array
{
    if (!$item) {
        return null;
    }
    return [
        'id' => (string) ($item['id'] ?? ''),
        'username' => (string) ($item['username'] ?? ''),
        'email' => (string) ($item['email'] ?? ''),
        'password_hash' => (string) ($item['password_hash'] ?? ''),
        'role' => (string) ($item['role'] ?? 'user'),
        'betas' => tplh_parse_betas($item['betas'] ?? []),
        'created_at' => (int) ($item['created_at'] ?? 0),
        'updated_at' => (int) ($item['updated_at'] ?? 0),
    ];
}

function tplh_user_by_id(string $id): ?array
{
    return tplh_profile_row(tplh_get_item('USER#' . $id, 'PROFILE'));
}

function tplh_find_user_by_login(string $login): ?array
{
    if (strpos($login, '@') !== false) {
        $ref = tplh_get_item('EMAIL#' . tplh_normalize_email($login), 'EMAIL');
    } else {
        $ref = tplh_get_item('USERNAME#' . tplh_normalize_username($login), 'UNAME');
    }
    if (!$ref || empty($ref['user_id'])) {
        return null;
    }
    return tplh_user_by_id((string) $ref['user_id']);
}

function tplh_create_user(string $username, string $email, string $passwordHash): array
{
    $now = time();
    $id = bin2hex(random_bytes(16));
    $m = tplh_marshaler();
    $t = tplh_table();
    try {
        tplh_ddb()->transactWriteItems(['TransactItems' => [
            ['Put' => [
                'TableName' => $t,
                'Item' => $m->marshalItem([
                    'PK' => 'USER#' . $id, 'SK' => 'PROFILE',
                    'id' => $id, 'username' => $username, 'email' => $email,
                    'password_hash' => $passwordHash, 'role' => 'user',
                    'betas' => '[]',
                    'created_at' => $now, 'updated_at' => $now,
                ]),
                'ConditionExpression' => 'attribute_not_exists(PK)',
            ]],
            ['Put' => [
                'TableName' => $t,
                'Item' => $m->marshalItem(['PK' => 'USERNAME#' . $username, 'SK' => 'UNAME', 'user_id' => $id]),
                'ConditionExpression' => 'attribute_not_exists(PK)',
            ]],
            ['Put' => [
                'TableName' => $t,
                'Item' => $m->marshalItem(['PK' => 'EMAIL#' . $email, 'SK' => 'EMAIL', 'user_id' => $id]),
                'ConditionExpression' => 'attribute_not_exists(PK)',
            ]],
        ]]);
    } catch (DynamoDbException $e) {
        if ($e->getAwsErrorCode() === 'TransactionCanceledException') {
            throw new RuntimeException('Account already exists.');
        }
        throw $e;
    }
    return tplh_user_by_id($id) ?? [];
}

function tplh_list_users(): array
{
    $rows = [];
    $params = [
        'TableName' => tplh_table(),
        'FilterExpression' => 'SK = :sk',
        'ExpressionAttributeValues' => [':sk' => ['S' => 'PROFILE']],
    ];
    do {
        $res = tplh_ddb()->scan($params);
        foreach ($res['Items'] ?? [] as $item) {
            $row = tplh_profile_row(tplh_marshaler()->unmarshalItem($item));
            if ($row && $row['id'] !== '') {
                $rows[] = tplh_admin_user_row($row);
            }
        }
        $params['ExclusiveStartKey'] = $res['LastEvaluatedKey'] ?? null;
    } while (!empty($params['ExclusiveStartKey']));
    usort($rows, static fn(array $a, array $b): int => strcasecmp($a['username'], $b['username']));
    return $rows;
}

function tplh_update_user_access(string $userId, ?string $role, ?array $betas): void
{
    $names = [];
    $values = [':t' => time()];
    $sets = ['updated_at = :t'];
    if ($role !== null) {
        $names['#r'] = 'role';
        $values[':r'] = $role;
        $sets[] = '#r = :r';
    }
    if ($betas !== null) {
        $values[':b'] = json_encode(tplh_parse_betas($betas));
        $sets[] = 'betas = :b';
    }
    $args = [
        'TableName' => tplh_table(),
        'Key' => ['PK' => ['S' => 'USER#' . $userId], 'SK' => ['S' => 'PROFILE']],
        'UpdateExpression' => 'SET ' . implode(', ', $sets),
        'ExpressionAttributeValues' => tplh_marshaler()->marshalItem($values),
    ];
    if ($names !== []) {
        $args['ExpressionAttributeNames'] = $names;
    }
    tplh_ddb()->updateItem($args);
}

function tplh_delete_user(string $userId): void
{
    $user = tplh_user_by_id($userId);
    if (!$user) {
        return;
    }
    tplh_batch_delete_keys(tplh_session_keys_for_user($userId));
    tplh_batch_delete_keys(tplh_query_keys('USER#' . $userId, 'FAV#'));
    $username = (string) ($user['username'] ?? '');
    $email = (string) ($user['email'] ?? '');
    $t = tplh_table();
    $items = [[
        'Delete' => [
            'TableName' => $t,
            'Key' => ['PK' => ['S' => 'USER#' . $userId], 'SK' => ['S' => 'PROFILE']],
        ],
    ]];
    if ($username !== '') {
        $items[] = ['Delete' => [
            'TableName' => $t,
            'Key' => ['PK' => ['S' => 'USERNAME#' . $username], 'SK' => ['S' => 'UNAME']],
        ]];
    }
    if ($email !== '') {
        $items[] = ['Delete' => [
            'TableName' => $t,
            'Key' => ['PK' => ['S' => 'EMAIL#' . $email], 'SK' => ['S' => 'EMAIL']],
        ]];
    }
    tplh_ddb()->transactWriteItems(['TransactItems' => $items]);
}

function tplh_update_password_hash(string $userId, string $hash): void
{
    tplh_ddb()->updateItem([
        'TableName' => tplh_table(),
        'Key' => ['PK' => ['S' => 'USER#' . $userId], 'SK' => ['S' => 'PROFILE']],
        'UpdateExpression' => 'SET password_hash = :p, updated_at = :t',
        'ExpressionAttributeValues' => tplh_marshaler()->marshalItem([':p' => $hash, ':t' => time()]),
    ]);
}

function tplh_username_taken(string $username, ?string $exceptUserId = null): bool
{
    $ref = tplh_get_item('USERNAME#' . $username, 'UNAME');
    if (!$ref) {
        return false;
    }
    if ($exceptUserId !== null && (string) ($ref['user_id'] ?? '') === $exceptUserId) {
        return false;
    }
    return true;
}

function tplh_email_taken(string $email): bool
{
    return tplh_get_item('EMAIL#' . $email, 'EMAIL') !== null;
}

function tplh_set_username(string $userId, string $username): void
{
    $current = tplh_user_by_id($userId);
    $oldUsername = $current['username'] ?? '';
    if ($oldUsername === $username) {
        tplh_ddb()->updateItem([
            'TableName' => tplh_table(),
            'Key' => ['PK' => ['S' => 'USER#' . $userId], 'SK' => ['S' => 'PROFILE']],
            'UpdateExpression' => 'SET updated_at = :t',
            'ExpressionAttributeValues' => tplh_marshaler()->marshalItem([':t' => time()]),
        ]);
        return;
    }
    $m = tplh_marshaler();
    $t = tplh_table();
    try {
        tplh_ddb()->transactWriteItems(['TransactItems' => [
            ['Put' => [
                'TableName' => $t,
                'Item' => $m->marshalItem(['PK' => 'USERNAME#' . $username, 'SK' => 'UNAME', 'user_id' => $userId]),
                'ConditionExpression' => 'attribute_not_exists(PK)',
            ]],
            ['Delete' => [
                'TableName' => $t,
                'Key' => ['PK' => ['S' => 'USERNAME#' . $oldUsername], 'SK' => ['S' => 'UNAME']],
            ]],
            ['Update' => [
                'TableName' => $t,
                'Key' => ['PK' => ['S' => 'USER#' . $userId], 'SK' => ['S' => 'PROFILE']],
                'UpdateExpression' => 'SET username = :u, updated_at = :t',
                'ExpressionAttributeValues' => $m->marshalItem([':u' => $username, ':t' => time()]),
            ]],
        ]]);
    } catch (DynamoDbException $e) {
        if ($e->getAwsErrorCode() === 'TransactionCanceledException') {
            throw new RuntimeException('That username is already taken.');
        }
        throw $e;
    }
}

// ---- sessions ---------------------------------------------------------------

function tplh_create_session(string $userId): array
{
    $token = bin2hex(random_bytes(32));
    $csrf = bin2hex(random_bytes(32));
    $now = time();
    $expires = $now + TPLH_SESSION_TTL;
    tplh_put_item([
        'PK' => 'SESSION#' . tplh_hash_token($token), 'SK' => 'SESSION',
        'token_hash' => tplh_hash_token($token),
        'user_id' => $userId,
        'csrf_hash' => tplh_hash_token($csrf),
        'created_at' => $now,
        'expires_at' => $expires,
        'ttl' => $expires,
    ]);
    return ['token' => $token, 'csrf' => $csrf];
}

function tplh_session_row(?string $token): ?array
{
    if (!$token) {
        return null;
    }
    $hash = tplh_hash_token($token);
    $row = tplh_get_item('SESSION#' . $hash, 'SESSION');
    if (!$row) {
        return null;
    }
    if ((int) ($row['expires_at'] ?? 0) <= time()) {
        return null;
    }
    return [
        'token_hash' => (string) ($row['token_hash'] ?? $hash),
        'user_id' => (string) ($row['user_id'] ?? ''),
        'csrf_hash' => (string) ($row['csrf_hash'] ?? ''),
        'created_at' => (int) ($row['created_at'] ?? 0),
        'expires_at' => (int) ($row['expires_at'] ?? 0),
    ];
}

function tplh_delete_session(?string $token): void
{
    if (!$token) {
        return;
    }
    tplh_delete_item('SESSION#' . tplh_hash_token($token), 'SESSION');
}

function tplh_touch_session(string $tokenHash): void
{
    $expires = time() + TPLH_SESSION_TTL;
    tplh_ddb()->updateItem([
        'TableName' => tplh_table(),
        'Key' => ['PK' => ['S' => 'SESSION#' . $tokenHash], 'SK' => ['S' => 'SESSION']],
        'UpdateExpression' => 'SET expires_at = :e, #ttl = :e',
        'ExpressionAttributeNames' => ['#ttl' => 'ttl'],
        'ExpressionAttributeValues' => tplh_marshaler()->marshalItem([':e' => $expires]),
    ]);
}

function tplh_rotate_csrf(string $tokenHash): string
{
    $csrf = bin2hex(random_bytes(32));
    tplh_ddb()->updateItem([
        'TableName' => tplh_table(),
        'Key' => ['PK' => ['S' => 'SESSION#' . $tokenHash], 'SK' => ['S' => 'SESSION']],
        'UpdateExpression' => 'SET csrf_hash = :c',
        'ExpressionAttributeValues' => tplh_marshaler()->marshalItem([':c' => tplh_hash_token($csrf)]),
    ]);
    return $csrf;
}

function tplh_csrf_ok(array $session, string $provided): bool
{
    if ($provided === '') {
        return false;
    }
    return hash_equals($session['csrf_hash'], tplh_hash_token($provided));
}

// ---- favorites --------------------------------------------------------------

function tplh_favorite_ids(string $userId): array
{
    $res = tplh_ddb()->query([
        'TableName' => tplh_table(),
        'KeyConditionExpression' => 'PK = :pk AND begins_with(SK, :sk)',
        'ExpressionAttributeValues' => tplh_marshaler()->marshalItem([
            ':pk' => 'USER#' . $userId,
            ':sk' => 'FAV#',
        ]),
        'ConsistentRead' => true,
    ]);
    $rows = [];
    foreach ($res['Items'] ?? [] as $item) {
        $rows[] = tplh_marshaler()->unmarshalItem($item);
    }
    usort($rows, static fn($a, $b) => ((int) ($a['created_at'] ?? 0)) <=> ((int) ($b['created_at'] ?? 0)));
    $ids = [];
    foreach ($rows as $row) {
        $unit = (string) ($row['unit_id'] ?? '');
        if ($unit !== '' && tplh_is_valid_unit_id($unit)) {
            $ids[] = $unit;
        }
    }
    return $ids;
}

function tplh_add_favorite(string $userId, string $unitId): void
{
    try {
        tplh_put_item([
            'PK' => 'USER#' . $userId, 'SK' => 'FAV#' . $unitId,
            'unit_id' => $unitId, 'created_at' => time(),
        ], 'attribute_not_exists(SK)');
    } catch (DynamoDbException $e) {
        if ($e->getAwsErrorCode() !== 'ConditionalCheckFailedException') {
            throw $e;
        }
        // Already a favorite; keep the original created_at (idempotent, like INSERT OR IGNORE).
    }
}

function tplh_remove_favorite(string $userId, string $unitId): void
{
    tplh_delete_item('USER#' . $userId, 'FAV#' . $unitId);
}

// ---- cookies + request token ------------------------------------------------

function tplh_is_https(): bool
{
    if (getenv('AUTH_FORCE_SECURE_COOKIE') === '1') {
        return true;
    }
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
