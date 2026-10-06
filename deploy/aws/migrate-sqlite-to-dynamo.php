<?php
declare(strict_types=1);

/**
 * One-off migration: copy users + favorites from an accounts.sqlite file into
 * the DynamoDB table. Sessions and rate_limits are intentionally skipped
 * (ephemeral; users simply sign in again). Password hashes are copied verbatim
 * (standard $argon2id$ PHC strings verify unchanged under the Bref build).
 *
 * Run against a COPY of the live database, after `sam deploy` has created the
 * table. It writes directly to DynamoDB using the same env vars the Lambda uses.
 *
 * Usage:
 *   AWS_REGION=us-east-1 AUTH_TABLE=tplh_accounts \
 *     php deploy/aws/migrate-sqlite-to-dynamo.php /path/to/accounts.sqlite [--dry-run]
 *
 * Local test against DynamoDB Local:
 *   AUTH_DDB_ENDPOINT=http://127.0.0.1:8000 AWS_REGION=us-east-1 \
 *     AUTH_TABLE=tplh_accounts php deploy/aws/migrate-sqlite-to-dynamo.php sample.sqlite
 */

require __DIR__ . '/vendor/autoload.php';

use Aws\DynamoDb\DynamoDbClient;
use Aws\DynamoDb\Marshaler;

function fail(string $msg): void
{
    fwrite(STDERR, "ERROR: $msg\n");
    exit(1);
}

$args = array_values(array_filter(array_slice($argv, 1), static fn($a) => $a !== ''));
$dryRun = in_array('--dry-run', $args, true);
$args = array_values(array_filter($args, static fn($a) => $a !== '--dry-run'));
$sqlitePath = $args[0] ?? '';
if ($sqlitePath === '' || !is_file($sqlitePath)) {
    fail('pass the path to a copy of accounts.sqlite (file not found: ' . $sqlitePath . ')');
}

$region = getenv('AWS_REGION') ?: (getenv('AUTH_DDB_REGION') ?: 'us-east-1');
$table = getenv('AUTH_TABLE') ?: 'tplh_accounts';

$ddbCfg = ['region' => $region, 'version' => '2012-08-10'];
$endpoint = getenv('AUTH_DDB_ENDPOINT');
if (is_string($endpoint) && $endpoint !== '') {
    $ddbCfg['endpoint'] = $endpoint;
    $ddbCfg['credentials'] = ['key' => 'local', 'secret' => 'local'];
}
$ddb = new DynamoDbClient($ddbCfg);
$m = new Marshaler();

$pdo = new PDO('sqlite:' . $sqlitePath, null, null, [
    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
    PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
]);

fwrite(STDERR, "Migrating from $sqlitePath -> DynamoDB table '$table' (region $region)"
    . ($endpoint ? " endpoint $endpoint" : '') . ($dryRun ? ' [DRY RUN]' : '') . "\n");

$put = static function (array $item) use ($ddb, $m, $table, $dryRun): void {
    if ($dryRun) {
        return;
    }
    $ddb->putItem(['TableName' => $table, 'Item' => $m->marshalItem($item)]);
};

$users = 0;
$favorites = 0;
$userCols = [];
foreach ($pdo->query('PRAGMA table_info(users)') as $col) {
    $userCols[] = $col['name'];
}
$hasBetas = in_array('betas', $userCols, true);
$userSql = 'SELECT id, username, email, password_hash, role, created_at, updated_at'
    . ($hasBetas ? ', betas' : '')
    . ' FROM users';
foreach ($pdo->query($userSql) as $u) {
    $id = (string) $u['id'];
    $username = (string) $u['username'];
    $email = (string) $u['email'];
    $profile = [
        'PK' => 'USER#' . $id, 'SK' => 'PROFILE',
        'id' => $id,
        'username' => $username,
        'email' => $email,
        'password_hash' => (string) $u['password_hash'],
        'role' => ($u['role'] ?? 'user') === 'admin' ? 'admin' : 'user',
        'created_at' => (int) ($u['created_at'] ?? time()),
        'updated_at' => (int) ($u['updated_at'] ?? time()),
    ];
    if ($hasBetas) {
        $profile['betas'] = (string) ($u['betas'] ?? '[]');
    }
    $put($profile);
    $put(['PK' => 'USERNAME#' . strtolower($username), 'SK' => 'UNAME', 'user_id' => $id]);
    $put(['PK' => 'EMAIL#' . strtolower($email), 'SK' => 'EMAIL', 'user_id' => $id]);
    $users++;
}

// Favorites table may not exist in very old databases; guard the query.
try {
    $stmt = $pdo->query('SELECT user_id, unit_id, created_at FROM favorites');
    foreach ($stmt as $f) {
        $put([
            'PK' => 'USER#' . (string) $f['user_id'],
            'SK' => 'FAV#' . (string) $f['unit_id'],
            'unit_id' => (string) $f['unit_id'],
            'created_at' => (int) ($f['created_at'] ?? time()),
        ]);
        $favorites++;
    }
} catch (Throwable $e) {
    fwrite(STDERR, "note: skipping favorites ({$e->getMessage()})\n");
}

fwrite(STDERR, sprintf("Done: %d users, %d favorites%s.\n", $users, $favorites, $dryRun ? ' (dry run, nothing written)' : ''));
