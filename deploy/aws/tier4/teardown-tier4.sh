#!/usr/bin/env bash
# Tear down the Tier 4 serverless API: delete the SAM/CloudFormation stack
# (Lambda + Function URL + DynamoDB + log group) and the lambda OAC. Does NOT
# touch the shared Tier 3 S3 bucket or CloudFront distribution; it only warns
# that /api/* will point at a deleted origin until you re-wire it.
#
# Options:
#   --purge-key   also delete the app-key SSM SecureString (APP_KEY_SSM_PARAM)
#   --yes         skip the confirmation prompt
#
# Usage: deploy/aws/tier4/teardown-tier4.sh [--purge-key] [--yes]
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/lib-tier4.sh"
load_config_t4
preflight_aws

: "${STACK_NAME:?set STACK_NAME in config.sh}"
PURGE_KEY=0
ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --purge-key) PURGE_KEY=1 ;;
    --yes) ASSUME_YES=1 ;;
    *) die "unknown option: $arg" ;;
  esac
done

if [[ "$ASSUME_YES" -ne 1 ]]; then
  warn "This deletes stack '$STACK_NAME' (Lambda + Function URL + DynamoDB table ${DDB_TABLE:-}). Data will be lost."
  read -r -p "Type the stack name to confirm: " reply
  [[ "$reply" == "$STACK_NAME" ]] || die "confirmation did not match; aborting"
fi

# --- delete the CloudFormation stack -----------------------------------------
if aws cloudformation describe-stacks --stack-name "$STACK_NAME" >/dev/null 2>&1; then
  log "deleting stack $STACK_NAME"
  aws cloudformation delete-stack --stack-name "$STACK_NAME"
  log "waiting for stack deletion"
  if aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME"; then
    ok "stack deleted"
  else
    warn "stack delete did not complete cleanly; check the CloudFormation console"
  fi
else
  ok "stack $STACK_NAME not found (already deleted)"
fi

# --- delete the lambda OAC ---------------------------------------------------
OAC_NAME="$(res_name lambda-oac)"
OAC_ID="$(aws cloudfront list-origin-access-controls \
  --query "OriginAccessControlList.Items[?Name=='$OAC_NAME'].Id | [0]" --output text 2>/dev/null | sed 's/None//')"
if [[ -n "$OAC_ID" ]]; then
  OAC_ETAG="$(aws cloudfront get-origin-access-control --id "$OAC_ID" --query ETag --output text 2>/dev/null | sed 's/None//')"
  if aws cloudfront delete-origin-access-control --id "$OAC_ID" --if-match "$OAC_ETAG" >/dev/null 2>&1; then
    ok "deleted lambda OAC $OAC_ID"
  else
    warn "could not delete OAC $OAC_ID (still referenced by the distribution's /api/* origin). Re-point /api/* first, then delete it."
  fi
else
  ok "no lambda OAC to delete"
fi

# --- optionally purge the app key --------------------------------------------
if [[ "$PURGE_KEY" -eq 1 && -n "${APP_KEY_SSM_PARAM:-}" ]]; then
  if aws ssm delete-parameter --name "$APP_KEY_SSM_PARAM" >/dev/null 2>&1; then
    ok "deleted app key $APP_KEY_SSM_PARAM"
  else
    ok "app key $APP_KEY_SSM_PARAM not found"
  fi
fi

cat >&2 <<DONE

$(ok "Tier 4 serverless API torn down")
  The CloudFront /api/* behavior now points at a deleted origin. To restore the
  Tier 3 EC2 API, re-run ../provision-cdn.sh (or ../setup-tls.sh + ../deploy.sh);
  to redeploy Tier 4, run 'sam deploy' then connect-cloudfront.sh again.
DONE
