#!/usr/bin/env bash
# Create a read-only GitHub *deploy key* and install it on the instance so the
# box can clone/pull the PRIVATE repo over SSH.
#
# It will:
#   1. generate an ed25519 keypair at deploy/aws/deploy-key[.pub] (git-ignored),
#   2. register the PUBLIC key as a read-only deploy key on the repo
#      (via `gh` if available/authenticated, otherwise print manual steps),
#   3. copy the PRIVATE key to the instance at /root/.ssh/id_ed25519 over SSH.
#
# Usage: deploy/aws/make-deploy-key.sh [public-ip-or-host]
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/lib.sh"
load_config
load_outputs

HOST="${1:-${PUBLIC_IP:-}}"
[[ -n "$HOST" ]] || die "no host; pass the public IP or run provision.sh first"
PEM="$AWS_DIR/${KEY_NAME}.pem"
KEY="$AWS_DIR/deploy-key"

need ssh-keygen; need ssh; need scp

# --- 1. generate keypair -----------------------------------------------------
if [[ -f "$KEY" ]]; then
  ok "reusing existing deploy key $KEY"
else
  log "generating ed25519 deploy key"
  ssh-keygen -t ed25519 -N '' -C "tplh-deploy@${DOMAIN:-tplh}" -f "$KEY" >/dev/null
  chmod 0600 "$KEY"
  ok "created $KEY(.pub)"
fi
PUBKEY="$(cat "$KEY.pub")"

# --- 2. register as a read-only deploy key -----------------------------------
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  if gh repo deploy-key list -R "$GITHUB_REPO" 2>/dev/null | grep -q "tplh-aws"; then
    ok "a 'tplh-aws' deploy key already exists on $GITHUB_REPO"
  else
    log "adding read-only deploy key to $GITHUB_REPO via gh"
    gh repo deploy-key add "$KEY.pub" -R "$GITHUB_REPO" -t "tplh-aws-$(date +%Y%m%d)" \
      && ok "deploy key registered (read-only)"
  fi
else
  warn "gh CLI not available/authenticated — add the deploy key manually:"
  cat >&2 <<MANUAL

  GitHub -> repo Settings -> Deploy keys -> Add deploy key
    Title        : tplh-aws
    Key          : ${PUBKEY}
    Allow write  : NO (read-only)

MANUAL
  read -r -p "Press Enter once the deploy key is added on GitHub... " _ || true
fi

# --- 3. install the private key on the instance ------------------------------
[[ -f "$PEM" ]] || die "admin SSH key $PEM not found (needed to reach the box). \
If you imported your own key, set SSH opts manually and skip this step."
log "installing private deploy key on $HOST"
scp -i "$PEM" -o StrictHostKeyChecking=accept-new "$KEY" "ec2-user@${HOST}:/tmp/tplh_deploy_key"
ssh -i "$PEM" -o StrictHostKeyChecking=accept-new "ec2-user@${HOST}" \
  'sudo install -o root -g root -m 0600 /tmp/tplh_deploy_key /root/.ssh/id_ed25519 && shred -u /tmp/tplh_deploy_key && echo installed'
ok "deploy key installed at /root/.ssh/id_ed25519 on $HOST"

log "verifying the instance can reach GitHub"
if ssh -i "$PEM" "ec2-user@${HOST}" \
  'sudo GIT_SSH_COMMAND="ssh -i /root/.ssh/id_ed25519 -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new" git ls-remote '"$REPO_SSH"' HEAD >/dev/null && echo OK'; then
  ok "instance can pull the repo"
else
  warn "could not verify git access; check that the deploy key was added on GitHub"
fi

echo
ok "Done. Now run the first deploy:"
echo "  ssh -i $PEM ec2-user@${HOST} 'sudo bash /opt/tplh/deploy.sh'"
