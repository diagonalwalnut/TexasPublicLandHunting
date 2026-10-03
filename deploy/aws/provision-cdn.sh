#!/usr/bin/env bash
# Tier 3 static front: private S3 bucket + CloudFront distribution that serves the
# built site from S3 (default behavior, cached) and routes /api/* to the EC2 API
# origin (uncached, cookies/CSRF/Host forwarded). Also creates the OAC, a
# response-headers policy (ported from web/public/.htaccess), and the public ACM
# certificate. Idempotent-ish: reuses resources it can find by name/comment.
#
# Run AFTER provision.sh (and ideally after the API origin has TLS via
# setup-tls.sh). Usage: deploy/aws/provision-cdn.sh
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/lib.sh"
load_config
preflight_aws
load_outputs

: "${S3_BUCKET:?set S3_BUCKET in config.sh}"
: "${DOMAIN:?}" "${API_ORIGIN_DOMAIN:?}"
case "$S3_BUCKET" in *REPLACE*) die "set a real, globally-unique S3_BUCKET in config.sh" ;; esac
[[ "$AWS_REGION" == "us-east-1" ]] || warn "ACM cert for CloudFront must be in us-east-1; AWS_REGION=$AWS_REGION"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

# AWS-managed policy IDs (stable, global):
CACHE_OPTIMIZED="658327ea-f89d-4fab-a63d-7e88639e58f6"   # CachingOptimized
CACHE_DISABLED="4135ea2d-6df8-44a3-9df3-4b5a84be39ad"    # CachingDisabled
ORP_ALLVIEWER="216adef6-5c7f-47e4-b989-5492eafa07d3"     # AllViewer origin request policy

# --- S3 bucket (private) -----------------------------------------------------
if aws s3api head-bucket --bucket "$S3_BUCKET" >/dev/null 2>&1; then
  ok "bucket $S3_BUCKET exists"
else
  log "creating bucket $S3_BUCKET"
  if [[ "$AWS_REGION" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "$S3_BUCKET" >/dev/null
  else
    aws s3api create-bucket --bucket "$S3_BUCKET" \
      --create-bucket-configuration "LocationConstraint=$AWS_REGION" >/dev/null
  fi
fi
aws s3api put-public-access-block --bucket "$S3_BUCKET" \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true >/dev/null
aws s3api put-bucket-encryption --bucket "$S3_BUCKET" \
  --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}' >/dev/null
ok "bucket secured (private + encrypted)"
save_output S3_BUCKET "$S3_BUCKET"

# --- Origin Access Control ---------------------------------------------------
OAC_NAME="$(res_name oac)"
OAC_ID="$(aws cloudfront list-origin-access-controls \
  --query "OriginAccessControlList.Items[?Name=='$OAC_NAME'].Id | [0]" --output text 2>/dev/null | sed 's/None//')"
if [[ -z "$OAC_ID" ]]; then
  log "creating origin access control $OAC_NAME"
  OAC_ID="$(aws cloudfront create-origin-access-control \
    --origin-access-control-config "Name=$OAC_NAME,SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3" \
    --query 'OriginAccessControl.Id' --output text)"
fi
ok "OAC $OAC_ID"

# --- Response headers policy (security headers from web/public/.htaccess) -----
RHP_NAME="$(res_name security-headers)"
RHP_ID="$(aws cloudfront list-response-headers-policies --type custom \
  --query "ResponseHeadersPolicyList.Items[?ResponseHeadersPolicy.ResponseHeadersPolicyConfig.Name=='$RHP_NAME'].ResponseHeadersPolicy.Id | [0]" \
  --output text 2>/dev/null | sed 's/None//')"
if [[ -z "$RHP_ID" ]]; then
  log "creating response headers policy $RHP_NAME"
  rhp_cfg="$(mktemp)"
  cat > "$rhp_cfg" <<JSON
{
  "Name": "$RHP_NAME",
  "Comment": "TPLH security headers (from web/public/.htaccess)",
  "SecurityHeadersConfig": {
    "ContentTypeOptions": { "Override": true },
    "FrameOptions": { "Override": true, "FrameOption": "DENY" },
    "ReferrerPolicy": { "Override": true, "ReferrerPolicy": "strict-origin-when-cross-origin" },
    "StrictTransportSecurity": { "Override": true, "IncludeSubdomains": true, "Preload": false, "AccessControlMaxAgeSec": 31536000 }
  },
  "CustomHeadersConfig": {
    "Quantity": 2,
    "Items": [
      { "Header": "Cross-Origin-Opener-Policy", "Value": "same-origin", "Override": true },
      { "Header": "Permissions-Policy", "Value": "camera=(), microphone=(), geolocation=()", "Override": true }
    ]
  }
}
JSON
  RHP_ID="$(aws cloudfront create-response-headers-policy \
    --response-headers-policy-config "file://$rhp_cfg" \
    --query 'ResponseHeadersPolicy.Id' --output text)"
  rm -f "$rhp_cfg"
