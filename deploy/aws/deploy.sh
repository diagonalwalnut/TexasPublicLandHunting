#!/usr/bin/env bash
# Publish the PHP API ON THE INSTANCE (Tier 3). Idempotent; safe to re-run.
#
# In Tier 3 the frontend is built in CI and synced to S3 — this script only
# updates the /api tree. It pulls the private repo over SSH (deploy key), copies
# web/public/api into an atomic release, flips the `current` symlink, reloads
# php-fpm + Apache, and health-checks /api/health. No npm/build here.
#
# Invoked by an operator over SSH, or by GitHub Actions via SSM (see
# .github/workflows/deploy-aws.yml, the deploy-api job).
set -euo pipefail

CONFIG_ENV="/opt/tplh/config.env"
[[ -f "$CONFIG_ENV" ]] || { echo "FATAL: $CONFIG_ENV missing (run bootstrap first)"; exit 1; }
# shellcheck disable=SC1090
source "$CONFIG_ENV"

: "${REPO_SSH:?}" "${REPO_BRANCH:?}"
APP_ROOT="${APP_ROOT:-/var/www/tplh}"
REPO_DIR="${REPO_DIR:-/opt/tplh/repo}"
KEEP_RELEASES="${KEEP_RELEASES:-5}"
DEPLOY_KEY="${DEPLOY_KEY:-/root/.ssh/id_ed25519}"
HEALTH_HOST="${API_ORIGIN_DOMAIN:-${DOMAIN:-localhost}}"

if [[ $EUID -ne 0 ]]; then echo "FATAL: run as root (use sudo)"; exit 1; fi
log() { printf '==> %s\n' "$*"; }

if [[ ! -f "$DEPLOY_KEY" ]]; then
  cat >&2 <<MSG
FATAL: deploy key $DEPLOY_KEY not found.
Create and install it first (from your workstation):
  deploy/aws/make-deploy-key.sh
MSG
  exit 1
fi
export GIT_SSH_COMMAND="ssh -i $DEPLOY_KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"

# --- fetch source ------------------------------------------------------------
if [[ ! -d "$REPO_DIR/.git" ]]; then
  log "cloning $REPO_SSH"
  git clone --branch "$REPO_BRANCH" "$REPO_SSH" "$REPO_DIR"
else
  log "updating $REPO_DIR"
  git -C "$REPO_DIR" remote set-url origin "$REPO_SSH"
  git -C "$REPO_DIR" fetch --prune origin
fi
git -C "$REPO_DIR" checkout -B "$REPO_BRANCH" "origin/$REPO_BRANCH"
git -C "$REPO_DIR" reset --hard "origin/$REPO_BRANCH"
COMMIT="$(git -C "$REPO_DIR" rev-parse --short HEAD)"
log "at commit $COMMIT"

API_SRC="$REPO_DIR/web/public/api"
[[ -f "$API_SRC/index.php" ]] || { echo "FATAL: $API_SRC/index.php missing"; exit 1; }

# --- publish atomically ------------------------------------------------------
release="$APP_ROOT/releases/$(date -u +%Y%m%d%H%M%S)-$COMMIT"
log "publishing API to $release"
install -d -m 0755 "$release"
# The API is served under /api, so place it at <release>/api.
rsync -a --delete "$API_SRC/" "$release/api/"
# AUTH_DATA_DIR points at the persistent dir, so nothing user-generated lives in
# the release. A tiny root page is handy for a non-/api origin probe.
cat > "$release/index.html" <<HTML
<!doctype html><meta charset="utf-8"><title>TPLH API origin</title>
<body><p>API origin — commit ${COMMIT}. Static site is served by CloudFront.</p>
HTML
chown -R apache:apache "$release"
ln -sfn "$release" "$APP_ROOT/current"
log "current -> $(readlink "$APP_ROOT/current")"

# --- prune old releases ------------------------------------------------------
shopt -s nullglob
all_releases=("$APP_ROOT"/releases/*/)
shopt -u nullglob
if ((${#all_releases[@]} > KEEP_RELEASES)); then
  mapfile -t sorted < <(printf '%s\n' "${all_releases[@]}" | sort -r)
  live="$(readlink -f "$APP_ROOT/current")"
  for d in "${sorted[@]:KEEP_RELEASES}"; do
    [[ "$(readlink -f "$d")" == "$live" ]] && continue
    log "pruning $d"; rm -rf "$d"
  done
fi

# --- reload services ---------------------------------------------------------
log "reloading php-fpm + httpd"
apachectl configtest
systemctl reload php-fpm || systemctl restart php-fpm
systemctl reload httpd || systemctl restart httpd

# --- health check ------------------------------------------------------------
log "health check"
code="$(curl -fsS -o /dev/null -w '%{http_code}' -H "Host: $HEALTH_HOST" \
  http://127.0.0.1/api/health || true)"
if [[ "$code" == "200" ]]; then
  log "OK: /api/health returned 200 (commit $COMMIT live)"
else
  echo "WARNING: /api/health returned '$code' (check /var/log/httpd/tplh_error.log)"
  exit 1
fi
