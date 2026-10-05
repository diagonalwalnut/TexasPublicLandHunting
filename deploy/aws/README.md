# Deploying Texas Public Land Hunting to AWS

The site is a static Vite build on a private S3 bucket behind CloudFront, and an
accounts API (PHP on Lambda, DynamoDB) that CloudFront serves at `/api/*`.

The step-by-step version is [SETUP-FROM-SCRATCH.md](./SETUP-FROM-SCRATCH.md).

## Layout

| Path | What it does |
| --- | --- |
| `provision-cdn.sh` | Private S3 bucket, CloudFront distribution, ACM certificate. |
| `template.yaml` | Lambda function URL, DynamoDB table, IAM role. |
| `samconfig.toml` | `sam deploy` defaults. Stack name stays `tplh-tier4-api` so an existing stack is updated, not replaced. |
| `Makefile` | `sam build` hook: copies `src/` and runs `composer install --no-dev`. |
| `src/` | Accounts API (Bref). |
| `create-app-key.sh` | One-time SSM SecureString used to hash session and CSRF tokens. |
| `connect-cloudfront.sh` | Point `/api/*` at the Function URL and stop CloudFront from replacing API errors with the homepage. |
| `setup-github-oidc.sh` | Keyless GitHub Actions deploy role. |
| `teardown.sh` | Delete the API stack. Leaves S3 and CloudFront in place. |
| `config.example.sh` | Copy to `config.sh` (git-ignored). |

## Deploy

From `deploy/aws`, with `config.sh` filled in and PHP plus Composer on `PATH`:

```bash
./create-app-key.sh
sudo dnf install -y php-cli php-xml php-mbstring php-sodium unzip   # CloudShell, once
sam build && sam deploy
./connect-cloudfront.sh
```

`./connect-cloudfront.sh` waits until CloudFront finishes deploying and exits only
when `https://$DOMAIN/api/health` returns JSON `{"ok":true}`.

Publish the static files separately:

```bash
(cd web && npm ci && npm run build)
aws s3 sync web/dist/ "s3://$S3_BUCKET/" --delete --exclude 'api/*'
aws cloudfront create-invalidation --distribution-id "$CLOUDFRONT_DISTRIBUTION_ID" --paths '/*'
```

GitHub Actions can do both from **Actions → Deploy to AWS → Run workflow**
([`.github/workflows/deploy-aws.yml`](../../.github/workflows/deploy-aws.yml)).
That workflow does not run on push.

## Local accounts

`npm run dev` in `web/` still uses the SQLite API in `web/public/api/`. Production
accounts are this Lambda function, not that directory.
