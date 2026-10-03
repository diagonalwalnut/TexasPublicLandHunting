#!/usr/bin/env bash
# Build + release the site ON THE INSTANCE. Idempotent; safe to run repeatedly.
#
# Invoked by:
#   - an operator over SSH: ssh ec2-user@HOST 'sudo bash /opt/tplh/deploy.sh'
#   - GitHub Actions via SSM run-command (see .github/workflows/deploy-aws.yml)
#
# Steps: pull the private repo over SSH (deploy key) -> npm ci + build ->
# publish to an atomic release dir -> flip the `current` symlink -> reload PHP
# and Apache -> health check. The persistent auth data dir is never touched.
set -euo pipefail

CONFIG_ENV="/opt/tplh/config.env"
[[ -f "$CONFIG_ENV" ]] || { echo "FATAL: $CONFIG_ENV missing (run bootstrap first)"; exit 1; }
# shellcheck disable=SC1090
source "$CONFIG_ENV"

: "${REPO_SSH:?}" "${REPO_BRANCH:?}" "${DOMAIN:?}"
APP_ROOT="${APP_ROOT:-/var/www/tplh}"
REPO_DIR="${REPO_DIR:-/opt/tplh/repo}"
KEEP_RELEASES="${KEEP_RELEASES:-5}"
DEPLOY_KEY="${DEPLOY_KEY:-/root/.ssh/id_ed25519}"

if [[ $EUID -ne 0 ]]; then echo "FATAL: run as root (use sudo)"; exit 1; fi

log() { printf '==> %s\n' "$*"; }

# Use the read-only GitHub deploy key for all git operations here.
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

# --- build -------------------------------------------------------------------
log "building web/ (npm ci && npm run build)"
pushd "$REPO_DIR/web" >/dev/null
npm ci --no-audit --no-fund
npm run build
[[ -f dist/index.html ]] || { echo "FATAL: build produced no dist/index.html"; exit 1; }
popd >/dev/null

# --- publish atomically ------------------------------------------------------
release="$APP_ROOT/releases/$(date -u +%Y%m%d%H%M%S)-$COMMIT"
log "publishing to $release"
mkdir -p "$release"
rsync -a --delete "$REPO_DIR/web/dist/" "$release/"
# The build strips dist/api/data, and AUTH_DATA_DIR points at the persistent
# dir, so nothing user-generated lives under the release. Fix ownership for php-fpm.
chown -R apache:apache "$release"
ln -sfn "$release" "$APP_ROOT/current"
log "current -> $(readlink "$APP_ROOT/current")"

# --- prune old releases ------------------------------------------------------
# Release dirs are named <UTC-timestamp>-<commit>, so a reverse lexical sort is
# newest-first. Keep the newest $KEEP_RELEASES, never delete the live one.
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
code="$(curl -fsS -o /dev/null -w '%{http_code}' -H 'Host: '"$DOMAIN" \
  http://127.0.0.1/api/health || true)"
if [[ "$code" == "200" ]]; then
  log "OK: /api/health returned 200 (commit $COMMIT live)"
else
  echo "WARNING: /api/health returned '$code' (check /var/log/httpd/tplh_error.log)"
  exit 1
fi
