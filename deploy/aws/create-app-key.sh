#!/usr/bin/env bash
# One-time: create the app HMAC key as an SSM SecureString. The Lambda reads it
# at runtime to hash session + CSRF tokens.
# Safe to re-run: it will NOT overwrite an existing key unless --force is given.
#
# Usage: deploy/aws/create-app-key.sh [--force]
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/lib.sh"
load_config
preflight_aws

: "${APP_KEY_SSM_PARAM:?set APP_KEY_SSM_PARAM in config.sh}"
FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

if aws ssm get-parameter --name "$APP_KEY_SSM_PARAM" >/dev/null 2>&1; then
  if [[ "$FORCE" -eq 0 ]]; then
    ok "app key already exists at $APP_KEY_SSM_PARAM (use --force to rotate)"
    exit 0
  fi
  warn "rotating existing app key (sessions signed with the old key will be invalidated)"
fi

KEY="$(openssl rand -hex 32)"
aws ssm put-parameter \
  --name "$APP_KEY_SSM_PARAM" \
  --type SecureString \
  --value "$KEY" \
  --overwrite \
  --tier Standard \
  --description "TPLH app HMAC key (session/CSRF token hashing)" >/dev/null
ok "app key written to SSM SecureString: $APP_KEY_SSM_PARAM"
