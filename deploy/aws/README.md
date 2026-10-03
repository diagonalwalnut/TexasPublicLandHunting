# Deploying Texas Public Land Hunting to AWS

This directory contains a complete, automated plan for moving the site off
HostGator onto a single AWS EC2 instance, plus a GitHub Actions pipeline that
redeploys on every push to `main`.

The design intentionally mirrors the current HostGator environment (Apache +
PHP + SQLite with `.htaccess`), so the application code and its `.htaccess`
rules run **unchanged**. That makes this the lowest‑risk lift‑and‑shift.

---

## 1. Architecture

```
                         ┌──────────────────────────────────────────────┐
   DNS A record          │  EC2 instance (Amazon Linux 2023, t3.small)   │
 huntpublicland… ──────▶ │  Elastic IP (stable public address)           │
        :443 / :80       │                                               │
                         │  Apache httpd                                 │
   GitHub Actions        │   ├─ :80  → ACME challenge + HTTPS redirect    │
   (push to main)        │   └─ :443 → DocumentRoot /var/www/tplh/current │
        │                │        AllowOverride All  (honors .htaccess)  │
        │ OIDC           │          ├─ static SPA (dist/*)               │
        ▼                │          └─ /api → php-fpm → index.php         │
   IAM deploy role ───▶  │  php-fpm (PHP 8, pdo_sqlite, argon2id)        │
        │ ssm:SendCommand│   env[AUTH_DATA_DIR] = /var/lib/tplh/data      │
        ▼                │                                               │
   /opt/tplh/deploy.sh ──┤  /var/lib/tplh/data  (PERSISTENT, git-ignored)│
     git pull (deploy    │   ├─ accounts.sqlite  (users/sessions/favs)   │
     key) → npm build →  │   ├─ app.key          (session HMAC secret)   │
     atomic release swap │   └─ admins.txt       (admin allowlist)       │
                         └──────────────────────────────────────────────┘
```

Key decisions:

- **Single EC2 instance, not S3/CloudFront.** The app is not purely static — it
  has a PHP/SQLite accounts API. One instance running Apache + php-fpm serves
  both the SPA and the API, exactly like the current shared host, with nothing
  to re-architect.
- **Amazon Linux 2023** ships PHP 8 with `pdo_sqlite` and Argon2id
  (`php-sodium`), matching `password.php`.
- **Persistent data lives outside the release dir** at `/var/lib/tplh/data`, and
  php-fpm points the app there via `env[AUTH_DATA_DIR]`. Redeploys replace the
  code but never touch user accounts.
- **Atomic releases.** `deploy.sh` builds into a timestamped release dir and
  flips the `current` symlink, so a deploy is instantaneous and trivially
  reversible.
- **Private repo → read-only deploy key.** The instance clones over SSH with a
  GitHub *deploy key* (created/installed by `make-deploy-key.sh`).
- **CI uses GitHub OIDC**, so there are **no long-lived AWS keys** in GitHub and
  no inbound SSH; deploys run through SSM on an IAM role scoped to this one
  instance.

> The CARTO basemap key is compiled into the frontend source (`HuntMap.tsx`,
> `OregonMap.tsx`), so there is **no build-time secret** to configure on the
> server.

---

## 2. Cost (us-east-1, approximate)

| Item | Monthly |
| --- | --- |
| EC2 `t3.small` on-demand (730 h) | ~$15 |
| 20 GiB gp3 EBS | ~$1.60 |
| Elastic IP (while associated) | $0 |
| Data transfer (low traffic) | ~$1–3 |
| **Total** | **~$18–20** |

A 1-year `t3.small` Savings Plan/RI cuts the compute to ~$9/mo. `t3.micro`
(~$7.50/mo) also works but may need swap to run `npm run build`.

---

## 3. Prerequisites (on your workstation)

- An AWS account (active, no services required — this creates them) and the
  **AWS CLI v2** configured with admin-ish credentials: `aws configure`.
- `jq` (used by the scripts).
- `git`, `ssh`, `scp` (standard).
- Optional: the GitHub CLI `gh` (authenticated) so `make-deploy-key.sh` can
  register the deploy key for you; otherwise it prints the manual step.

Verify: `aws sts get-caller-identity` should print your account.

---

## 4. Files

| File | Runs where | Purpose |
| --- | --- | --- |
| `config.example.sh` | — | Copy to `config.sh`, edit, it is auto-sourced. |
| `lib.sh` | workstation | Shared logging/AWS helpers. |
| `provision.sh` | workstation | Create key pair, security group, SSM role, EC2 instance, Elastic IP. |
| `bootstrap.sh` | instance (user-data) | Install Apache/php-fpm/Node, lay out dirs, write vhost + pool env. |
| `make-deploy-key.sh` | workstation | Create + install the GitHub read-only deploy key. |
| `deploy.sh` | instance | `git pull` → `npm build` → atomic release → reload → health check. |
| `setup-tls.sh` | instance | Let's Encrypt cert + port-443 vhost + auto-renew. |
| `setup-github-oidc.sh` | workstation | GitHub OIDC provider + scoped IAM deploy role. |
| `teardown.sh` | workstation | Delete everything this tooling created. |
| `apache/tplh.conf` | reference | Reviewable copy of the generated vhost. |
| `../../.github/workflows/deploy-aws.yml` | GitHub | CI/CD: deploy via SSM on push to `main`. |

---

## 5. Step-by-step

### 5.0 Configure

```bash
cd deploy/aws
cp config.example.sh config.sh
# Edit config.sh: at minimum set SSH_ALLOW_CIDR (your IP/32), DOMAIN,
# DOMAIN_ALIASES, ADMIN_EMAIL. Confirm REPO_SSH/REPO_BRANCH.
```