fi
ok "response headers policy $RHP_ID"

# --- ACM certificate (us-east-1, DNS-validated) ------------------------------
CERT_ARN="${ACM_CERT_ARN:-}"
if [[ -z "$CERT_ARN" ]]; then
  CERT_ARN="$(aws acm list-certificates --region us-east-1 \
    --query "CertificateSummaryList[?DomainName=='$DOMAIN'].CertificateArn | [0]" --output text 2>/dev/null | sed 's/None//')"
fi
if [[ -z "$CERT_ARN" ]]; then
  log "requesting ACM certificate for $DOMAIN $DOMAIN_ALIASES"
  san_args=()
  for a in ${DOMAIN_ALIASES:-}; do san_args+=(--subject-alternative-names "$a"); done
  CERT_ARN="$(aws acm request-certificate --region us-east-1 \
    --domain-name "$DOMAIN" "${san_args[@]}" \
    --validation-method DNS \
    --query CertificateArn --output text)"
  ok "requested $CERT_ARN"
  sleep 3
fi
save_output ACM_CERT_ARN "$CERT_ARN"

CERT_STATUS="$(aws acm describe-certificate --region us-east-1 --certificate-arn "$CERT_ARN" \
  --query 'Certificate.Status' --output text)"
if [[ "$CERT_STATUS" != "ISSUED" ]]; then
  log "certificate is $CERT_STATUS; DNS validation records:"
  aws acm describe-certificate --region us-east-1 --certificate-arn "$CERT_ARN" \
    --query 'Certificate.DomainValidationOptions[].ResourceRecord' --output table >&2 || true
  if [[ -n "${HOSTED_ZONE_ID:-}" ]]; then
    log "creating validation records in hosted zone $HOSTED_ZONE_ID"
    aws acm describe-certificate --region us-east-1 --certificate-arn "$CERT_ARN" \
      --query 'Certificate.DomainValidationOptions[].ResourceRecord' --output json \
      | jq -c 'unique_by(.Name)[]' | while read -r rr; do
        name="$(jq -r .Name <<<"$rr")"; value="$(jq -r .Value <<<"$rr")"
        aws route53 change-resource-record-sets --hosted-zone-id "$HOSTED_ZONE_ID" \
          --change-batch "{\"Changes\":[{\"Action\":\"UPSERT\",\"ResourceRecordSet\":{\"Name\":\"$name\",\"Type\":\"CNAME\",\"TTL\":300,\"ResourceRecords\":[{\"Value\":\"$value\"}]}}]}" >/dev/null || true
      done
    log "waiting for certificate validation (can take a few minutes)"
    aws acm wait certificate-validated --region us-east-1 --certificate-arn "$CERT_ARN"
    ok "certificate issued"
  else
    die "Add the DNS validation CNAME(s) above at your DNS provider, then re-run this script. (Set HOSTED_ZONE_ID to automate.)"
  fi
fi
ok "ACM certificate ready"

# --- CloudFront distribution -------------------------------------------------
DIST_ID="$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Comment=='$PROJECT'].Id | [0]" --output text 2>/dev/null | sed 's/None//')"
S3_ORIGIN_DOMAIN="${S3_BUCKET}.s3.${AWS_REGION}.amazonaws.com"
aliases_items=""
alias_qty=1
aliases_items="\"$DOMAIN\""
for a in ${DOMAIN_ALIASES:-}; do aliases_items="$aliases_items,\"$a\""; alias_qty=$((alias_qty+1)); done

