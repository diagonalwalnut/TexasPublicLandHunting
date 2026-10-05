#!/usr/bin/env bash
# Point the existing Tier 3 CloudFront distribution's /api/* behavior at the
# Tier 4 Lambda Function URL instead of the EC2 origin:
#   * create a CloudFront Origin Access Control of type "lambda" (SigV4),
#   * create api-origin and the /api/* behavior when the distribution does not
#     have them yet (an S3-only distribution serves /api/* as the cached homepage),
#   * rewrite api-origin to the Function URL domain + attach the OAC,
#   * use CachingDisabled and AllViewerExceptHostHeader (OAC requires CloudFront
#     to set Host = Function URL domain for signing), and allow POST,
#   * remove the distribution-wide 403/404 -> /index.html rules, which turn API
#     errors into a 200 HTML page and then cache that page,
#   * grant cloudfront.amazonaws.com lambda:InvokeFunctionUrl on this dist,
#   * wait until the distribution is deployed, then invalidate /api/*.
#
# Prereqs: the Tier 3 distribution exists (provision-cdn.sh) and `sam deploy` has
# created the function + Function URL. Run: deploy/aws/tier4/connect-cloudfront.sh
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/lib-tier4.sh"
load_config_t4
preflight_aws
log "connect-cloudfront.sh api-routing-2"

: "${STACK_NAME:?set STACK_NAME in config.sh}" "${LAMBDA_FUNCTION:?set LAMBDA_FUNCTION}"

STACK_STATUS="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --query 'Stacks[0].StackStatus' --output text 2>/dev/null || true)"
case "$STACK_STATUS" in
  CREATE_COMPLETE|UPDATE_COMPLETE|UPDATE_ROLLBACK_COMPLETE) ;;
  "")
    die "stack $STACK_NAME was not found. From deploy/aws/tier4 run: sam build && sam deploy"
    ;;
  *)
    die "stack $STACK_NAME is $STACK_STATUS, so account create/login cannot work yet.
If the status is CREATE_FAILED, the DynamoDB table was not created. From deploy/aws/tier4:
  aws cloudformation delete-stack --stack-name $STACK_NAME
  aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME
  sam build && sam deploy
Then re-run ./connect-cloudfront.sh"
    ;;
esac

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
# Managed policies (stable, global).
# CachingDisabled: /api/* must not cache. A cached 200 homepage is what the
# sign-in dialog treats as "accounts not available".
CACHE_DISABLED="4135ea2d-6df8-44a3-9df3-4b5a84be39ad"
# AllViewerExceptHostHeader: OAC requires CloudFront to set Host to the Function URL.
ORP_ALLVIEWER_NO_HOST="b689b0a8-53d0-40ab-baf2-68738e2966ac"

DIST_ID="$(resolve_distribution_id)"
[[ -n "$DIST_ID" ]] || die "no CloudFront distribution found (run the Tier 3 provision-cdn.sh first, or set CLOUDFRONT_DISTRIBUTION_ID)"
DIST_ARN="arn:aws:cloudfront::${ACCOUNT_ID}:distribution/${DIST_ID}"
ok "distribution $DIST_ID"

FURL="$(resolve_function_url)"
[[ -n "$FURL" ]] || die "no Function URL found (run 'sam deploy' first)"
FURL_DOMAIN="${FURL#https://}"; FURL_DOMAIN="${FURL_DOMAIN#http://}"; FURL_DOMAIN="${FURL_DOMAIN%%/*}"
ok "function URL domain $FURL_DOMAIN"

# --- Origin Access Control (type: lambda) ------------------------------------
OAC_NAME="$(res_name lambda-oac)"
OAC_ID="$(aws cloudfront list-origin-access-controls \
  --query "OriginAccessControlList.Items[?Name=='$OAC_NAME'].Id | [0]" --output text 2>/dev/null | sed 's/None//')"
if [[ -z "$OAC_ID" ]]; then
  log "creating lambda OAC $OAC_NAME"
  OAC_ID="$(aws cloudfront create-origin-access-control \
    --origin-access-control-config "Name=$OAC_NAME,SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=lambda" \
    --query 'OriginAccessControl.Id' --output text)"
fi
ok "lambda OAC $OAC_ID"

