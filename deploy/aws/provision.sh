#!/usr/bin/env bash
# Create the AWS infrastructure for Texas Public Land Hunting from scratch:
# key pair, security group, (optional) SSM instance role, and one EC2 instance
# bootstrapped with bootstrap.sh, plus an optional Elastic IP.
#
# Idempotent: re-running reuses resources it finds by name/tag. It does NOT
# deploy app code (the repo is private) — run make-deploy-key.sh then deploy.sh,
# or let GitHub Actions deploy.
#
# Usage:
#   cp deploy/aws/config.example.sh deploy/aws/config.sh && edit it
#   deploy/aws/provision.sh
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/lib.sh"
load_config
preflight_aws

SG_NAME="$(res_name sg)"
ROLE_NAME="$(res_name ec2-role)"
PROFILE_NAME="$(res_name ec2-profile)"
SERVER_NAME="$(res_name server)"

# --- AMI (latest Amazon Linux 2023, x86_64) ----------------------------------
log "resolving latest Amazon Linux 2023 AMI"
AMI_ID="$(aws ssm get-parameters \
  --names /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query 'Parameters[0].Value' --output text)"
[[ "$AMI_ID" == ami-* ]] || die "could not resolve AL2023 AMI (got '$AMI_ID')"
ok "AMI $AMI_ID"

# --- key pair ----------------------------------------------------------------
if aws ec2 describe-key-pairs --key-names "$KEY_NAME" >/dev/null 2>&1; then
  ok "key pair $KEY_NAME already exists"
elif [[ -n "${SSH_PUBKEY_PATH:-}" ]]; then
  [[ -f "$SSH_PUBKEY_PATH" ]] || die "SSH_PUBKEY_PATH not found: $SSH_PUBKEY_PATH"
  log "importing key pair $KEY_NAME from $SSH_PUBKEY_PATH"
  aws ec2 import-key-pair --key-name "$KEY_NAME" \
    --public-key-material "fileb://$SSH_PUBKEY_PATH" \
    --tag-specifications "$(tagspec key-pair "$KEY_NAME")" >/dev/null
  ok "imported key pair $KEY_NAME"
else
  pem="$AWS_DIR/${KEY_NAME}.pem"
  log "creating key pair $KEY_NAME -> $pem"
  aws ec2 create-key-pair --key-name "$KEY_NAME" \
    --tag-specifications "$(tagspec key-pair "$KEY_NAME")" \
    --query KeyMaterial --output text > "$pem"
  chmod 0400 "$pem"
  ok "saved private key $pem (keep it safe; git-ignored)"
fi

# --- security group ----------------------------------------------------------
VPC_ID="$(default_vpc_id)"
[[ -n "$VPC_ID" ]] || die "no default VPC in $AWS_REGION; create one or set a subnet."
SG_ID="$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=$SG_NAME" "Name=vpc-id,Values=$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null | sed 's/None//')"
if [[ -z "$SG_ID" ]]; then
  log "creating security group $SG_NAME in $VPC_ID"
  SG_ID="$(aws ec2 create-security-group --group-name "$SG_NAME" \
    --description "TPLH web server" --vpc-id "$VPC_ID" \
    --tag-specifications "$(tagspec security-group "$SG_NAME")" \
    --query GroupId --output text)"
fi
ok "security group $SG_ID"
authorize() {  # proto port cidr desc
  # An already-existing rule returns non-zero; that is fine, so swallow it.
  if aws ec2 authorize-security-group-ingress --group-id "$SG_ID" \
    --ip-permissions "IpProtocol=$1,FromPort=$2,ToPort=$2,IpRanges=[{CidrIp=$3,Description=$4}]" \
    >/dev/null 2>&1; then
    ok "allowed $4 ($3:$2)"
  fi
}
authorize tcp 80  "0.0.0.0/0"            "http"
authorize tcp 443 "0.0.0.0/0"            "https"
authorize tcp 22  "${SSH_ALLOW_CIDR}"    "ssh"

# --- SSM instance role (optional) --------------------------------------------
IAM_PROFILE_ARG=()
if [[ "${ENABLE_SSM:-0}" == "1" ]]; then
  if ! aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
    log "creating IAM role $ROLE_NAME for SSM"
    aws iam create-role --role-name "$ROLE_NAME" \
      --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
      --tags "Key=Project,Value=$PROJECT" >/dev/null
  fi
  aws iam attach-role-policy --role-name "$ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore >/dev/null 2>&1 || true
  if ! aws iam get-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null 2>&1; then
    aws iam create-instance-profile --instance-profile-name "$PROFILE_NAME" >/dev/null
    aws iam add-role-to-instance-profile --instance-profile-name "$PROFILE_NAME" \
      --role-name "$ROLE_NAME" >/dev/null
    log "waiting for instance profile to propagate"; sleep 12
  fi
  IAM_PROFILE_ARG=(--iam-instance-profile "Name=$PROFILE_NAME")
  ok "SSM instance profile $PROFILE_NAME"
fi

# --- existing instance? ------------------------------------------------------
EXISTING="$(find_instance_id)"
if [[ -n "$EXISTING" ]]; then
  warn "instance already exists: $EXISTING (skipping launch)"
  INSTANCE_ID="$EXISTING"
