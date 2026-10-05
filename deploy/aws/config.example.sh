# shellcheck shell=bash
# Configuration for the Texas Public Land Hunting AWS deployment.
#
# Static site on S3 + CloudFront, accounts API on Lambda + DynamoDB.
# Copy this file to config.sh and edit the values. config.sh is auto-loaded by
# every script here and is git-ignored. Never commit real values or account ids.

# ---- AWS target --------------------------------------------------------------
# Keep everything in us-east-1: CloudFront's ACM certificate MUST live there,
# and the Function URL and DynamoDB live alongside it.
export AWS_REGION="us-east-1"
# Short name used to tag/name every resource this tooling creates.
export PROJECT="tplh"

# ---- Accounts API (Lambda + DynamoDB) ---------------------------------------
# CloudFormation/SAM stack name. This is the live stack name; do not rename it
# on an account that already deployed tplh-tier4-api.
export STACK_NAME="tplh-tier4-api"
# DynamoDB table (single-table design: users / sessions / favorites / rate limits).
export DDB_TABLE="tplh_accounts"
# Fallback Lambda function name. The real name is read from the SAM stack output
# (SAM names it "<STACK_NAME>-api", e.g. tplh-tier4-api-api); this value is only
# used if that lookup fails.
export LAMBDA_FUNCTION="tplh-tier4-api-api"
# Lambda architecture: arm64 (Graviton) or x86_64. Must match the Bref layer in
# samconfig.toml.
export LAMBDA_ARCH="arm64"
# Function memory (MB). Argon2id (libsodium) is CPU-heavy; 1024 keeps logins fast.
export LAMBDA_MEMORY="1024"
# SSM Parameter (SecureString) that holds the app HMAC key (session/CSRF hashing).
# Created once by create-app-key.sh; the Lambda reads it at runtime.
export APP_KEY_SSM_PARAM="/tplh/tier4/app_key"

# ---- Static hosting ----------------------------------------------------------
# Globally unique, all-lowercase bucket name.
export S3_BUCKET="tplh-site-texaspubliclandhunt-2026"
# CloudFront distribution id. Leave blank to resolve by Comment (== PROJECT).
export CLOUDFRONT_DISTRIBUTION_ID=""
# Placeholder hostname provision-cdn.sh uses for the /api origin. connect-cloudfront.sh
# replaces it with the Lambda Function URL. Any hostname you control is fine.
export API_ORIGIN_DOMAIN="huntpubliclandintexas.com"
# Route 53 hosted zone id, or empty to add DNS records yourself.
export HOSTED_ZONE_ID=""

# ---- Domains -----------------------------------------------------------------
export DOMAIN="huntpubliclandintexas.com"
# Space-separated extra public hostnames.
export DOMAIN_ALIASES="www.huntpubliclandintexas.com"
# Origins the API accepts browser requests from (CSRF defense). Space/comma
# separated hostnames; viewer Origin/Referer is matched against this list.
export ALLOWED_ORIGINS="huntpubliclandintexas.com www.huntpubliclandintexas.com"
# Comma-separated admin email allowlist (users with these emails get role=admin).
export ADMIN_EMAILS="you@example.com"

# ---- GitHub Actions OIDC (setup-github-oidc.sh) ------------------------------
export GITHUB_REPO="diagonalwalnut/TexasPublicLandHunting"
export GITHUB_REF="refs/heads/main"
