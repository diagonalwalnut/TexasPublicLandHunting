# shellcheck shell=bash
# Shared helpers for the Tier 4 (serverless) deploy scripts.
# Reuses the Tier 3 lib.sh (log/ok/warn/die/need/preflight_aws/save_output) but
# loads THIS directory's config.sh and keeps a separate .outputs.env.

T4_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
export T4_DIR

# shellcheck source=../lib.sh
source "$T4_DIR/../lib.sh"

# Tier 4 keeps its own outputs file (Tier 3 outputs live in ../.outputs.env).
# Consumed by save_output/load_outputs in lib.sh.
# shellcheck disable=SC2034
OUTPUTS_FILE="$T4_DIR/.outputs.env"

load_config_t4() {
  if [[ -z "${PROJECT:-}" && -f "$T4_DIR/config.sh" ]]; then
    # shellcheck disable=SC1091
    source "$T4_DIR/config.sh"
  fi
  : "${AWS_REGION:?set AWS_REGION (copy config.example.sh to config.sh)}"
  : "${PROJECT:?set PROJECT}"
  export AWS_DEFAULT_REGION="$AWS_REGION"
}

# Resolve the Tier 3 CloudFront distribution id: explicit config, then the Tier 3
# outputs file, then by distribution Comment (== PROJECT).
resolve_distribution_id() {
  local id="${CLOUDFRONT_DISTRIBUTION_ID:-}"
  if [[ -z "$id" && -f "$T4_DIR/../.outputs.env" ]]; then
    id="$(grep '^CLOUDFRONT_DISTRIBUTION_ID=' "$T4_DIR/../.outputs.env" 2>/dev/null | tail -1 | cut -d= -f2-)"
  fi
  if [[ -z "$id" ]]; then
    id="$(aws cloudfront list-distributions \
      --query "DistributionList.Items[?Comment=='$PROJECT'].Id | [0]" \
      --output text 2>/dev/null | sed 's/None//')"
  fi
  printf '%s' "$id"
}

# Resolve the Function URL for the deployed Lambda (from the SAM stack output,
# else by function name).
resolve_function_url() {
  local url=""
  url="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='ApiFunctionUrl'].OutputValue | [0]" \
    --output text 2>/dev/null | sed 's/None//')"
  if [[ -z "$url" ]]; then
    url="$(aws lambda get-function-url-config --function-name "${LAMBDA_FUNCTION}" \
      --query FunctionUrl --output text 2>/dev/null | sed 's/None//')"
  fi
  printf '%s' "$url"
}
