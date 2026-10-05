#!/usr/bin/env bash
# Tear down the accounts API: delete the SAM/CloudFormation stack
# (Lambda + Function URL + DynamoDB + log group) and the lambda OAC. Does NOT
# delete the S3 bucket or CloudFront distribution. /api/* will point at a
# deleted origin until you deploy the API again and re-run connect-cloudfront.sh.
#
# Options:
#   --purge-key   also delete the app-key SSM SecureString (APP_KEY_SSM_PARAM)
#   --yes         skip the confirmation prompt
#
# Usage: deploy/aws/teardown.sh [--purge-key] [--yes]
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/lib.sh"
load_config
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

$(ok "Accounts API torn down")
  The CloudFront /api/* behavior now points at a deleted origin. To put it
  back, run 'sam deploy' then ./connect-cloudfront.sh. The S3 bucket and
  CloudFront distribution are still there.
DONE
