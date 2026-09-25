# Hosting

The site is two pieces:

- **Static files** from `cd web && npm run build`. That is `index.html`, JavaScript, CSS, and the JSON/GeoJSON under `data/`, including the Oregon beta.
- **The accounts API** in `web/public/api/`. It is PHP 8 with the SQLite extension, Argon2id password hashing, an HttpOnly session cookie, and a CSRF token. Account data is a SQLite file plus `app.key`, both under `api/data/` (or `AUTH_DATA_DIR`). The browser only calls `/api` on the same host, so the cookie and the content-security policy stay valid.

Map tiles stay on Carto and Esri. The host does not need to serve those.

## AWS

The smallest AWS setup that matches this app is a static site on S3 and CloudFront, with one small PHP server for accounts. The map and hunt data are already a Vite build. Sign-in is the part that cannot be a plain static upload.

| Piece | AWS service | Why |
| --- | --- | --- |
| Built site | S3 bucket, private | Holds `web/dist` |
| HTTPS, domain, cache | CloudFront + ACM certificate | One hostname for the site and `/api` |
| `/api/*` | One small instance (Lightsail, or EC2 `t4g.small`) running Apache or nginx with PHP-FPM | Keeps the current PHP API |
| SQLite and `app.key` | A disk on that same instance | SQLite needs one writer and a filesystem that stays put |
| DNS | Route 53, or the current registrar pointed at CloudFront | `huntpubliclandintexas.com` or a new name |
| Admin beta | `AUTH_ADMIN_EMAILS` in the PHP environment | Same rule as local and HostGator |

CloudFront sends `/api/*` to the PHP instance and everything else to S3. Requests for `/api/data/` stay forbidden, the way `web/public/.htaccess` blocks them now. The API sets the `Secure` cookie flag when it sees HTTPS.

One instance is enough. Favorites and sessions are a single SQLite file, and Argon2id is CPU-heavy at login. A second copy of the API needs a shared database. Lambda, or several containers, means replacing SQLite with RDS (Postgres or MySQL) and moving sessions off the local disk. That is a rewrite of `web/public/api/lib/store.php`, not a hosting change.

### Deploy steps

1. Build `web/dist` in GitHub Actions (or on a machine).
2. Create the S3 bucket, CloudFront distribution, and ACM certificate in `us-east-1` (CloudFront requires the certificate there).
3. Launch one PHP 8 instance with `php-sqlite3`, put the `api/` tree on it, and set `AUTH_DATA_DIR` to a directory outside the web root. Keep `app.key` and `accounts.sqlite` on that disk and back the disk up.
4. Add a CloudFront behavior so `/api/*` goes to the instance and the rest goes to S3. Copy the security headers from `web/public/.htaccess` onto CloudFront.
5. Point DNS at CloudFront.
6. On each release, sync `web/dist` to S3, invalidate CloudFront, and update the PHP files on the instance. Do not overwrite `api/data/` on deploy.

The React app does not need an AWS SDK or new environment variables if the API stays at `/api` on the same domain.

Ongoing cost for this shape is one small instance (Lightsail’s smallest plan is the usual starting point), plus S3 and CloudFront, which stay small for a hunt planner. A database service only shows up if the single SQLite file is no longer enough.

## HostGator

The current production host is HostGator at `https://huntpubliclandintexas.com/`. `python3 scripts/deploy-hostgator.py` uploads `web/dist` over explicit FTPS (AUTH TLS on port 21).

Required environment:

- `FTP_USER` — cPanel or FTP username (`texashunt` is expanded to `user@huntpubliclandintexas.com`)
- `FTP_PASSWORD`

Optional:

- `FTP_HOST` — default `192.185.41.29` (the shared IP for the domain; `ftp.mljpodcast.com` has no DNS)
- `FTP_PORT` — default `21`
- `FTP_REMOTE_DIR` — default `public_html`

Build first (`cd web && npm run build`), then run the deploy script from the repo root. Account data lives in `api/data/` on the server. Apache is configured to refuse that directory. Do not overwrite `accounts.sqlite` or `app.key` on upload. Admins are emails in `AUTH_ADMIN_EMAILS` or in `api/data/admins.txt`.
