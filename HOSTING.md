# Hosting

Production is one site:

- **Static files** from `cd web && npm run build` (`index.html`, JavaScript, CSS, and the JSON/GeoJSON under `data/`, including the Oregon beta) on a private S3 bucket behind CloudFront.
- **Accounts** on Lambda, backed by DynamoDB. CloudFront sends `/api/*` to that function. The browser calls `/api` on the same host, so the session cookie and the content-security policy stay valid.

Map tiles stay on Carto and Esri. The host does not serve those.

How to create the bucket, distribution, certificate, and function is [deploy/aws/SETUP-FROM-SCRATCH.md](deploy/aws/SETUP-FROM-SCRATCH.md).

`web/public/api/` is only the local development API (`npm run dev` starts it with PHP and SQLite). It is not uploaded as the production accounts service. Production deploys exclude `api/*` from the S3 sync.

Admin accounts are emails in `ADMIN_EMAILS` (Lambda environment / `samconfig.toml`) or, for local PHP, `AUTH_ADMIN_EMAILS` or `api/data/admins.txt`.
