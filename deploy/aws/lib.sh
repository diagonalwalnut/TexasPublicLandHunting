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
  # Always load this directory's config. An already-exported PROJECT must not
  # skip config.sh, or STACK_NAME is missing and connect-cloudfront.sh refuses
  # to run.
  if [[ -f "$AWS_DIR/config.sh" ]]; then
    # shellcheck disable=SC1091
    source "$AWS_DIR/config.sh"
  fi
  : "${AWS_REGION:?set AWS_REGION (copy config.example.sh to config.sh)}"
  : "${PROJECT:?set PROJECT}"
  # Static-site config.sh files written before the accounts API have no stack
  # name. These match samconfig.toml and the live stack, and never override a
  # value already set in config.sh.
  : "${STACK_NAME:=tplh-tier4-api}"
  : "${DDB_TABLE:=tplh_accounts}"
  : "${LAMBDA_FUNCTION:=${STACK_NAME}-api}"
  : "${APP_KEY_SSM_PARAM:=/tplh/tier4/app_key}"
  export AWS_DEFAULT_REGION="$AWS_REGION"
  export STACK_NAME DDB_TABLE LAMBDA_FUNCTION APP_KEY_SSM_PARAM
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

# CloudFront distribution id: explicit config, then .outputs.env, then by Comment.
resolve_distribution_id() {
  local id="${CLOUDFRONT_DISTRIBUTION_ID:-}"
  if [[ -z "$id" && -f "$AWS_DIR/.outputs.env" ]]; then
    id="$(grep '^CLOUDFRONT_DISTRIBUTION_ID=' "$AWS_DIR/.outputs.env" 2>/dev/null | tail -1 | cut -d= -f2-)"
  fi
  if [[ -z "$id" ]]; then
    id="$(aws cloudfront list-distributions \
      --query "DistributionList.Items[?Comment=='$PROJECT'].Id | [0]" \
      --output text 2>/dev/null | sed 's/None//')"
  fi
  printf '%s' "$id"
}

# SAM names the function "${AWS::StackName}-api". Read that from the stack, then
# fall back to LAMBDA_FUNCTION.
resolve_function_name() {
  local name=""
  name="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='ApiFunctionName'].OutputValue | [0]" \
    --output text 2>/dev/null | sed 's/None//')"
  [[ -z "$name" ]] && name="${LAMBDA_FUNCTION:-}"
  printf '%s' "$name"
}

resolve_function_url() {
  local url="" name=""
  url="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='ApiFunctionUrl'].OutputValue | [0]" \
    --output text 2>/dev/null | sed 's/None//')"
  if [[ -z "$url" ]]; then
    name="$(resolve_function_name)"
    url="$(aws lambda get-function-url-config --function-name "$name" \
      --query FunctionUrl --output text 2>/dev/null | sed 's/None//')"
  fi
  printf '%s' "$url"
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
