# Setting up the AWS environment from scratch (Tier 4)

This guide takes you from **nothing** (no AWS account, no tools installed) to a
**live, serverless deployment** of Texas Public Land Hunting on AWS. It assumes
**zero prior AWS experience** and explains every term the first time it appears.

If you already know AWS, the condensed command sequence is in
[`README.md`](./README.md); this document is the slow, explained version.

> **What you are building (Tier 4):** the website's files are served worldwide
> from a cache (CloudFront) in front of private storage (S3). The login/accounts
> API runs as on-demand code (AWS Lambda) that only runs — and only costs money —
> when someone calls it, with a database (DynamoDB) that scales to zero. There is
> **no server to manage, patch, or keep running**.

---

## 0. Vocabulary (read once, refer back as needed)

| Term | Plain-English meaning |
| --- | --- |
| **AWS account** | Your billing + login boundary for everything you create. |
| **Root user** | The email you signed up with. All-powerful; use it rarely. |
| **IAM user / role** | A limited identity you create for day-to-day work. |
| **Access key** | A username/password *for programs* (the AWS CLI), not the web console. |
| **Region** | A physical location for your resources. We use `us-east-1` (N. Virginia). |
| **S3** | File storage ("buckets" hold "objects"/files). Holds the website files. |
| **CloudFront** | A global cache/CDN that serves your site fast and over HTTPS. |
| **ACM** | AWS Certificate Manager — issues the free HTTPS certificate. |
| **Lambda** | Runs your code on demand; you pay per request, nothing when idle. |
| **Function URL** | A private HTTPS address for a Lambda function. |
| **DynamoDB** | A managed NoSQL database; pay per use, scales to zero. |
| **SSM Parameter Store** | A safe place to keep a secret (our app's signing key). |
| **Route 53** | AWS's DNS — maps your domain name to CloudFront. |
| **CloudFormation / SAM** | "Infrastructure as code": one command creates all the AWS pieces. |

**Total cost for this app: roughly $0.50–$2/month** at low/medium traffic (see
[§12](#12-what-this-costs)). The single largest line item is the $0.50/month
Route 53 hosted zone.

---

## 1. Create and secure an AWS account

1. Go to <https://aws.amazon.com/> and choose **Create an AWS Account**.
2. Enter an email, a strong password, and an account name (e.g. `tplh-prod`).
3. Provide contact details and a **credit card** (required even on the free
   tier). You will not be charged for staying within free-tier limits.
4. Verify your phone number and choose the **Basic (free) support** plan.

Once you can sign in to the **AWS Management Console** (the web dashboard),
secure the account — this protects everything else you do:

1. **Turn on MFA for the root user.** Top-right menu → **Security credentials**
   → **Multi-factor authentication (MFA)** → **Assign MFA device**. Use an
   authenticator app (Authy, Google Authenticator, 1Password, etc.).
2. **Set a billing alert so you are never surprised.** Search **Billing and Cost
   Management** → **Budgets** → **Create budget** → *Zero-spend* or a small
   monthly budget (e.g. $5) → add your email. AWS will email you if spend crosses
   the threshold.

> From now on, **do not use the root user for daily work.** Create the limited
> identity in the next step and use that.

---

## 2. Create an identity for deploying (IAM)

You need credentials that the AWS CLI (installed in §3) can use. The simplest
path for a first deployment is an **IAM user with administrator access**. (A
tighter, least-privilege alternative is noted at the end of this section.)

1. In the console, search for **IAM** → **Users** → **Create user**.
2. Name it `tplh-deployer`. Leave "provide console access" **unchecked** (this
   identity is only for the CLI).
3. **Permissions** → **Attach policies directly** → check **AdministratorAccess**
   → **Next** → **Create user**.
4. Open the new user → **Security credentials** tab → **Create access key** →
   choose **Command Line Interface (CLI)** → acknowledge → **Create**.
5. You are shown an **Access key ID** and a **Secret access key**.
   **Copy both now** — the secret is shown only once. Treat them like a password.

> **Least-privilege alternative (optional, do later):** AdministratorAccess is
> convenient for the first run. Once everything works, you can delete this user
> and let CI deploy instead using **GitHub OIDC** (no stored keys at all) via
> [`setup-github-oidc-tier4.sh`](./setup-github-oidc-tier4.sh) — see [§11](#11-optional-automate-deploys-with-github-actions).

---

## 3. Install the tools on your computer

You need six tools. Install whichever are missing, then verify with the commands
in the last column.

| Tool | Why | Verify |
| --- | --- | --- |
| **AWS CLI v2** | Talk to AWS from the terminal | `aws --version` |
| **AWS SAM CLI** | Build + deploy the Lambda/DynamoDB stack | `sam --version` |
| **Docker** | SAM uses it to build the Lambda package | `docker info` |
| **PHP 8.1+ & Composer** | Install the API's PHP dependencies | `php -v` / `composer --version` |
| **Node.js 18+ & npm** | Build the website files | `node -v` / `npm -v` |
| **jq & git** | Scripts parse JSON; clone the repo | `jq --version` / `git --version` |

Install commands by platform:

**macOS (Homebrew):**
```bash
brew install awscli aws-sam-cli jq php composer node git
brew install --cask docker   # then launch Docker Desktop once
```

**Ubuntu/Debian Linux:**
```bash
sudo apt-get update
sudo apt-get install -y unzip jq git php-cli php-curl php-xml php-sqlite3 nodejs npm docker.io
# AWS CLI v2:
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip && sudo ./aws/install && rm -rf aws awscliv2.zip
# SAM CLI:
curl -L "https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip" -o sam.zip
unzip sam.zip -d sam-installation && sudo ./sam-installation/install && rm -rf sam.zip sam-installation
# Composer:
php -r "copy('https://getcomposer.org/installer','composer-setup.php');"
php composer-setup.php --install-dir=/usr/local/bin --filename=composer && rm composer-setup.php
sudo usermod -aG docker "$USER"   # then log out/in so Docker works without sudo
```

**Windows:** install [AWS CLI](https://aws.amazon.com/cli/),
[SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html),
[Docker Desktop](https://www.docker.com/products/docker-desktop/),
[PHP](https://windows.php.net/download/) + [Composer](https://getcomposer.org/),
[Node.js](https://nodejs.org/), [Git](https://git-scm.com/), and
[jq](https://jqlang.github.io/jq/download/). Run the project commands from **Git
Bash** or **WSL** so the `.sh` scripts work.

---

## 4. Connect the AWS CLI to your account

Run `aws configure` and paste the access key from §2:

```bash
aws configure
# AWS Access Key ID     : <paste Access key ID>
# AWS Secret Access Key : <paste Secret access key>
# Default region name   : us-east-1
# Default output format : json
```

> **Always use `us-east-1`.** CloudFront's HTTPS certificate *must* live there,
> and keeping the API in the same region avoids cross-region latency.

Confirm it works — this should print your account number and the deployer user:

```bash
aws sts get-caller-identity
```

If you see an account id and a `.../tplh-deployer` ARN, you are connected.

---

## 5. Get a domain and a Route 53 hosted zone

You need a domain (e.g. `huntpubliclandintexas.com`) and a **hosted zone** in
Route 53. The hosted zone is where DNS records live; it is the single ~$0.50/mo
charge. Setting `HOSTED_ZONE_ID` in your config lets the scripts create the
HTTPS-validation and website DNS records **for you** (otherwise you add them by
hand).

**Option A — register the domain in Route 53 (simplest, one bill):**
Console → **Route 53** → **Registered domains** → **Register domains**. This
automatically creates a hosted zone.

**Option B — you already own the domain elsewhere (e.g. GoDaddy, Namecheap):**
Console → **Route 53** → **Hosted zones** → **Create hosted zone** → enter your
domain. Route 53 shows **4 name servers (NS)**. Copy them into your current
registrar's "name servers" setting so Route 53 becomes authoritative. (DNS
changes can take up to a few hours to propagate.)

**Find your hosted zone id** (looks like `Z0123456789ABCDEFGHIJ`):
```bash
aws route53 list-hosted-zones \
  --query "HostedZones[].{Name:Name,Id:Id}" --output table
```

> No domain yet and just want to test? You can still deploy everything; you would
> reach the site at the raw CloudFront domain (e.g. `d123.cloudfront.net`) and
> skip the alias/DNS parts. A real domain is recommended for production.

---

## 6. Get the code and the Bref layer ARN

**Clone the repository** over HTTPS (the repo is public, so this needs no SSH key
or login) and move into the Tier 4 directory:
```bash
git clone https://github.com/diagonalwalnut/TexasPublicLandHunting.git
cd TexasPublicLandHunting/deploy/aws/tier4
```

> The URL must be the full `https://github.com/...` address. Do **not** put your
> email in it — a value shaped like `you@example.com:owner/repo.git` is read by
> Git as an SSH host and fails with *"could not read from the remote
> repository."* If you prefer SSH, the address is
> `git@github.com:diagonalwalnut/TexasPublicLandHunting.git`, but that first
> requires [adding an SSH key to your GitHub account](https://docs.github.com/authentication/connecting-to-github-with-ssh).

**Find the current Bref layer ARN.** Bref is the open-source project that lets
PHP run on Lambda; it publishes a ready-made "layer" you attach to the function.
Open <https://runtimes.bref.sh>, pick **region `us-east-1`** and the **arm64 FPM**
runtime, and copy the ARN. It looks like:

```
arn:aws:lambda:us-east-1:534081306603:layer:arm-php-83-fpm:<version>
```

You will paste this into `samconfig.toml` in the next step. (`534081306603` is
Bref's public AWS account; `arm-` matches the cheaper Graviton architecture this
project uses by default.)

---

## 7. Configure the project

There are **two** small config files to fill in: one for the shared static front
(created by the Tier 3 tooling) and one for the Tier 4 API. Both copy an example
to a git-ignored `config.sh`.

### 7a. Static-front config (`deploy/aws/config.sh`)

```bash
cd ..                       # into deploy/aws
cp config.example.sh config.sh
```

Edit `config.sh` and set:

- `S3_BUCKET` — a **globally unique** bucket name (bucket names are shared across
  *all* AWS customers), e.g. `tplh-site-yourname-2026`.
- `DOMAIN` and `DOMAIN_ALIASES` — your public hostnames.
- `HOSTED_ZONE_ID` — paste the id from §5 to automate DNS.
- `API_ORIGIN_DOMAIN` — **for Tier 4 this is a placeholder.** You are not running
  the EC2 server, so set it to any hostname you control (e.g. your `DOMAIN`); the
  Tier 4 step in §9 overwrites this origin with the Lambda Function URL. You can
  ignore the other EC2-related values (`INSTANCE_TYPE`, `KEY_NAME`, `REPO_SSH`,
  etc.) — Tier 4 never runs `provision.sh`.

### 7b. Tier 4 API config (`deploy/aws/tier4/config.sh`)

```bash
cd tier4
cp config.example.sh config.sh
```

Edit `config.sh` and set `DOMAIN`, `DOMAIN_ALIASES`, `ALLOWED_ORIGINS` (the
hostnames the API accepts browser logins from — normally the same as your
domain + `www`), and `ADMIN_EMAILS` (any email listed here becomes an admin on
next sign-in). Leave `S3_BUCKET` / `CLOUDFRONT_DISTRIBUTION_ID` to be filled in
from the front you create in §8 (the scripts also auto-read them from the Tier 3
outputs file).

Finally, put the Bref ARN from §6 into **`deploy/aws/tier4/samconfig.toml`** on
the `BrefFpmLayerArn=...` line, and set `AllowedOrigins=` there to your hostnames.

> **Never commit `config.sh`.** It (and `*.pem`, `.outputs.env`, `vendor/`) is
> already git-ignored so your settings and secrets stay local.

---

## 8. Create the static front (S3 + CloudFront + HTTPS)

From `deploy/aws` run the front-end provisioner. It creates the private S3
bucket, the CloudFront distribution, and the free HTTPS certificate:

```bash
cd ..            # into deploy/aws
./provision-cdn.sh
```

**About the HTTPS certificate (ACM):** AWS must verify you own the domain by
checking a DNS record.
- If you set `HOSTED_ZONE_ID`, the script adds the record and waits —
  issuance usually completes in a few minutes.
- If not, the script **prints a CNAME record**, stops, and asks you to add it at
  your DNS provider; then **re-run `./provision-cdn.sh`**.

When it finishes it prints your **CloudFront distribution id** and **CloudFront
domain** (e.g. `d1234.cloudfront.net`) and saves them to `deploy/aws/.outputs.env`.

**Upload the website files** (build locally, then copy to S3 and refresh the
cache). The `--exclude 'api/*'` keeps the PHP API out of S3 — it lives in Lambda:

```bash
cd ../..                               # repo root
(cd web && npm ci && npm run build)
source deploy/aws/.outputs.env         # loads S3_BUCKET + CLOUDFRONT_DISTRIBUTION_ID
aws s3 sync web/dist/ "s3://$S3_BUCKET/" --delete --exclude 'api/*'
aws cloudfront create-invalidation \
  --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" --paths '/*'
```

> **CloudFront takes ~5–15 minutes** to deploy a new distribution the first time.
> The site (minus the API) is now live once propagation finishes.

---

## 9. Deploy the serverless API (Lambda + DynamoDB)

All commands run from `deploy/aws/tier4`:

```bash
cd deploy/aws/tier4
```

**1) Create the app signing key (once).** This writes a random secret to SSM
Parameter Store; the Lambda reads it to sign session/CSRF tokens:
```bash
./create-app-key.sh
```

**2) Install PHP dependencies** (Bref + AWS SDK into `vendor/`):
```bash
composer install
```

**3) Build and deploy the stack.** `sam build` packages the code (using Docker);
`sam deploy` creates the DynamoDB table, the Lambda function, its Function URL,
the log group, and the IAM role:
```bash
sam build
sam deploy --guided     # first time only; prompts and saves answers. Later: just `sam deploy`
```
When prompted, accept the defaults (region `us-east-1`, `CAPABILITY_IAM`), and
confirm the change set. Note the **`ApiFunctionUrl`** output it prints at the end.

**4) (Optional) Migrate existing accounts** from a previous SQLite deployment.
Run against a **copy** of the live database so you never touch production:
```bash
AWS_REGION=us-east-1 AUTH_TABLE=tplh_accounts \
  php migrate-sqlite-to-dynamo.php /path/to/accounts.sqlite --dry-run   # preview
AWS_REGION=us-east-1 AUTH_TABLE=tplh_accounts \
  php migrate-sqlite-to-dynamo.php /path/to/accounts.sqlite             # for real
```
Existing passwords keep working — the hash format is identical across tiers.

**5) Point CloudFront's `/api/*` at the Lambda.** This swaps the placeholder
origin for the real Function URL and locks it so only CloudFront can call it:
```bash
./connect-cloudfront.sh
```

---

## 10. Point your domain at CloudFront

If you set `HOSTED_ZONE_ID`, `provision-cdn.sh` already created the DNS alias
records — **skip this step**.

Otherwise, at your DNS provider, create records pointing your domain at the
CloudFront domain from §8:
- apex (`huntpubliclandintexas.com`) → an **A / ALIAS / ANAME** record to the
  CloudFront domain (a plain CNAME is not allowed at the apex),
- `www` → a **CNAME** to the CloudFront domain.

DNS + CloudFront propagation can take 5–15 minutes (sometimes longer for a brand
new domain).

---

## 11. Verify it works

```bash
# API health (hits CloudFront -> Lambda). Expect: {"ok":true,"hasher":"argon2id"}
curl -sS https://YOUR_DOMAIN/api/health

# The Function URL must be private: hitting it directly should return 403.
# (Get the URL from the sam deploy output, or read it back from the stack:)
aws cloudformation describe-stacks --stack-name tplh-tier4-api \
  --query "Stacks[0].Outputs[?OutputKey=='ApiFunctionUrl'].OutputValue" --output text
curl -i https://<that-function-url>/api/health      # expect HTTP 403

# Confirm data is landing in DynamoDB after you sign up on the site:
aws dynamodb scan --table-name tplh_accounts --max-items 5
```

Then open `https://YOUR_DOMAIN` in a browser, create an account, sign in, add a
favorite, reload — the account and favorites should persist. Logs for debugging
are in CloudWatch under `/aws/lambda/tplh-tier4-api-api`.

---

## 12. Optional: automate deploys with GitHub Actions

So you never need local access keys again, let CI deploy on demand using GitHub
OIDC (a short-lived, keyless trust between GitHub and AWS):

```bash
cd deploy/aws/tier4
./setup-github-oidc-tier4.sh
```

It prints the **repository secrets** to add in GitHub → *Settings → Secrets and
variables → Actions*: `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`, `S3_BUCKET`,
`CLOUDFRONT_DISTRIBUTION_ID`, `BREF_FPM_LAYER_ARN`, `ALLOWED_ORIGINS`, and
optionally `ADMIN_EMAILS`. Then run the
[`deploy-aws-tier4.yml`](../../../.github/workflows/deploy-aws-tier4.yml)
workflow (manual "Run workflow" by default).

---

## 13. What this costs

| Traffic | Monthly total |
| --- | --- |
| ~10k visits | **~$0.50–1** |
| ~100k visits | **~$1–2** |
| ~1M visits | **~$5–8** |

The Route 53 hosted zone ($0.50/mo) dominates at low traffic. Lambda, DynamoDB,
S3, and CloudFront sit inside perpetual free-tier limits for this app's load, and
everything **scales to zero** when idle. See [`README.md`](./README.md#cost-us-east-1-on-demand)
for the breakdown.

---

## 14. Tearing it down

Remove the serverless API (leaves the S3 + CloudFront front intact):
```bash
cd deploy/aws/tier4
./teardown-tier4.sh                     # delete the stack + OAC
./teardown-tier4.sh --purge-key --yes   # also delete the SSM app key, no prompt
```

To also remove the static front, bucket, distribution, and certificate, use the
Tier 3 teardown (`deploy/aws/teardown.sh`). Deleting a CloudFront distribution is
slow (it must disable first); be patient.

---

## 15. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `aws sts get-caller-identity` fails | Re-run `aws configure`; check the key was copied correctly and region is `us-east-1`. |
| `provision-cdn.sh` stops at ACM validation | Add the printed CNAME at your DNS provider and re-run, or set `HOSTED_ZONE_ID` to automate. |
| `sam build` fails | Make sure **Docker is running** (`docker info`) and `composer install` succeeded. |
| `/api/health` returns the website HTML, or the dialog says "Accounts not available" | `/api/*` is still the S3 site. `curl -sSI https://YOUR_DOMAIN/api/health` shows `server: AmazonS3` and `content-type: text/html`. Pull the latest main and re-run `./connect-cloudfront.sh`. When it finishes, the same curl is `application/json` and the body is `{"ok":true,...}`. |
| `connect-cloudfront.sh` says `STACK_NAME: set STACK_NAME` | `deploy/aws/tier4/config.sh` was skipped. Copy `config.example.sh` to `config.sh` in that directory and run the script again. Do not `source` the Tier 3 config in the same shell first. |
| `sam deploy` rejects `AdminEmails=` | Delete the `AdminEmails=` line from `samconfig.toml`, or set it to a real email. An empty override is invalid. |
| Stack `CREATE_FAILED` on `AccountsTable` / KMS key does not exist | Delete the failed stack (`aws cloudformation delete-stack --stack-name tplh-tier4-api`, wait for `stack-delete-complete`) and `sam deploy` again. The template uses DynamoDB's default AWS owned key. |
| `/api/health` returns 403 via your domain | You skipped or mis-ran `connect-cloudfront.sh` (CloudFront isn't allowed to call the Function URL yet). Re-run it. |
| Function URL returns 403 when hit directly | **Expected** — it's private by design (IAM-authenticated; only CloudFront can call it). |
| Sign-in fails in the browser | Check `ALLOWED_ORIGINS` (config + `samconfig.toml`) lists your exact hostname(s); redeploy with `sam deploy`. |
| Site shows old content after deploy | Run a CloudFront invalidation: `aws cloudfront create-invalidation --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" --paths '/*'`. |
| "bucket already exists" | S3 names are global — pick a more unique `S3_BUCKET`. |

For architecture, security, and operations detail, see [`README.md`](./README.md).