if [[ -z "$DIST_ID" ]]; then
  log "creating CloudFront distribution"
  dist_cfg="$(mktemp)"
  cat > "$dist_cfg" <<JSON
{
  "CallerReference": "tplh-$(date -u +%s)",
  "Comment": "$PROJECT",
  "Enabled": true,
  "PriceClass": "PriceClass_100",
  "DefaultRootObject": "index.html",
  "Aliases": { "Quantity": $alias_qty, "Items": [ $aliases_items ] },
  "Origins": {
    "Quantity": 2,
    "Items": [
      {
        "Id": "s3-static",
        "DomainName": "$S3_ORIGIN_DOMAIN",
        "OriginAccessControlId": "$OAC_ID",
        "S3OriginConfig": { "OriginAccessIdentity": "" }
      },
      {
        "Id": "api-origin",
        "DomainName": "$API_ORIGIN_DOMAIN",
        "CustomOriginConfig": {
          "HTTPPort": 80,
          "HTTPSPort": 443,
          "OriginProtocolPolicy": "https-only",
          "OriginSslProtocols": { "Quantity": 1, "Items": ["TLSv1.2"] }
        }
      }
    ]
  },
  "DefaultCacheBehavior": {
    "TargetOriginId": "s3-static",
    "ViewerProtocolPolicy": "redirect-to-https",
    "Compress": true,
    "AllowedMethods": { "Quantity": 3, "Items": ["GET","HEAD","OPTIONS"], "CachedMethods": { "Quantity": 2, "Items": ["GET","HEAD"] } },
    "CachePolicyId": "$CACHE_OPTIMIZED",
    "ResponseHeadersPolicyId": "$RHP_ID"
  },
  "CacheBehaviors": {
    "Quantity": 1,
    "Items": [
      {
        "PathPattern": "/api/*",
        "TargetOriginId": "api-origin",
        "ViewerProtocolPolicy": "redirect-to-https",
        "Compress": true,
        "AllowedMethods": { "Quantity": 7, "Items": ["GET","HEAD","OPTIONS","PUT","POST","PATCH","DELETE"], "CachedMethods": { "Quantity": 2, "Items": ["GET","HEAD"] } },
        "CachePolicyId": "$CACHE_DISABLED",
        "OriginRequestPolicyId": "$ORP_ALLVIEWER"
      }
    ]
  },
  "CustomErrorResponses": {
    "Quantity": 2,
    "Items": [
      { "ErrorCode": 403, "ResponsePagePath": "/index.html", "ResponseCode": "200", "ErrorCachingMinTTL": 10 },
      { "ErrorCode": 404, "ResponsePagePath": "/index.html", "ResponseCode": "200", "ErrorCachingMinTTL": 10 }
    ]
  },
  "ViewerCertificate": {
    "ACMCertificateArn": "$CERT_ARN",
    "SSLSupportMethod": "sni-only",
    "MinimumProtocolVersion": "TLSv1.2_2021"
  }
}
JSON
  DIST_ID="$(aws cloudfront create-distribution --distribution-config "file://$dist_cfg" \
    --query 'Distribution.Id' --output text)"
  rm -f "$dist_cfg"
  ok "distribution $DIST_ID created"
else
  ok "distribution $DIST_ID already exists (not modifying config)"
fi
DIST_DOMAIN="$(aws cloudfront get-distribution --id "$DIST_ID" --query 'Distribution.DomainName' --output text)"
DIST_ARN="arn:aws:cloudfront::${ACCOUNT_ID}:distribution/${DIST_ID}"
save_output CLOUDFRONT_DISTRIBUTION_ID "$DIST_ID"
save_output CLOUDFRONT_DOMAIN "$DIST_DOMAIN"

# --- bucket policy for OAC (scoped to this distribution) ---------------------
log "attaching bucket policy for CloudFront OAC"
bucket_pol="$(mktemp)"
cat > "$bucket_pol" <<JSON
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "AllowCloudFrontOAC",
    "Effect": "Allow",
    "Principal": { "Service": "cloudfront.amazonaws.com" },
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::${S3_BUCKET}/*",
    "Condition": { "StringEquals": { "AWS:SourceArn": "${DIST_ARN}" } }
  }]
}
JSON
aws s3api put-bucket-policy --bucket "$S3_BUCKET" --policy "file://$bucket_pol" >/dev/null
rm -f "$bucket_pol"
ok "bucket policy applied"

# --- optional Route 53 alias records -----------------------------------------
if [[ -n "${HOSTED_ZONE_ID:-}" ]]; then
  log "creating Route 53 alias records -> CloudFront"
  for host in "$DOMAIN" ${DOMAIN_ALIASES:-}; do
    aws route53 change-resource-record-sets --hosted-zone-id "$HOSTED_ZONE_ID" \
      --change-batch "{\"Changes\":[{\"Action\":\"UPSERT\",\"ResourceRecordSet\":{\"Name\":\"$host\",\"Type\":\"A\",\"AliasTarget\":{\"HostedZoneId\":\"Z2FDTNDATAQYW2\",\"DNSName\":\"$DIST_DOMAIN\",\"EvaluateTargetHealth\":false}}}]}" >/dev/null || true
  done
  ok "Route 53 alias records set"
fi

cat >&2 <<DONE

$(ok "CloudFront front provisioned (Tier 3)")
  Bucket       : $S3_BUCKET
  Distribution : $DIST_ID
  CF domain    : $DIST_DOMAIN
  Cert         : $CERT_ARN

Next steps:
  1. Point public DNS at CloudFront (if not using Route 53 automation):
       $DOMAIN  ->  $DIST_DOMAIN   (A/ALIAS at apex, CNAME for www)
     Apex domains need an ALIAS/ANAME (Route 53 alias, or a provider that
     flattens CNAMEs). CloudFront propagation takes ~5-15 min.
  2. Publish static + API via CI (deploy/aws/setup-github-oidc.sh), or manually:
       (cd web && npm ci && npm run build)
       aws s3 sync web/dist/ s3://$S3_BUCKET/ --delete --exclude 'api/*'
       aws cloudfront create-invalidation --distribution-id $DIST_ID --paths '/*'
  3. Set these CI secrets for the deploy workflow:
       S3_BUCKET=$S3_BUCKET
       CLOUDFRONT_DISTRIBUTION_ID=$DIST_ID
DONE
