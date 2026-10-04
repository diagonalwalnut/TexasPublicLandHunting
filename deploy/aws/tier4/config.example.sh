# shellcheck shell=bash
# Configuration for the Texas Public Land Hunting AWS deployment (Tier 4).
#
# Tier 4 = static site on S3 + CloudFront (reused from Tier 3) + a serverless,
# scale-to-zero accounts API: PHP (Bref) on Lambda behind a Lambda Function URL
# that CloudFront routes /api/* to, backed by DynamoDB. See ../SCALING-TIERS.md.
#
# Copy this file to config.sh and edit the values. config.sh is auto-loaded by
# every script here and is git-ignored. Never commit real values or account ids.

# ---- AWS target --------------------------------------------------------------
# Keep everything in us-east-1: CloudFront's ACM certificate MUST live there,
# and the Function URL/DynamoDB live alongside it to avoid cross-region latency.
export AWS_REGION="us-east-1"
# Short name used to tag/name every resource this tooling creates.
export PROJECT="tplh"

# ---- Serverless API (Lambda + DynamoDB) -------------------------------------
# CloudFormation/SAM stack name for the serverless API.
export STACK_NAME="tplh-tier4-api"
# DynamoDB table (single-table design: users / sessions / favorites / rate limits).
export DDB_TABLE="tplh_accounts"
# Fallback Lambda function name. The real name is read from the SAM stack output
# (SAM names it "<STACK_NAME>-api", e.g. tplh-tier4-api-api); this value is only
# used if that lookup fails.
export LAMBDA_FUNCTION="tplh-tier4-api-api"
# Lambda architecture: arm64 (Graviton, cheaper/faster) or x86_64. Must match the
# Bref layer you reference in template.yaml.
export LAMBDA_ARCH="arm64"
# Function memory (MB). Argon2id (libsodium) is CPU-heavy; 1024 keeps logins fast.
export LAMBDA_MEMORY="1024"
# SSM Parameter (SecureString) that holds the app HMAC key (session/CSRF hashing).
# Created once by create-app-key.sh; the Lambda reads it at runtime.
export APP_KEY_SSM_PARAM="/tplh/tier4/app_key"
export API_ORIGIN_DOMAIN="huntpubliclandintexas.com"
# ---- Static hosting (reused from Tier 3) ------------------------------------
# These are produced by the Tier 3 deploy/aws/provision-cdn.sh (.outputs.env) or
# can be set explicitly. Tier 4 reuses the SAME S3 bucket + CloudFront
# distribution; it only swaps the /api/* origin from EC2 to the Function URL.
export S3_BUCKET="tplh-site-TexasPublicLandHunt-2026"
# CloudFront distribution id (from Tier 3). Leave blank to resolve by Comment.
export CLOUDFRONT_DISTRIBUTION_ID=""

# ---- Domains -----------------------------------------------------------------
export DOMAIN="huntpubliclandintexas.com"
# Space-separated extra public hostnames.
export DOMAIN_ALIASES="www.huntpubliclandintexas.com"
# Origins the API accepts browser requests from (CSRF defense). Space/comma
# separated hostnames; viewer Origin/Referer is matched against this list.
export ALLOWED_ORIGINS="huntpubliclandintexas.com www.huntpubliclandintexas.com"
# Comma-separated admin email allowlist (users with these emails get role=admin).
export ADMIN_EMAILS="you@example.com"
export HOSTED_ZONE_ID="Z00357652RQLSX1TWD9SD"
# ---- GitHub Actions OIDC (setup-github-oidc-tier4.sh) ------------------------
export GITHUB_REPO="diagonalwalnut/TexasPublicLandHunting"
export GITHUB_REF="refs/heads/main"
