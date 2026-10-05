#!/usr/bin/env bash
# Fixture checks for cloudfront-api.jq. No AWS credentials required.
set -euo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")"
need() { command -v "$1" >/dev/null || { echo "missing $1" >&2; exit 1; }; }
need jq

DOM="fn.lambda-url.us-east-1.on.aws"
OAC="E2X762RKCYEKIA"
ORP="b689b0a8-53d0-40ab-baf2-68738e2966ac"
CACHE="4135ea2d-6df8-44a3-9df3-4b5a84be39ad"

transform() {
  jq -f cloudfront-api.jq --arg dom "$DOM" --arg oac "$OAC" --arg orp "$ORP" --arg cache "$CACHE"
}

assert() {
  local name="$1" json="$2" filter="$3"
  if ! jq -e "$filter" >/dev/null <<<"$json"; then
    echo "FAIL $name" >&2
    echo "$json" | jq . >&2
    exit 1
  fi
  echo "ok $name"
}

# The live failure: no /api behavior, so /api/health hits S3 and the custom
# error page caches index.html as a 200.
s3_only="$(cat <<'JSON' | transform
{
  "ETag": "ETAG",
  "DistributionConfig": {
    "Origins": {
      "Quantity": 1,
      "Items": [
        { "Id": "s3-static", "DomainName": "bucket.s3.us-east-1.amazonaws.com", "S3OriginConfig": { "OriginAccessIdentity": "" } }
      ]
    },
    "DefaultCacheBehavior": {
      "TargetOriginId": "s3-static",
      "ViewerProtocolPolicy": "redirect-to-https",
      "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
      "ResponseHeadersPolicyId": "rhp",
      "TrustedSigners": { "Enabled": false, "Quantity": 0 }
    },
    "CustomErrorResponses": {
      "Quantity": 2,
      "Items": [
        { "ErrorCode": 403, "ResponsePagePath": "/index.html", "ResponseCode": "200", "ErrorCachingMinTTL": 10 },
        { "ErrorCode": 404, "ResponsePagePath": "/index.html", "ResponseCode": "200", "ErrorCachingMinTTL": 10 }
      ]
    }
  }
}
JSON
)"
assert "creates /api behavior on a static-only distribution" "$s3_only" '
  ((.Origins.Items | map(select(.Id=="api-origin")) | length) == 1)
  and ((.Origins.Items | map(select(.Id=="s3-static")) | length) == 1)
  and (.CacheBehaviors.Quantity == 1)
  and (.CacheBehaviors.Items[0].PathPattern == "/api/*")
  and (.CacheBehaviors.Items[0].TargetOriginId == "api-origin")
  and (.CacheBehaviors.Items[0].CachePolicyId == "4135ea2d-6df8-44a3-9df3-4b5a84be39ad")
  and (.CacheBehaviors.Items[0].OriginRequestPolicyId == "b689b0a8-53d0-40ab-baf2-68738e2966ac")
  and ((.CacheBehaviors.Items[0].AllowedMethods.Items | index("POST")) != null)
  and (.CacheBehaviors.Items[0].ResponseHeadersPolicyId == "rhp")
  and (.CacheBehaviors.Items[0].TrustedSigners.Enabled == false)
  and (.Origins.Items[-1].DomainName == "fn.lambda-url.us-east-1.on.aws")
  and (.Origins.Items[-1].OriginAccessControlId == "E2X762RKCYEKIA")
  and (.Origins.Items[-1].S3OriginConfig | not)
  and (.CustomErrorResponses.Quantity == 0)
  and (.CustomErrorResponses.Items | not)
  and (.DefaultCacheBehavior.TargetOriginId == "s3-static")
'

# Behavior exists but still uses the placeholder origin policy and a cacheable
# forwarded-values config. Custom errors would still hide API 403/404.
placeholder="$(cat <<'JSON' | transform
{
  "DistributionConfig": {
    "Origins": {
      "Quantity": 2,
      "Items": [
        { "Id": "s3-static", "DomainName": "bucket.s3.amazonaws.com", "S3OriginConfig": { "OriginAccessIdentity": "" } },
        {
          "Id": "api-origin",
          "DomainName": "huntpubliclandintexas.com",
          "S3OriginConfig": { "OriginAccessIdentity": "" },
          "OriginPath": "/ignored"
        }
      ]
    },
    "DefaultCacheBehavior": { "TargetOriginId": "s3-static", "ViewerProtocolPolicy": "redirect-to-https" },
    "CacheBehaviors": {
      "Quantity": 1,
      "Items": [{
        "PathPattern": "/api/*",
        "TargetOriginId": "s3-static",
        "ViewerProtocolPolicy": "allow-all",
        "MinTTL": 0,
        "MaxTTL": 86400,
        "DefaultTTL": 86400,
        "ForwardedValues": { "QueryString": false, "Cookies": { "Forward": "none" } },
        "AllowedMethods": { "Quantity": 2, "Items": ["GET", "HEAD"], "CachedMethods": { "Quantity": 2, "Items": ["GET", "HEAD"] } }
      }]
    },
    "CustomErrorResponses": {
      "Quantity": 1,
      "Items": [{ "ErrorCode": 403, "ResponsePagePath": "/index.html", "ResponseCode": "200" }]
    }
  }
}
JSON
)"
assert "repairs a placeholder /api behavior" "$placeholder" '
  (([.CacheBehaviors.Items[] | select(.PathPattern=="/api/*")] | length) == 1)
  and (.CacheBehaviors.Items[0].TargetOriginId == "api-origin")
  and (.CacheBehaviors.Items[0].CachePolicyId == "4135ea2d-6df8-44a3-9df3-4b5a84be39ad")
  and (.CacheBehaviors.Items[0].ForwardedValues | not)
  and (.CacheBehaviors.Items[0].MaxTTL | not)
  and ((.CacheBehaviors.Items[0].AllowedMethods.Items | index("POST")) != null)
  and ((.CacheBehaviors.Items[0].AllowedMethods.Items | index("DELETE")) != null)
  and (([.Origins.Items[] | select(.Id=="api-origin")][0].DomainName) == "fn.lambda-url.us-east-1.on.aws")
  and (([.Origins.Items[] | select(.Id=="api-origin")][0].OriginPath) == "")
  and (([.Origins.Items[] | select(.Id=="api-origin")][0].S3OriginConfig) | not)
  and (.CustomErrorResponses.Quantity == 0)
'

echo "cloudfront-api.jq ok"
