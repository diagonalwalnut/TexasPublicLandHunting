# shellcheck shell=bash
# Configuration for the Texas Public Land Hunting AWS deployment (Tier 3).
#
# Tier 3 = static site on S3 + CloudFront, PHP/SQLite API on a slim Graviton EC2
# box, built in CI. See SCALING-TIERS.md for the rationale and the other tiers.
#
# Copy this file to config.sh and edit the values. config.sh is auto-loaded by
# every script and is git-ignored. Never commit real values, keys, or account ids.

# ---- AWS target --------------------------------------------------------------
# Keep everything in us-east-1: CloudFront's ACM certificate MUST live there.
export AWS_REGION="us-east-1"
# Short name used to tag/name every resource this tooling creates.
export PROJECT="tplh"

# ---- EC2 API instance (Graviton / arm64) -------------------------------------
# API-only in Tier 3 (no build on the box), so a small burstable box is plenty.
export INSTANCE_TYPE="t4g.micro"
# CPU architecture: arm64 (Graviton, cheaper) or x86_64.
export CPU_ARCH="arm64"
# Root EBS volume size in GiB (gp3). API + OS + SQLite fit easily in 10.
export VOLUME_SIZE="10"

# ---- SSH access --------------------------------------------------------------
export KEY_NAME="tplh-admin"
# Optional: path to an existing SSH *public* key to import instead of creating one.
export SSH_PUBKEY_PATH=""
# CIDR allowed to reach port 22. Lock to your IP, e.g. 203.0.113.4/32.
# Find your IP with: curl -s https://checkip.amazonaws.com
export SSH_ALLOW_CIDR="0.0.0.0/0"

# ---- Application source (GitHub) --------------------------------------------
# Private repo: the instance clones over SSH with a read-only deploy key
# (make-deploy-key.sh). CI builds the frontend from the same repo.
export REPO_SSH="git@github.com:diagonalwalnut/TexasPublicLandHunting.git"
export REPO_BRANCH="main"

# ---- Domains -----------------------------------------------------------------
# Public site, served by CloudFront.
export DOMAIN="huntpubliclandintexas.com"
# Extra public hostnames for the CloudFront cert (space-separated).
export DOMAIN_ALIASES="www.huntpubliclandintexas.com"
# CloudFront's custom origin for /api/*. Point this hostname (A record) at the
# instance's Elastic IP; the instance gets a Let's Encrypt cert for it so the
# CloudFront->origin hop is HTTPS. Keep it distinct from DOMAIN.
export API_ORIGIN_DOMAIN="origin-api.huntpubliclandintexas.com"
# Email for Let's Encrypt (origin cert) AND the app admin allowlist.
export ADMIN_EMAIL="you@example.com"

# ---- Static hosting (S3 + CloudFront) ---------------------------------------
# Globally-unique S3 bucket that holds the built dist/ (private; OAC-only).
export S3_BUCKET="tplh-site-TexasPublicLandHunt-2026"
# ACM certificate ARN for DOMAIN (+aliases) in us-east-1. Leave blank to have
# provision-cdn.sh request and validate one (DNS-validated).
export ACM_CERT_ARN=""
# Optional Route 53 hosted zone id. If set, provision-cdn.sh creates the ACM
# validation records and the apex/www alias records automatically. Blank = you
# add DNS records manually.
export HOSTED_ZONE_ID="Z00357652RQLSX1TWD9SD"

# ---- Feature toggles ---------------------------------------------------------
# Elastic IP so the /api origin address is stable (recommended/required).
export ALLOCATE_EIP="1"
# SSM instance profile so GitHub Actions can deploy the API with no inbound SSH.
export ENABLE_SSM="1"

# ---- GitHub Actions OIDC (setup-github-oidc.sh) ------------------------------
export GITHUB_REPO="diagonalwalnut/TexasPublicLandHunting"
export GITHUB_REF="refs/heads/main"
