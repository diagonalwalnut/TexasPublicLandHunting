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

### Lint / test / build
- Build + typecheck: `npm run build` (from `web/`) = `tsc --noEmit && vite build`. There is no separate ESLint/Prettier config; the TypeScript check is the type/lint gate.
- Python tests are plain scripts (no pytest): `python3 scripts/test_auth.py`, `python3 scripts/test_data.py`, `python3 scripts/test_methods.py`.

### HostGator FTP (not GitHub)
- FTP login lives only on this Cloud Agent machine in `$HOME/.config/tplh/ftp.env` (`chmod 600`). Login shells source that file from `~/.bashrc`. **Never commit it, and never add `FTP_USER` / `FTP_PASSWORD` as GitHub Actions secrets.**
- Before a local deploy: `set -a && . "$HOME/.config/tplh/ftp.env" && set +a`, then `python3 scripts/deploy-hostgator.py` from the repo root (after `npm run build` in `web/`). Required vars: `FTP_USER`, `FTP_PASSWORD`, `FTP_HOST`, `FTP_PORT`.
- Explicit FTPS is AUTH TLS on port 21 (`scripts/deploy-hostgator.py`). A missing env file means deploy is skipped, not that GitHub should be filled in.
- The GitHub `Deploy to HostGator` workflow will keep skipping FTP until GitHub secrets exist; that skip is intentional.
