#!/usr/bin/env bash
# Instance bootstrap for Texas Public Land Hunting (Amazon Linux 2023).
#
# provision.sh prepends a generated /opt/tplh/config.env writer to this file and
# passes the whole thing as EC2 user-data, so cloud-init runs it as root on first
# boot. It installs Apache + PHP-FPM + Node, lays out the release directories and
# the PERSISTENT auth data dir, and configures an ACME-friendly vhost. It does
# NOT clone the private repo (that needs the deploy key) — deploy.sh does that.
set -euo pipefail

exec > >(tee -a /var/log/tplh-bootstrap.log) 2>&1
echo "=== tplh bootstrap $(date -u +%FT%TZ) ==="

CONFIG_ENV="/opt/tplh/config.env"
[[ -f "$CONFIG_ENV" ]] || { echo "FATAL: $CONFIG_ENV missing"; exit 1; }
# shellcheck disable=SC1090
source "$CONFIG_ENV"

: "${DOMAIN:?}" "${ADMIN_EMAIL:?}" "${REPO_SSH:?}" "${REPO_BRANCH:?}"
DATA_DIR="${DATA_DIR:-/var/lib/tplh/data}"
APP_ROOT="${APP_ROOT:-/var/www/tplh}"
ACME_ROOT="${ACME_ROOT:-/var/www/tplh/acme}"
DOMAIN_ALIASES="${DOMAIN_ALIASES:-}"

# --- packages ----------------------------------------------------------------
echo "--- installing packages"
dnf -y update || true
# Apache, PHP 8 (with pdo_sqlite + argon2 via sodium), git, tooling.
dnf -y install \
  httpd mod_ssl \
  php php-fpm php-pdo php-mbstring php-cli php-sodium php-opcache \
  git rsync tar findutils

# Node.js 20 (Vite 7 needs Node >= 20.19). NodeSource gives a current 20.x.
if ! command -v node >/dev/null 2>&1 || [[ "$(node -v 2>/dev/null | cut -c2-3)" -lt 20 ]]; then
  echo "--- installing Node.js 20"
  curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -
  dnf -y install nodejs
fi
node -v && php -v | head -1

# --- directory layout --------------------------------------------------------
echo "--- creating directories"
install -d -m 0755 "$APP_ROOT" "$APP_ROOT/releases"
install -d -m 0755 "$ACME_ROOT/.well-known/acme-challenge"
# Persistent auth data (SQLite DB, app.key, admins.txt) OUTSIDE the release
# dirs so redeploys never touch it. php-fpm runs as apache.
install -d -o apache -g apache -m 0700 "$DATA_DIR"
# Seed the admin allowlist file (in addition to the AUTH_ADMIN_EMAILS env).
if [[ ! -f "$DATA_DIR/admins.txt" ]]; then
  printf '%s\n' "$ADMIN_EMAIL" > "$DATA_DIR/admins.txt"
  chown apache:apache "$DATA_DIR/admins.txt"
  chmod 0600 "$DATA_DIR/admins.txt"
fi

# Placeholder first release so Apache serves something before the first deploy.
if [[ ! -e "$APP_ROOT/current" ]]; then
  ph="$APP_ROOT/releases/000000-placeholder"
  install -d -m 0755 "$ph"
  cat > "$ph/index.html" <<'HTML'
<!doctype html><meta charset="utf-8"><title>Texas Public Land Hunting</title>
<body style="font-family:system-ui;margin:4rem auto;max-width:40rem;padding:0 1rem">
<h1>Texas Public Land Hunting</h1>
<p>The server is provisioned. Run <code>deploy.sh</code> to publish the site.</p>
HTML
  chown -R apache:apache "$ph"
  ln -sfn "$ph" "$APP_ROOT/current"
fi

# --- PHP-FPM: pass the app env into getenv() ---------------------------------
# The app reads AUTH_DATA_DIR / AUTH_ADMIN_EMAILS via getenv(). With php-fpm,
# Apache SetEnv does NOT reach PHP, so set them on the pool instead.
POOL="/etc/php-fpm.d/www.conf"
if ! grep -q 'tplh app env' "$POOL" 2>/dev/null; then
  echo "--- configuring php-fpm pool env"
  {
    echo ''
    echo '; tplh app env'
    echo "env[AUTH_DATA_DIR] = ${DATA_DIR}"
    echo "env[AUTH_ADMIN_EMAILS] = ${ADMIN_EMAIL}"
  } >> "$POOL"
fi

# --- Apache vhost (HTTP) -----------------------------------------------------
# Serves the SPA + PHP API from the current release, with .htaccess honored
# (AllowOverride All). The ACME challenge Alias is served from a separate dir
# with AllowOverride None so the app's force-HTTPS .htaccess cannot 301 the
# Let's Encrypt HTTP-01 challenge before a certificate exists.
echo "--- writing Apache vhost"
server_alias_line=""
if [[ -n "$DOMAIN_ALIASES" ]]; then
  server_alias_line="    ServerAlias ${DOMAIN_ALIASES}"
fi
cat > /etc/httpd/conf.d/tplh.conf <<CONF
<VirtualHost *:80>
    ServerName ${DOMAIN}
${server_alias_line}
    DocumentRoot ${APP_ROOT}/current

    # Let's Encrypt HTTP-01 challenge (must stay plain HTTP, no .htaccess).
    Alias /.well-known/acme-challenge ${ACME_ROOT}/.well-known/acme-challenge
    <Directory ${ACME_ROOT}>
        AllowOverride None
        Require all granted
    </Directory>

    <Directory ${APP_ROOT}/current>
        AllowOverride All
        Require all granted
        Options -Indexes +FollowSymLinks
    </Directory>

    ErrorLog logs/tplh_error.log
    CustomLog logs/tplh_access.log combined
</VirtualHost>
CONF

# Neutralize the default welcome page.
if [[ -f /etc/httpd/conf.d/welcome.conf ]]; then
  : > /etc/httpd/conf.d/welcome.conf
fi

# --- SELinux (guarded; AL2023 is permissive by default) ----------------------
if command -v getenforce >/dev/null 2>&1 && [[ "$(getenforce)" == "Enforcing" ]]; then
  echo "--- applying SELinux contexts"
  dnf -y install policycoreutils-python-utils || true
  semanage fcontext -a -t httpd_sys_rw_content_t "${DATA_DIR}(/.*)?" 2>/dev/null || true
  restorecon -R "$DATA_DIR" || true
  setsebool -P httpd_unified 1 || true
fi

# --- known_hosts for GitHub (so deploy.sh can clone non-interactively) -------
install -d -m 0700 /root/.ssh
if ! grep -q 'github.com' /root/.ssh/known_hosts 2>/dev/null; then
  ssh-keyscan -t ed25519,rsa github.com >> /root/.ssh/known_hosts 2>/dev/null || true
  chmod 0644 /root/.ssh/known_hosts
fi

# --- start services ----------------------------------------------------------
echo "--- enabling services"
systemctl enable --now php-fpm
# Validate config before (re)starting Apache.
apachectl configtest
systemctl enable --now httpd
systemctl reload httpd || systemctl restart httpd

echo "=== bootstrap complete. Next: add the deploy key, then run deploy.sh ==="
