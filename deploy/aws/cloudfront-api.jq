# Rewrite a CloudFront get-distribution-config document so /api/* is served by
# the Lambda Function URL (uncached, every method, Host set by CloudFront) and
# so origin 403/404 responses are not replaced with the cached homepage.
#
# Args: $dom (function URL host), $oac (lambda OAC id), $orp (origin request
# policy id), $cache (cache policy id).
(if type == "object" and has("DistributionConfig") then .DistributionConfig else . end)
| if any(.Origins.Items[]?; .Id == "api-origin") | not then
    .Origins.Items = ((.Origins.Items // []) + [{
      Id: "api-origin",
      OriginPath: "",
      CustomHeaders: { Quantity: 0 },
      ConnectionAttempts: 3,
      ConnectionTimeout: 10,
      OriginShield: { Enabled: false }
    }])
  else . end
| .Origins.Items |= map(
    if .Id == "api-origin" then
      .DomainName = $dom
      | .OriginPath = ""
      | .OriginAccessControlId = $oac
      | del(.S3OriginConfig)
      | .CustomOriginConfig = {
          HTTPPort: 80,
          HTTPSPort: 443,
          OriginProtocolPolicy: "https-only",
          OriginSslProtocols: { Quantity: 1, Items: ["TLSv1.2"] },
          OriginReadTimeout: 30,
          OriginKeepaliveTimeout: 5
        }
    else . end)
| .Origins.Quantity = (.Origins.Items | length)
| .DefaultCacheBehavior as $base
| [(.CacheBehaviors.Items // [])[] | select(.PathPattern == "/api/*")] as $found
| (if ($found | length) > 0 then $found[0] else $base end) as $seed
| .CacheBehaviors.Items = (
    [($seed
      | .PathPattern = "/api/*"
      | .TargetOriginId = "api-origin"
      | .ViewerProtocolPolicy = "redirect-to-https"
      | .Compress = true
      | .CachePolicyId = $cache
      | .OriginRequestPolicyId = $orp
      | .AllowedMethods = {
          Quantity: 7,
          Items: ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
          CachedMethods: { Quantity: 2, Items: ["GET", "HEAD"] }
        }
      | del(.ForwardedValues, .MinTTL, .MaxTTL, .DefaultTTL))]
    + [(.CacheBehaviors.Items // [])[] | select(.PathPattern != "/api/*")]
  )
| .CacheBehaviors.Quantity = (.CacheBehaviors.Items | length)
| .CustomErrorResponses = { Quantity: 0 }
| del(.CustomErrorResponses.Items)
