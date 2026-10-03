#!/usr/bin/env bash
# Create (or reuse) the GitHub OIDC provider and a deploy role scoped for the
# Tier 4 serverless deploy: build/deploy the SAM stack (Lambda + Function URL +
# DynamoDB), sync static to S3, and invalidate CloudFront. No long-lived keys.
#
# After running, set the printed GitHub repo secrets:
#   AWS_DEPLOY_ROLE_ARN, AWS_REGION, S3_BUCKET, CLOUDFRONT_DISTRIBUTION_ID,
#   BREF_FPM_LAYER_ARN, ALLOWED_ORIGINS, ADMIN_EMAILS (optional)
#
# Usage: deploy/aws/tier4/setup-github-oidc-tier4.sh
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/lib-tier4.sh"
load_config_t4
preflight_aws

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
PROVIDER_HOST="token.actions.githubusercontent.com"
PROVIDER_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/${PROVIDER_HOST}"
ROLE_NAME="$(res_name gha-deploy-tier4)"

: "${GITHUB_REPO:?set GITHUB_REPO (owner/repo)}"
: "${GITHUB_REF:=refs/heads/main}"
: "${S3_BUCKET:?set S3_BUCKET in config.sh}"
: "${STACK_NAME:?set STACK_NAME}" "${DDB_TABLE:?set DDB_TABLE}"
DIST_ID="$(resolve_distribution_id)"
[[ -n "$DIST_ID" ]] || die "no CloudFront distribution found (run the Tier 3 provision-cdn.sh first)"

# --- OIDC provider -----------------------------------------------------------
if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$PROVIDER_ARN" >/dev/null 2>&1; then
  ok "OIDC provider already exists"
else
  log "creating GitHub OIDC provider"
  aws iam create-open-id-connect-provider \
    --url "https://${PROVIDER_HOST}" \
    --client-id-list "sts.amazonaws.com" \
    --thumbprint-list "6938fd4d98bab03faadb97b34396831e3780aea1" >/dev/null
  ok "OIDC provider created"
fi

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
      "Sid": "StaticToS3",
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
    },
    {
      "Sid": "SamArtifacts",
      "Effect": "Allow",
      "Action": ["s3:CreateBucket", "s3:ListBucket", "s3:GetObject", "s3:PutObject", "s3:GetBucketLocation", "s3:PutBucketPolicy", "s3:GetBucketPolicy", "s3:PutEncryptionConfiguration", "s3:PutBucketVersioning"],
      "Resource": ["arn:aws:s3:::aws-sam-cli-managed-default*", "arn:aws:s3:::aws-sam-cli-managed-default*/*"]
    },
    {
      "Sid": "CloudFormation",
      "Effect": "Allow",
      "Action": ["cloudformation:*"],
      "Resource": [
        "arn:aws:cloudformation:${AWS_REGION}:${ACCOUNT_ID}:stack/${STACK_NAME}/*",
        "arn:aws:cloudformation:${AWS_REGION}:${ACCOUNT_ID}:stack/aws-sam-cli-managed-default/*"
      ]
    },
    {
      "Sid": "CloudFormationRead",
      "Effect": "Allow",
      "Action": ["cloudformation:Describe*", "cloudformation:List*", "cloudformation:Get*", "cloudformation:ValidateTemplate", "cloudformation:CreateChangeSet"],
      "Resource": "*"
    },
    {
      "Sid": "LambdaManage",
      "Effect": "Allow",
      "Action": ["lambda:*"],
      "Resource": [
        "arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${STACK_NAME}-api",
        "arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${STACK_NAME}-api:*"
      ]
    },
    {
      "Sid": "LambdaLayers",
      "Effect": "Allow",
      "Action": ["lambda:GetLayerVersion"],
      "Resource": "arn:aws:lambda:${AWS_REGION}:*:layer:*:*"
    },
    {
      "Sid": "DynamoManage",
      "Effect": "Allow",
      "Action": ["dynamodb:CreateTable", "dynamodb:DeleteTable", "dynamodb:DescribeTable", "dynamodb:DescribeContinuousBackups", "dynamodb:UpdateContinuousBackups", "dynamodb:DescribeTimeToLive", "dynamodb:UpdateTimeToLive", "dynamodb:UpdateTable", "dynamodb:TagResource", "dynamodb:ListTagsOfResource"],
      "Resource": "arn:aws:dynamodb:${AWS_REGION}:${ACCOUNT_ID}:table/${DDB_TABLE}"
    },
    {
      "Sid": "LogsManage",
      "Effect": "Allow",
      "Action": ["logs:CreateLogGroup", "logs:DeleteLogGroup", "logs:DescribeLogGroups", "logs:PutRetentionPolicy", "logs:TagResource", "logs:ListTagsForResource"],
      "Resource": "arn:aws:logs:${AWS_REGION}:${ACCOUNT_ID}:log-group:/aws/lambda/${STACK_NAME}-api*"
    },
    {
      "Sid": "ExecutionRole",
      "Effect": "Allow",
      "Action": ["iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:PassRole", "iam:TagRole", "iam:AttachRolePolicy", "iam:DetachRolePolicy", "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:GetRolePolicy", "iam:ListRolePolicies", "iam:ListAttachedRolePolicies"],
      "Resource": "arn:aws:iam::${ACCOUNT_ID}:role/${STACK_NAME}-*"
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
  --policy-name "$(res_name gha-deploy-tier4-policy)" --policy-document "$perm" >/dev/null
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
save_output GHA_DEPLOY_ROLE_ARN "$ROLE_ARN"
ok "role ready: $ROLE_ARN"

cat >&2 <<DONE

$(ok "Set these GitHub repository secrets")
  (Settings -> Secrets and variables -> Actions -> New repository secret)

    AWS_DEPLOY_ROLE_ARN        = ${ROLE_ARN}
    AWS_REGION                 = ${AWS_REGION}
    S3_BUCKET                  = ${S3_BUCKET}
    CLOUDFRONT_DISTRIBUTION_ID = ${DIST_ID}
    BREF_FPM_LAYER_ARN         = (current Bref FPM layer, https://runtimes.bref.sh)
    ALLOWED_ORIGINS            = ${ALLOWED_ORIGINS:-your.domain www.your.domain}
    ADMIN_EMAILS               = ${ADMIN_EMAILS:-}

Then run .github/workflows/deploy-aws-tier4.yml from the Actions tab (it is
manual-dispatch by default).
DONE
