# shellcheck shell=bash
# Shared helpers for the Texas Public Land Hunting AWS deploy scripts.
# Source this after `set -euo pipefail`.

# Directory that contains these scripts, resolved regardless of caller CWD.
AWS_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
export AWS_DIR

# ---- logging -----------------------------------------------------------------
_c() { if [[ -t 2 ]]; then printf '\033[%sm' "$1" >&2; fi; }
log()  { _c "0;36"; printf '==> %s\n' "$*" >&2; _c "0"; }
ok()   { _c "0;32"; printf '  ✓ %s\n' "$*" >&2; _c "0"; }
warn() { _c "0;33"; printf '  ! %s\n' "$*" >&2; _c "0"; }
die()  { _c "0;31"; printf 'ERROR: %s\n' "$*" >&2; _c "0"; exit 1; }

# ---- prerequisites -----------------------------------------------------------
need() { command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"; }

load_config() {
  # Auto-load config.sh from the script dir if the caller has not already.
  if [[ -z "${PROJECT:-}" && -f "$AWS_DIR/config.sh" ]]; then
    # shellcheck disable=SC1091
    source "$AWS_DIR/config.sh"
  fi
  : "${AWS_REGION:?set AWS_REGION (copy config.example.sh to config.sh)}"
  : "${PROJECT:?set PROJECT}"
  export AWS_DEFAULT_REGION="$AWS_REGION"
}

preflight_aws() {
  need aws
  need jq
  local who
  who="$(aws sts get-caller-identity --query Arn --output text 2>/dev/null)" \
    || die "AWS credentials are not configured or are invalid (aws sts get-caller-identity failed)."
  ok "AWS identity: $who"
  ok "Region: $AWS_REGION"
}

# ---- naming ------------------------------------------------------------------
res_name() { printf '%s-%s' "$PROJECT" "$1"; }   # res_name sg -> tplh-sg

# ---- tag helpers -------------------------------------------------------------
# Standard tag spec for create calls: tagspec <resource-type> <Name>
tagspec() {
  printf 'ResourceType=%s,Tags=[{Key=Name,Value=%s},{Key=Project,Value=%s},{Key=ManagedBy,Value=tplh-deploy}]' \
    "$1" "$2" "$PROJECT"
}

# Find the running/pending app instance id (by Project + Name tag), or "".
find_instance_id() {
  aws ec2 describe-instances \
    --filters "Name=tag:Project,Values=$PROJECT" \
              "Name=tag:Name,Values=$(res_name server)" \
              "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query 'Reservations[].Instances[0].InstanceId' --output text 2>/dev/null \
    | tr -d '\n' | sed 's/None//'
}

instance_public_ip() {
  aws ec2 describe-instances --instance-ids "$1" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text 2>/dev/null \
    | sed 's/None//'
}

default_vpc_id() {
  aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" \
    --query 'Vpcs[0].VpcId' --output text 2>/dev/null | sed 's/None//'
}

# Persist a key=value output for later scripts (teardown, deploy, CI setup).
OUTPUTS_FILE="${OUTPUTS_FILE:-$AWS_DIR/.outputs.env}"
save_output() {
  local key="$1" val="$2"
  touch "$OUTPUTS_FILE"
  grep -v "^${key}=" "$OUTPUTS_FILE" > "$OUTPUTS_FILE.tmp" 2>/dev/null || true
  mv "$OUTPUTS_FILE.tmp" "$OUTPUTS_FILE" 2>/dev/null || true
  printf '%s=%s\n' "$key" "$val" >> "$OUTPUTS_FILE"
}
load_outputs() { [[ -f "$OUTPUTS_FILE" ]] && { # shellcheck disable=SC1090
  source "$OUTPUTS_FILE"; }; return 0; }
