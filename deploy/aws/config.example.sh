# shellcheck shell=bash
# Configuration for the Texas Public Land Hunting AWS deployment.
#
# Copy this file to config.sh and edit the values, then:
#   source deploy/aws/config.sh
# or let each script auto-load it (they source config.sh if present).
#
# config.sh is git-ignored (see deploy/aws/.gitignore). Never commit real
# values, keys, or account IDs.

# ---- AWS target --------------------------------------------------------------
export AWS_REGION="us-east-1"
# Short name used to tag/name every resource this tooling creates.
export PROJECT="tplh"

# ---- EC2 instance ------------------------------------------------------------
# t3.small (2 vCPU / 2 GiB) comfortably builds the site and runs Apache+PHP.
# t3.micro works but may need swap for `npm run build`.
export INSTANCE_TYPE="t3.small"
# Root EBS volume size in GiB (gp3).
export VOLUME_SIZE="20"

# ---- SSH access --------------------------------------------------------------
# Name of the EC2 key pair (created or imported by provision.sh).
export KEY_NAME="tplh-admin"
# Optional: path to an existing SSH *public* key to import as the key pair.
# Leave empty to have provision.sh create a new key pair and save the .pem
# next to these scripts as ${KEY_NAME}.pem.
export SSH_PUBKEY_PATH=""
# CIDR allowed to reach port 22. Lock this to your IP, e.g. 203.0.113.4/32.
# Find your IP with: curl -s https://checkip.amazonaws.com
export SSH_ALLOW_CIDR="0.0.0.0/0"

# ---- Application source (GitHub) --------------------------------------------
# The repository is PRIVATE, so the instance clones over SSH using a read-only
# GitHub *deploy key* created by make-deploy-key.sh.
export REPO_SSH="git@github.com:diagonalwalnut/TexasPublicLandHunting.git"
export REPO_BRANCH="main"

# ---- Site / TLS --------------------------------------------------------------
# Public domain that will point at this instance (A record -> Elastic IP).
export DOMAIN="huntpubliclandintexas.com"
# Extra hostnames for the TLS certificate (space-separated), e.g. "www.${DOMAIN}".
export DOMAIN_ALIASES="www.huntpubliclandintexas.com"
# Email for Let's Encrypt expiry notices AND the app admin allowlist
# (AUTH_ADMIN_EMAILS). Use a real address you control.
export ADMIN_EMAIL="you@example.com"

# ---- Feature toggles ---------------------------------------------------------
# Allocate + associate an Elastic IP so the public address is stable across
# stop/start (recommended, required before you point DNS at the box).
export ALLOCATE_EIP="1"
# Attach an SSM instance profile so GitHub Actions can deploy with no inbound
# SSH and no long-lived SSH key (recommended).
export ENABLE_SSM="1"

# ---- GitHub Actions OIDC (optional, used by setup-github-oidc.sh) ------------
# "owner/repo" exactly as on GitHub (case-sensitive for the OIDC subject).
export GITHUB_REPO="diagonalwalnut/TexasPublicLandHunting"
# Which ref is allowed to assume the deploy role.
export GITHUB_REF="refs/heads/main"
