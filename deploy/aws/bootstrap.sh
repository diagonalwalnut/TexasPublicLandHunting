#!/usr/bin/env bash
# Instance bootstrap for Texas Public Land Hunting (Amazon Linux 2023, Tier 3).
#
# In Tier 3 the instance is API-ONLY: CloudFront serves the static site from S3
# and routes only /api/* here. So this installs Apache + PHP-FPM (NO Node — the
# frontend is built in CI), lays out the release dir + the PERSISTENT auth data
# dir, and writes an ACME-friendly vhost that acts as CloudFront's origin.
#
# provision.sh prepends a generated /opt/tplh/config.env writer and passes the
# whole thing as EC2 user-data (cloud-init runs it as root on first boot). It does
# NOT clone the private repo (that needs the deploy key) — deploy.sh does that.
set -euo pipefail

exec > >(tee -a /var/log/tplh-bootstrap.log) 2>&1
echo "=== tplh bootstrap $(date -u +%FT%TZ) ==="

CONFIG_ENV="/opt/tplh/config.env"
[[ -f "$CONFIG_ENV" ]] || { echo "FATAL: $CONFIG_ENV missing"; exit 1; }
# shellcheck disable=SC1090
source "$CONFIG_ENV"

: "${ADMIN_EMAIL:?}" "${REPO_SSH:?}" "${REPO_BRANCH:?}"
DATA_DIR="${DATA_DIR:-/var/lib/tplh/data}"
APP_ROOT="${APP_ROOT:-/var/www/tplh}"
ACME_ROOT="${ACME_ROOT:-/var/www/tplh/acme}"
# ServerName for the origin vhost; CloudFront still forwards Host=DOMAIN, which
# this (default) vhost also serves.
ORIGIN_NAME="${API_ORIGIN_DOMAIN:-${DOMAIN:-localhost}}"

# --- packages (NO Node; build happens in CI) ---------------------------------
echo "--- installing packages"
dnf -y update || true
dnf -y install \
  httpd mod_ssl \
  php php-fpm php-pdo php-mbstring php-cli php-sodium php-opcache \
  git rsync tar findutils

php -v | head -1

# --- directory layout --------------------------------------------------------
echo "--- creating directories"
install -d -m 0755 "$APP_ROOT" "$APP_ROOT/releases"
install -d -m 0755 "$ACME_ROOT/.well-known/acme-challenge"
# Persistent auth data (SQLite DB, app.key, admins.txt) OUTSIDE the release dirs
# so redeploys never touch it. php-fpm runs as apache.
install -d -o apache -g apache -m 0700 "$DATA_DIR"
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
<!doctype html><meta charset="utf-8"><title>TPLH API origin</title>
<body><p>API origin provisioned. Run deploy.sh to publish the /api tree.</p>
HTML
  chown -R apache:apache "$ph"
  ln -sfn "$ph" "$APP_ROOT/current"
fi

# --- PHP-FPM: pass the app env into getenv() ---------------------------------
# The app reads AUTH_DATA_DIR / AUTH_ADMIN_EMAILS via getenv(). With php-fpm,
# Apache SetEnv does NOT reach PHP, so set them on the pool instead (explicit
# env[] lines are passed even though php-fpm's default clear_env=yes).
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

# --- Apache vhost (origin) ---------------------------------------------------
# Single default vhost: serves /api/* for any Host (CloudFront forwards the
# viewer Host). AllowOverride All honors the app's api/.htaccess. The ACME Alias
# is served with AllowOverride None so the app's force-HTTPS .htaccess cannot
# 301 the Let's Encrypt HTTP-01 challenge.
echo "--- writing Apache vhost"
cat > /etc/httpd/conf.d/tplh.conf <<CONF
<VirtualHost *:80>
    ServerName ${ORIGIN_NAME}
    DocumentRoot ${APP_ROOT}/current

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
apachectl configtest
systemctl enable --now httpd
systemctl reload httpd || systemctl restart httpd

echo "=== bootstrap complete. Next: add the deploy key, then run deploy.sh ==="