`config.sh`, `*.pem`, and `deploy-key*` are git-ignored.

### 5.1 Provision the infrastructure

```bash
./provision.sh
```

Creates the key pair (saved as `tplh-admin.pem` unless you set
`SSH_PUBKEY_PATH`), a security group (80/443 open, 22 from your CIDR), an SSM
instance role, the EC2 instance (bootstrapped automatically), and an Elastic IP.
It prints the public IP and writes `.outputs.env`.

### 5.2 Point DNS

Create an `A` record for `DOMAIN` (and `www`) pointing at the Elastic IP shown by
`provision.sh`. You can do this at your current registrar — Route 53 is not
required. (See “Route 53” note below if you want to move DNS to AWS.)

### 5.3 Install the deploy key (private repo access)

```bash
./make-deploy-key.sh            # uses the IP from .outputs.env
```

Generates a read-only deploy key, registers the public half on the repo (via
`gh`, or prints it for manual add), and copies the private half to
`/root/.ssh/id_ed25519` on the instance.

### 5.4 First deploy

```bash
ssh -i tplh-admin.pem ec2-user@<PUBLIC_IP> 'sudo bash /opt/tplh/deploy.sh'
```

Builds the site and publishes it. The health check hits `/api/health` and must
return 200.

### 5.5 Enable HTTPS (after DNS resolves)

```bash
ssh -i tplh-admin.pem ec2-user@<PUBLIC_IP> 'sudo bash /opt/tplh/setup-tls.sh'
```

Issues a Let's Encrypt certificate, adds the port-443 vhost, and installs a
daily auto-renew hook. From then on the app's `.htaccess` upgrades HTTP→HTTPS.

### 5.6 Continuous deployment from GitHub

```bash
./setup-github-oidc.sh
```

Creates the GitHub OIDC provider and a deploy role scoped to `ssm:SendCommand`
on this instance only. Then add the printed **repository secrets**:

- `AWS_DEPLOY_ROLE_ARN`
- `AWS_REGION`
- `TPLH_INSTANCE_ID`

After that, every push to `main` runs `.github/workflows/deploy-aws.yml`, which
assumes the role and triggers `deploy.sh` through SSM (no SSH, no static keys).
You can also run it from the Actions tab (`workflow_dispatch`).

---

## 6. Operations

- **Redeploy manually:** push to `main`, run the workflow, or
  `ssh … 'sudo bash /opt/tplh/deploy.sh'`.
- **Roll back:** releases are kept under `/var/www/tplh/releases/`. Point
  `current` at a previous one and reload:
  ```bash
  sudo ln -sfn /var/www/tplh/releases/<older> /var/www/tplh/current
  sudo systemctl reload httpd
  ```
- **Logs:** `/var/log/httpd/tplh_error.log`, `tplh_ssl_error.log`,
  `/var/log/tplh-bootstrap.log`; app errors go to the Apache error log
  (`error_log('tplh-auth: …')`).
- **Back up accounts:** the whole state is three files in `/var/lib/tplh/data`.
  Snapshot safely with the SQLite backup API:
  ```bash
  sudo sqlite3 /var/lib/tplh/data/accounts.sqlite ".backup '/tmp/accounts-$(date +%F).sqlite'"
  ```
  Copy that off-box (e.g. to S3) on a schedule. `app.key` must be kept with the
  DB — sessions depend on it.
- **Admins:** `ADMIN_EMAIL` is seeded into both the php-fpm env and
  `/var/lib/tplh/data/admins.txt`. Add more one-per-line to that file (no
  redeploy needed).

---

## 7. Security notes

- Lock `SSH_ALLOW_CIDR` to your IP. With SSM enabled you can set it to your IP
  only (or remove 22 entirely and use `aws ssm start-session`).
- IMDSv2 is required on the instance (`HttpTokens=required`).
- The deploy key is **read-only**; CI holds **no AWS secrets** (OIDC) and the
  deploy IAM role can only send the deploy command to this one instance.
- `api/data` is blocked at the web layer by `.htaccess` **and** lives outside the
  docroot, so the SQLite DB and `app.key` are never web-served.
- Never commit `config.sh`, `*.pem`, or `deploy-key*` (all git-ignored).

---

## 8. Route 53 (optional)

To manage DNS in AWS instead of your registrar: create a hosted zone for the
domain, update the registrar's nameservers to the zone's NS records, then add an
`A` record for the apex and `www` pointing at the Elastic IP. The rest of the
flow is unchanged.

---

## 9. Teardown

```bash
./teardown.sh           # prompts; add FORCE=1 to skip, FORCE_ALL=1 to also drop the CI role
```

Terminates the instance, releases the Elastic IP, and deletes the security
group, instance profile/role, and key pair. The GitHub OIDC provider is left in
place (it may be shared); remove it by hand if unused.

---

## 10. Troubleshooting

- **Bootstrap didn't finish:** `sudo cat /var/log/tplh-bootstrap.log`.
- **`deploy.sh` can't clone:** the deploy key isn't on GitHub or not at
  `/root/.ssh/id_ed25519` — re-run `make-deploy-key.sh`.
- **`setup-tls.sh` fails validation:** DNS for `DOMAIN` must resolve to the
  Elastic IP first (`dig +short DOMAIN`).
- **`/api/health` not 200:** check `/var/log/httpd/tplh_error.log` and that
  `/var/lib/tplh/data` is owned by `apache` and writable.
- **CI can't reach the instance:** the instance needs the SSM agent online
  (it's preinstalled on AL2023 and enabled via the instance role) — confirm with
  `aws ssm describe-instance-information`.
