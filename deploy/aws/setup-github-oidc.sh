#!/usr/bin/env bash
# Create an IAM OIDC identity provider for GitHub Actions and a deploy role that
# GitHub can assume (no long-lived AWS keys). The role may only trigger a deploy
# via SSM on THIS project's instance.
#
# After running, set these GitHub repo secrets (printed at the end):
#   AWS_DEPLOY_ROLE_ARN, AWS_REGION, TPLH_INSTANCE_ID
#
# Usage: deploy/aws/setup-github-oidc.sh
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/lib.sh"
load_config
preflight_aws
load_outputs

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
PROVIDER_HOST="token.actions.githubusercontent.com"
PROVIDER_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/${PROVIDER_HOST}"
ROLE_NAME="$(res_name gha-deploy)"
INSTANCE_ID="${TPLH_INSTANCE_ID:-${INSTANCE_ID:-}}"
[[ -n "$INSTANCE_ID" ]] || INSTANCE_ID="$(find_instance_id)"
[[ -n "$INSTANCE_ID" ]] || die "no instance id (run provision.sh first or export INSTANCE_ID)"

: "${GITHUB_REPO:?set GITHUB_REPO (owner/repo)}"
: "${GITHUB_REF:=refs/heads/main}"
: "${S3_BUCKET:?set S3_BUCKET in config.sh}"
DIST_ID="${CLOUDFRONT_DISTRIBUTION_ID:-}"
[[ -n "$DIST_ID" ]] || DIST_ID="$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Comment=='$PROJECT'].Id | [0]" --output text 2>/dev/null | sed 's/None//')"
[[ -n "$DIST_ID" ]] || die "no CloudFront distribution found (run provision-cdn.sh first)"

# --- OIDC provider -----------------------------------------------------------
if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$PROVIDER_ARN" >/dev/null 2>&1; then
  ok "OIDC provider already exists"
else
  log "creating GitHub OIDC provider"
  # GitHub's current root CA thumbprint; IAM still requires one even though it is
  # no longer used for validation of this well-known provider.
  aws iam create-open-id-connect-provider \
    --url "https://${PROVIDER_HOST}" \
    --client-id-list "sts.amazonaws.com" \
    --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1" >/dev/null
  ok "OIDC provider created"
fi

# --- trust + permission policies ---------------------------------------------
trust="$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "${PROVIDER_ARN}" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": { "${PROVIDER_HOST}:aud": "sts.amazonaws.com" },
      "StringLike": { "${PROVIDER_HOST}:sub": "repo:${GITHUB_REPO}:ref:${GITHUB_REF}" }
    }
  }]
}
JSON
)"

perm="$(cat <<JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SendDeployCommand",
      "Effect": "Allow",
      "Action": "ssm:SendCommand",
      "Resource": [
        "arn:aws:ec2:${AWS_REGION}:${ACCOUNT_ID}:instance/${INSTANCE_ID}",
        "arn:aws:ssm:${AWS_REGION}::document/AWS-RunShellScript"
      ]
    },
    {
      "Sid": "ReadCommandResults",
      "Effect": "Allow",
      "Action": ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations", "ssm:ListCommands"],
      "Resource": "*"
    },
    {
      "Sid": "DescribeInstances",
      "Effect": "Allow",
      "Action": "ec2:DescribeInstances",
      "Resource": "*"
    },
    {
      "Sid": "SyncStaticToS3",
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": "arn:aws:s3:::${S3_BUCKET}"
    },
    {
      "Sid": "WriteStaticObjects",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::${S3_BUCKET}/*"
    },
    {
      "Sid": "InvalidateCloudFront",
      "Effect": "Allow",
      "Action": ["cloudfront:CreateInvalidation", "cloudfront:GetInvalidation"],
      "Resource": "arn:aws:cloudfront::${ACCOUNT_ID}:distribution/${DIST_ID}"
    }
  ]
}
JSON
)"

if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  log "updating trust policy on $ROLE_NAME"
  aws iam update-assume-role-policy --role-name "$ROLE_NAME" --policy-document "$trust" >/dev/null
else
  log "creating role $ROLE_NAME"
  aws iam create-role --role-name "$ROLE_NAME" \
    --assume-role-policy-document "$trust" \
    --tags "Key=Project,Value=$PROJECT" >/dev/null
fi
aws iam put-role-policy --role-name "$ROLE_NAME" \
  --policy-name "$(res_name gha-deploy-policy)" --policy-document "$perm" >/dev/null
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
save_output GHA_DEPLOY_ROLE_ARN "$ROLE_ARN"
ok "role ready: $ROLE_ARN"

cat >&2 <<DONE

$(ok "Set these GitHub repository secrets")
  (Settings -> Secrets and variables -> Actions -> New repository secret)

    AWS_DEPLOY_ROLE_ARN        = ${ROLE_ARN}
    AWS_REGION                 = ${AWS_REGION}
    TPLH_INSTANCE_ID           = ${INSTANCE_ID}
    S3_BUCKET                  = ${S3_BUCKET}
    CLOUDFRONT_DISTRIBUTION_ID = ${DIST_ID}

Then pushes to '${GITHUB_REF##*/}' will deploy via .github/workflows/deploy-aws.yml
(static -> S3 + CloudFront invalidation; API -> SSM). Or run it from the Actions tab.
DONE