else
  # --- render user-data (config.env writer + bootstrap body) -----------------
  USER_DATA="$(mktemp)"; trap 'rm -f "$USER_DATA"' EXIT
  {
    echo '#!/usr/bin/env bash'
    echo 'set -euo pipefail'
    echo 'install -d -m 0755 /opt/tplh'
    echo "cat > /opt/tplh/config.env <<'TPLHCFG'"
    echo "PROJECT=${PROJECT}"
    echo "DOMAIN=${DOMAIN}"
    echo "DOMAIN_ALIASES=${DOMAIN_ALIASES:-}"
    echo "ADMIN_EMAIL=${ADMIN_EMAIL}"
    echo "REPO_SSH=${REPO_SSH}"
    echo "REPO_BRANCH=${REPO_BRANCH}"
    echo "DATA_DIR=/var/lib/tplh/data"
    echo "APP_ROOT=/var/www/tplh"
    echo "ACME_ROOT=/var/www/tplh/acme"
    echo "REPO_DIR=/opt/tplh/repo"
    echo "TPLHCFG"
    echo '# install deploy.sh for later use (so the instance can self-deploy)'
    echo "cat > /opt/tplh/deploy.sh <<'TPLHDEPLOY'"
    cat "$AWS_DIR/deploy.sh"
    echo "TPLHDEPLOY"
    echo 'chmod 0755 /opt/tplh/deploy.sh'
    echo "cat > /opt/tplh/setup-tls.sh <<'TPLHTLS'"
    cat "$AWS_DIR/setup-tls.sh"
    echo "TPLHTLS"
    echo 'chmod 0755 /opt/tplh/setup-tls.sh'
    # Append the bootstrap body (minus its shebang).
    tail -n +1 "$AWS_DIR/bootstrap.sh" | sed '1{/^#!/d;}'
  } > "$USER_DATA"

  log "launching $INSTANCE_TYPE instance ($SERVER_NAME)"
  run_launch() {
    aws ec2 run-instances \
      --image-id "$AMI_ID" \
      --instance-type "$INSTANCE_TYPE" \
      --key-name "$KEY_NAME" \
      --security-group-ids "$SG_ID" \
      "${IAM_PROFILE_ARG[@]}" \
      --metadata-options "HttpTokens=required,HttpEndpoint=enabled" \
      --block-device-mappings "DeviceName=/dev/xvda,Ebs={VolumeSize=${VOLUME_SIZE},VolumeType=gp3,DeleteOnTermination=true}" \
      --user-data "file://$USER_DATA" \
      --tag-specifications "$(tagspec instance "$SERVER_NAME")" "$(tagspec volume "$SERVER_NAME")" \
      --query 'Instances[0].InstanceId' --output text
  }
  # Retry: a freshly-created instance profile can take a moment to be usable.
  for attempt in 1 2 3 4 5; do
    if INSTANCE_ID="$(run_launch 2>/tmp/tplh_launch.err)"; then break; fi
    warn "run-instances attempt $attempt failed: $(tr -d '\n' </tmp/tplh_launch.err)"
    INSTANCE_ID=""; sleep $((attempt * 6))
  done
  [[ -n "${INSTANCE_ID:-}" ]] || die "failed to launch instance (see /tmp/tplh_launch.err)"
  ok "launched $INSTANCE_ID"
fi
save_output INSTANCE_ID "$INSTANCE_ID"
save_output SECURITY_GROUP_ID "$SG_ID"

log "waiting for instance to reach running"
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
ok "instance running"

# --- Elastic IP (optional) ---------------------------------------------------
PUBLIC_IP="$(instance_public_ip "$INSTANCE_ID")"
if [[ "${ALLOCATE_EIP:-0}" == "1" ]]; then
  EIP_NAME="$(res_name eip)"
  ALLOC_ID="$(aws ec2 describe-addresses \
    --filters "Name=tag:Name,Values=$EIP_NAME" "Name=tag:Project,Values=$PROJECT" \
    --query 'Addresses[0].AllocationId' --output text 2>/dev/null | sed 's/None//')"
  if [[ -z "$ALLOC_ID" ]]; then
    log "allocating Elastic IP"
    ALLOC_ID="$(aws ec2 allocate-address --domain vpc \
      --tag-specifications "$(tagspec elastic-ip "$EIP_NAME")" \
      --query AllocationId --output text)"
  fi
  aws ec2 associate-address --instance-id "$INSTANCE_ID" --allocation-id "$ALLOC_ID" >/dev/null
  PUBLIC_IP="$(aws ec2 describe-addresses --allocation-ids "$ALLOC_ID" \
    --query 'Addresses[0].PublicIp' --output text)"
  save_output EIP_ALLOCATION_ID "$ALLOC_ID"
  ok "Elastic IP $PUBLIC_IP associated"
fi
save_output PUBLIC_IP "$PUBLIC_IP"
save_output DOMAIN "$DOMAIN"

cat >&2 <<DONE

$(ok "Provisioning complete")
  Instance : $INSTANCE_ID
  Public IP: $PUBLIC_IP
  Outputs  : $OUTPUTS_FILE

Next steps:
  1. Point DNS:  ${DOMAIN}  A  ->  ${PUBLIC_IP}   (and www if used)
  2. Install the GitHub deploy key so the box can pull the private repo:
       deploy/aws/make-deploy-key.sh
  3. First deploy (build + publish):
       ssh -i ${AWS_DIR}/${KEY_NAME}.pem ec2-user@${PUBLIC_IP} 'sudo bash /opt/tplh/deploy.sh'
     (or, with SSM enabled, trigger the GitHub Actions "Deploy to AWS" workflow)
  4. After DNS resolves, enable HTTPS:
       ssh -i ${AWS_DIR}/${KEY_NAME}.pem ec2-user@${PUBLIC_IP} 'sudo bash /opt/tplh/setup-tls.sh'
       (copy setup-tls.sh up first, or run it via SSM)
DONE
