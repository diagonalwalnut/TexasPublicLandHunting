# Texas Public Land Hunting

Unofficial 2026–27 explorer for TPWD Annual Public Hunting units. See `README.md` for the product overview, data sources, and account/security design.

## Cursor Cloud specific instructions

### Services and how they fit together
- Frontend (`web/`): Vite + React + MapLibre map and filterable hunt report. This IS the product; it works standalone from committed data in `web/public/data/`.
- Accounts API (`web/public/api/`): PHP + SQLite. Powers sign-up/sign-in and saved (favorite) units. Optional — the map and report still work if it is down.
- Data pipeline (`scripts/*.py`): Python tools that regenerate the committed `data/` and `web/public/data/` artifacts. Not needed to run the app; the data is already checked in.

### Running (standard commands live in `web/package.json`)
- `npm run dev` (from `web/`) runs BOTH Vite (port 5173) and the PHP API (`127.0.0.1:8088`) via `dev-server.mjs`. Vite proxies `/api` → the PHP server.
- Gotcha: `dev-server.mjs` calls `process.exit(1)` if it cannot spawn `php`. If PHP is ever unavailable, run `npm run dev:web` (Vite only) for the map/report, or `npm run dev:api` for just the accounts API.
- The map needs network egress for third-party tile hosts (allowlisted in the CSP `connect-src`).

### PHP accounts API notes
- Requires `php-cli` with the `sqlite3`/`pdo_sqlite` extensions and `PASSWORD_ARGON2ID` (all present in this environment).
- SQLite DB + HMAC key are created on first use under `web/public/api/data/` (git-ignored). Delete that directory to reset accounts.
- API is same-origin only; requests need a matching `Origin`/`Referer`. Mutating routes require the `X-CSRF-Token` header (returned by `/api/signup`, `/api/signin`, `/api/me`) plus the session cookie.
- Production Sign-in probes `/accounts.php?action=health` first, then `/api/index.php?action=health`. `web/public/accounts.php` is a generated front controller (`python3 scripts/bundle_accounts_php.py`) that restores missing or 0-byte `api/*.php` files left by a failed HostGator FTP `STOR`. Root `.htaccess` also rewrites `/api/index.php` to `accounts.php` when that file is missing or empty. After changing PHP under `web/public/api/`, regenerate `accounts.php` before building.

### Lint / test / build
- Build + typecheck: `npm run build` (from `web/`) = `tsc --noEmit && vite build`. There is no separate ESLint/Prettier config; the TypeScript check is the type/lint gate.
- Python tests are plain scripts (no pytest): `python3 scripts/test_auth.py`, `python3 scripts/test_data.py`, `python3 scripts/test_methods.py`, `python3 scripts/test_drawn.py`, `python3 scripts/test_accounts_restore.py`, `python3 scripts/test_drawn_payload.py`.

### Accounts, roles, and beta
- The first user in an empty SQLite DB is an administrator; later sign-ups are standard users. If an older DB has users but no admin, startup migration promotes the oldest account.
- Administrators can open **Users** to grant or remove the administrator role. The API refuses to remove the last administrator.
- The **Beta** switch is in the site header top-right and is shown only to signed-in admins. The flag is stored on `users.beta_enabled` (per admin). Turning it on loads drawn-hunt JSON from `/data/drawn_*.json` (committed under `web/public/data/`; refresh with `python3 scripts/fetch_drawn.py`, which reuses `cache/drawn/`). If those files are missing on HostGator, `drawn_payload.php` restores them (regenerate with `python3 scripts/bundle_drawn_payload.py`) and the browser also falls back to a bundled copy.

### HostGator FTP (not GitHub)
- FTP login lives only on this Cloud Agent machine in `$HOME/.config/tplh/ftp.env` (`chmod 600`). Login shells source that file from `~/.bashrc`. **Never commit it, and never add `FTP_USER` / `FTP_PASSWORD` as GitHub Actions secrets.**
- `ftp.mljpodcast.com` has no DNS. `FTP_HOST` must be `192.185.41.29` (the A record for `huntpubliclandintexas.com` / `mljpodcast.com`). Port 21, explicit AUTH TLS. Upload target is `public_html` (`FTP_REMOTE_DIR`).
- Before a local deploy: `set -a && . "$HOME/.config/tplh/ftp.env" && set +a`, then `python3 scripts/deploy-hostgator.py` from the repo root (after `npm run build` in `web/`). Required vars: `FTP_USER`, `FTP_PASSWORD`, `FTP_HOST`, `FTP_PORT`.
- HostGator Pure-FTPd needs `PRET STOR <file>` before `PASV` or the data port is refused. `scripts/deploy-hostgator.py` sends PRET. If the Python uploader still hangs on data TLS, use `lftp` with `ftp:ssl-force true`, `ftp:ssl-protect-data false`, `ftp:ssl-protect-list false`, and `mirror -R web/dist /public_html`.
- Cloud Agent caveat: FTP **control** (AUTH TLS on port 21) works from this VM, but the **data** channel often never gets `150`/`226` because the VM’s egress IP is not stable (HostGator then ignores PASV and refuses active `PORT` to the RFC1918 address). Publish from a single-public-IP machine, not from this Cloud Agent, unless GitHub Actions secrets are allowed (they are not, by request).
- A failed `STOR` truncates the remote file to 0 bytes. Do not retry `index.html` from this VM unless a throwaway canary filename gets `226`. HostGator File Manager (or a laptop with a stable IP) is the restore path.
- Prebuilt restore packages live in `deploy/hostgator-restore/` (built `index.html` + hashed assets, plus zip/tar.gz). Cursor chat **.zip attachments often fail to download**; use the GitHub folder or the `.tar.gz` artifacts. Never upload repo `web/index.html` to `public_html` — that is the Vite dev page (`/src/main.tsx`) and will 404 on Apache.
- The GitHub `Deploy to HostGator` workflow will keep skipping FTP until GitHub secrets exist; that skip is intentional.