# --- rewrite the distribution config -----------------------------------------
cfg_raw="$(mktemp)"; cfg_new="$(mktemp)"
aws cloudfront get-distribution-config --id "$DIST_ID" > "$cfg_raw"
ETAG="$(jq -r '.ETag' "$cfg_raw")"
log "distribution before update:"
jq -r '
  .DistributionConfig
  | "  origins: " + ([.Origins.Items[] | "\(.Id)=\(.DomainName)"] | join(" ")),
    "  behaviors: " + (
        if ((.CacheBehaviors.Items // []) | length) == 0 then "(none)"
        else ([.CacheBehaviors.Items[] | "\(.PathPattern)->\(.TargetOriginId)"] | join(" "))
        end
      ),
    "  custom errors: " + ((.CustomErrorResponses.Quantity // 0) | tostring)
' "$cfg_raw" >&2

jq -f "$T4_DIR/cloudfront-api.jq" \
  --arg dom "$FURL_DOMAIN" --arg oac "$OAC_ID" \
  --arg orp "$ORP_ALLVIEWER_NO_HOST" --arg cache "$CACHE_DISABLED" \
  "$cfg_raw" > "$cfg_new"

jq -e --arg dom "$FURL_DOMAIN" --arg orp "$ORP_ALLVIEWER_NO_HOST" --arg cache "$CACHE_DISABLED" '
  ([.Origins.Items[] | select(.Id == "api-origin")] | length) == 1
  and ([.Origins.Items[] | select(.Id == "api-origin")][0].DomainName == $dom)
  and (([.CacheBehaviors.Items[] | select(.PathPattern == "/api/*")] | length) == 1)
  and .CacheBehaviors.Items[0].PathPattern == "/api/*"
  and .CacheBehaviors.Items[0].TargetOriginId == "api-origin"
  and .CacheBehaviors.Items[0].CachePolicyId == $cache
  and .CacheBehaviors.Items[0].OriginRequestPolicyId == $orp
  and (.CacheBehaviors.Items[0].AllowedMethods.Items | index("POST") != null)
  and .CustomErrorResponses.Quantity == 0
' "$cfg_new" >/dev/null \
  || die "refusing to publish a CloudFront config that would still serve /api/* from S3"

log "updating distribution $DIST_ID (api-origin -> $FURL_DOMAIN, OAC $OAC_ID)"
aws cloudfront update-distribution --id "$DIST_ID" --if-match "$ETAG" \
  --distribution-config "file://$cfg_new" >/dev/null
rm -f "$cfg_raw" "$cfg_new"
ok "distribution update submitted"

# --- allow CloudFront to invoke the Function URL -----------------------------
FUNC_NAME="$(resolve_function_name)"
[[ -n "$FUNC_NAME" ]] || die "could not resolve the Lambda function name (run 'sam deploy' first)"
log "granting cloudfront.amazonaws.com lambda:InvokeFunctionUrl on $FUNC_NAME"
if aws lambda add-permission \
  --function-name "$FUNC_NAME" \
  --statement-id "AllowCloudFrontServicePrincipal" \
  --action lambda:InvokeFunctionUrl \
  --principal cloudfront.amazonaws.com \
  --source-arn "$DIST_ARN" \
  --function-url-auth-type AWS_IAM >/dev/null 2>&1; then
  ok "invoke permission added"
else
  ok "invoke permission already present"
fi

# Invalidate only after the new config is live. Invalidating first lets the
# still-deployed S3 behavior cache /index.html for /api/* again. /* is required
# as well: a 403/404 rewritten to /index.html is cached on the default behavior.
log "waiting for distribution $DIST_ID to deploy (often 5-15 minutes; leave this running)"
aws cloudfront wait distribution-deployed --id "$DIST_ID"
log "invalidating /* and /api/*"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths '/*' '/api/*' >/dev/null
save_output CLOUDFRONT_DISTRIBUTION_ID "$DIST_ID"
save_output LAMBDA_OAC_ID "$OAC_ID"
save_output API_FUNCTION_URL "$FURL"

log "checking https://$DOMAIN/api/health"
health_hdr="$(mktemp)"; health_body="$(mktemp)"
health_ok=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
  curl -sS -D "$health_hdr" -o "$health_body" "https://$DOMAIN/api/health" --max-time 25 || true
  if grep -qi '^content-type: application/json' "$health_hdr" && grep -q '"ok":true' "$health_body"; then
    health_ok=1
    break
  fi
  log "health is not JSON yet; waiting for the invalidation"
  sleep 10
done
if [[ "$health_ok" != 1 ]]; then
  echo "---- https://$DOMAIN/api/health headers ----" >&2
  cat "$health_hdr" >&2 || true
  echo "---- body ----" >&2
  head -c 400 "$health_body" >&2 || true
  echo >&2
  die "account health is still the website HTML. The distribution update did not take effect."
fi
rm -f "$health_hdr" "$health_body"

cat >&2 <<DONE

$(ok "CloudFront now routes /api/* to the Lambda Function URL (Tier 4)")
  Distribution : $DIST_ID
  API origin   : $FURL_DOMAIN  (OAC $OAC_ID, IAM-signed)
  Health       : {"ok":true} from https://$DOMAIN/api/health
DONE
