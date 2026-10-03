#!/usr/bin/env bash
# Delete the AWS resources created by this tooling (by Project tag / known names).
# Prompts before destroying unless FORCE=1. Does not touch the GitHub repo.
#
# Usage: deploy/aws/teardown.sh          # interactive
#        FORCE=1 deploy/aws/teardown.sh  # no prompt
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/lib.sh"
load_config
preflight_aws
load_outputs

SG_NAME="$(res_name sg)"
ROLE_NAME="$(res_name ec2-role)"
PROFILE_NAME="$(res_name ec2-profile)"
GHA_ROLE_NAME="$(res_name gha-deploy)"

INSTANCE_ID="${INSTANCE_ID:-$(find_instance_id)}"

echo "About to delete (region $AWS_REGION, project $PROJECT):" >&2
echo "  instance        : ${INSTANCE_ID:-<none>}" >&2
echo "  elastic IP      : ${EIP_ALLOCATION_ID:-<lookup by tag>}" >&2
echo "  security group  : $SG_NAME" >&2
echo "  instance role   : $ROLE_NAME / $PROFILE_NAME" >&2
echo "  key pair        : $KEY_NAME" >&2
echo "  GH Actions role : $GHA_ROLE_NAME (kept unless FORCE_ALL=1)" >&2
if [[ "${FORCE:-0}" != "1" ]]; then
  read -r -p "Type 'destroy' to proceed: " ans
  [[ "$ans" == "destroy" ]] || die "aborted"
fi

# --- instance ----------------------------------------------------------------
if [[ -n "$INSTANCE_ID" ]]; then
  log "terminating instance $INSTANCE_ID"
  aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" >/dev/null || true
  aws ec2 wait instance-terminated --instance-ids "$INSTANCE_ID" || true
  ok "instance terminated"
fi

# --- elastic IP --------------------------------------------------------------
ALLOC_ID="${EIP_ALLOCATION_ID:-$(aws ec2 describe-addresses \
  --filters "Name=tag:Name,Values=$(res_name eip)" "Name=tag:Project,Values=$PROJECT" \
  --query 'Addresses[0].AllocationId' --output text 2>/dev/null | sed 's/None//')}"
if [[ -n "$ALLOC_ID" ]]; then
  log "releasing Elastic IP $ALLOC_ID"
  aws ec2 release-address --allocation-id "$ALLOC_ID" >/dev/null 2>&1 || true
  ok "Elastic IP released"
fi

# --- security group (retry: ENI detach lags instance termination) ------------
SG_ID="$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$SG_NAME" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null | sed 's/None//')"
if [[ -n "$SG_ID" ]]; then
  for attempt in 1 2 3 4 5 6; do
    if aws ec2 delete-security-group --group-id "$SG_ID" >/dev/null 2>&1; then
      ok "deleted security group $SG_ID"; break
    fi
    warn "security group busy, retry $attempt"; sleep 10
  done
fi

# --- instance profile + role -------------------------------------------------
if aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null 2>&1; then
  aws iam remove-role-from-instance-profile --instance-profile-name "$PROFILE_NAME" \
    --role-name "$ROLE_NAME" >/dev/null 2>&1 || true
  aws iam delete-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null 2>&1 || true
  ok "deleted instance profile $PROFILE_NAME"
fi
if aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  aws iam detach-role-policy --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore >/dev/null 2>&1 || true
  aws iam delete-role --role-name "$ROLE_NAME" >/dev/null 2>&1 || true
  ok "deleted role $ROLE_NAME"
fi

# --- key pair ----------------------------------------------------------------
if aws ec2 describe-key-pairs --key-names "$KEY_NAME" >/dev/null 2>&1; then
  log "deleting key pair $KEY_NAME"
  aws ec2 delete-key-pair --key-name "$KEY_NAME" >/dev/null 2>&1 || true
  rm -f "$AWS_DIR/${KEY_NAME}.pem"
  ok "deleted key pair"
fi

# --- GitHub Actions deploy role (only with FORCE_ALL) ------------------------
if [[ "${FORCE_ALL:-0}" == "1" ]] && aws iam get-role --role-name "$GHA_ROLE_NAME" >/dev/null 2>&1; then
  aws iam delete-role-policy --role-name "$GHA_ROLE_NAME" \
    --policy-name "$(res_name gha-deploy-policy)" >/dev/null 2>&1 || true
  aws iam delete-role --role-name "$GHA_ROLE_NAME" >/dev/null 2>&1 || true
  ok "deleted GitHub Actions role $GHA_ROLE_NAME"
fi

rm -f "$OUTPUTS_FILE"
ok "teardown complete"
