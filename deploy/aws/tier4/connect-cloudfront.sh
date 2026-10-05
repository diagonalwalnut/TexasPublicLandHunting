#!/usr/bin/env bash
# Point the existing Tier 3 CloudFront distribution's /api/* behavior at the
# Tier 4 Lambda Function URL instead of the EC2 origin:
#   * create a CloudFront Origin Access Control of type "lambda" (SigV4),
#   * rewrite the "api-origin" to the Function URL domain + attach the OAC,
#   * switch the /api/* origin-request policy to AllViewerExceptHostHeader
#     (OAC requires CloudFront to set Host = Function URL domain for signing),
#   * grant cloudfront.amazonaws.com lambda:InvokeFunctionUrl on this dist,
#   * invalidate /api/*.
#
# Prereqs: the Tier 3 distribution exists (provision-cdn.sh) and `sam deploy` has
# created the function + Function URL. Run: deploy/aws/tier4/connect-cloudfront.sh
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/lib-tier4.sh"
load_config_t4
preflight_aws

: "${STACK_NAME:?set STACK_NAME in config.sh}" "${LAMBDA_FUNCTION:?set LAMBDA_FUNCTION}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
# Managed origin-request policy: forward all viewer headers EXCEPT Host (required
# for Lambda Function URL + OAC so the SigV4 Host matches the origin).
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

jq -e '.DistributionConfig.Origins.Items[] | select(.Id=="api-origin")' "$cfg_raw" >/dev/null \
  || die "distribution $DIST_ID has no 'api-origin' (is this the Tier 3 distribution?)"

jq --arg dom "$FURL_DOMAIN" --arg oac "$OAC_ID" --arg orp "$ORP_ALLVIEWER_NO_HOST" '
  .DistributionConfig
  | .Origins.Items |= map(
      if .Id == "api-origin" then
        .DomainName = $dom
        | .OriginAccessControlId = $oac
        | del(.S3OriginConfig)
        | .CustomOriginConfig = {
            "HTTPPort": 80,
            "HTTPSPort": 443,
            "OriginProtocolPolicy": "https-only",
            "OriginSslProtocols": { "Quantity": 1, "Items": ["TLSv1.2"] },
            "OriginReadTimeout": 30,
            "OriginKeepaliveTimeout": 5
          }
      else . end)
  | .CacheBehaviors.Items |= map(
      if .PathPattern == "/api/*" then .OriginRequestPolicyId = $orp else . end)
' "$cfg_raw" > "$cfg_new"

log "updating distribution $DIST_ID (api-origin -> $FURL_DOMAIN, OAC $OAC_ID)"
aws cloudfront update-distribution --id "$DIST_ID" --if-match "$ETAG" \
  --distribution-config "file://$cfg_new" >/dev/null
rm -f "$cfg_raw" "$cfg_new"
ok "distribution updated"

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

# --- invalidate the API path -------------------------------------------------
log "invalidating /api/*"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths '/api/*' >/dev/null
save_output CLOUDFRONT_DISTRIBUTION_ID "$DIST_ID"
save_output LAMBDA_OAC_ID "$OAC_ID"
save_output API_FUNCTION_URL "$FURL"

cat >&2 <<DONE

$(ok "CloudFront now routes /api/* to the Lambda Function URL (Tier 4)")
  Distribution : $DIST_ID
  API origin   : $FURL_DOMAIN  (OAC $OAC_ID, IAM-signed)
  Propagation  : ~5-15 min. Test: curl -sS https://$DOMAIN/api/health
DONE
