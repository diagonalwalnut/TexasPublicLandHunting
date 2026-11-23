# Public Land Hunting (multi-state)

Unofficial hunting planner for **Texas, Oregon, New Mexico, Colorado, Louisiana, Arkansas, and Oklahoma**. Pick a state in the header.

- **Texas / Louisiana / Arkansas / Oklahoma** — public hunting areas (WMA/APH and Corps lakes), seasons, licenses, and an **In Season** page.
- **Oregon / New Mexico / Colorado** — statewide management units (WMU/GMU), draw and OTC hunts, licenses, rules, public-land/Corps toggle, and **In Season**.

**This is not an official wildlife-agency product.** Dates, methods, and boundaries change. Confirm every hunt with the agency sources linked in each state’s Licenses and Rules panes before you go.

## What’s in the data

Compiled from public TPWD sources (see [data/SOURCES.md](data/SOURCES.md)):

- APH Area/Legal Game search JSON (`aph_202627.json`) — ~176 units, species tags, E-Postcard / youth / regular-permit flags
- 2026–27 Public Hunt Area KMZ and locator GPX — unit and dove-lease polygons
- Outdoor Annual 2026–27 season dates — archery, firearm, muzzleloader, shotgun, and youth windows used when a unit follows county seasons
- Outdoor Annual **seasons by county** pages — per-county game, zones, bag limits, and dates joined onto each unit
- Public Hunting Lands Map Booklet — printed page number for each unit (linked into the PDF)
- TPWD Public Hunt Locator Map (ArcGIS) — fallback point locations

Unit Legal Game boxes can override county seasons. Structured dates here are mostly **county defaults** unless a unit PDF was parsed.

## Run locally

```bash
python3 -m pip install -r requirements.txt
python3 scripts/fetch.py --counties  # Outdoor Annual county season pages
python3 scripts/build.py          # write data/ and web/public/data/

cd web
npm install
npm run dev          # Vite + PHP accounts API (needs php-cli and php-sqlite3)
```

`python3 scripts/test_auth.py` checks that passwords are stored as Argon2id hashes.

Optional: `python3 scripts/fetch.py --pdfs` downloads unit map PDFs so `build.py` can attach Legal Game text.

## Project layout

- `scripts/` — fetch and join TPWD sources
- `data/` — compiled GeoJSON/JSON checked in for the static site
- `web/` — Vite + React + MapLibre map and filterable hunt report
- `web/public/api/` — local development accounts API (PHP + SQLite). Production accounts run on Lambda; see [HOSTING.md](HOSTING.md)
- `deploy/aws/` — S3, CloudFront, and the Lambda accounts API

Local `npm run dev` starts Vite and a PHP API on `127.0.0.1:8088` (`php-cli` and `php-sqlite3` required).

## Accounts and saved units

Hunters create an account with a **username**, **email**, and **password**, then **save units**. Sign-in accepts username or email plus password. The map and report still work if the PHP API is down.

In production the API is `https://huntpubliclandintexas.com/api/` on Lambda. Locally, `npm run dev` serves the same routes from `web/public/api/` with SQLite under `api/data/`. That directory must be writable by PHP. The database file is created on first sign-up.

There are no frontend auth secrets. Do not commit `api/data/*.sqlite` or `api/data/*.key`.

## Account security

### Username
- Unique public handle; trim + lowercase before store or compare.
- Allowlist: 3–20 characters, `^[a-z][a-z0-9_]+$` (must start with a letter).
- Reserved names blocked in the PHP API and the browser (`admin`, `tpwd`, `official`, …).
- Rendered as React text nodes (not `dangerouslySetInnerHTML`).
- Lookups use parameterized SQL. Other users cannot list accounts.

### Email
- Unique; trim + lowercase; format check; max length 254.
- Sign-in accepts email or username. Sign-up email collisions return a generic error so the form does not confirm whether an address is registered.

### Password storage
- Passwords are **never stored or logged as plain text**. They are sent only over HTTPS (`POST /api/signup` and `/api/signin`) and hashed on the server before insert.
- Hash: **Argon2id** via PHP `password_hash(PASSWORD_ARGON2ID)` (OWASP 2023 recommendation), unique salt per user, 19 MiB memory, 3 iterations, 1 thread. If a host lacks Argon2id, the API falls back to bcrypt cost 12 and **rehashes to Argon2id on the next successful login**.
- Minimum 12 characters. Maximum 128 bytes (DoS cap; Argon2id does not truncate at 72 bytes like bcrypt).
- Common passwords are rejected. Password may not equal the email, the email local-part, or the username.
- Unknown logins still run `password_verify` against a dummy Argon2id hash so timing stays close to a real miss.
- Sign-in errors are generic (`Username, email, or password is incorrect`).
- Password fields use `type="password"`, `autocomplete="username"` / `current-password` / `new-password`, and **allow paste**.
- Client-side cooldown after failed logins (sessionStorage). The API also rate-limits sign-up and sign-in by IP and by login id hash.

### Session
- Opaque 256-bit session token in an **HttpOnly, SameSite=Lax, Secure** (on HTTPS) cookie. Only a **HMAC-SHA256** of the token is stored.
- CSRF token in the JSON body; mutating routes require `X-CSRF-Token`.
- Sign-out deletes the server row and clears the cookie.

### Browser / hosting
- CSP `connect-src` is `'self'` plus the map tile hosts — no third-party auth origin.
- COOP remains `same-origin`.
- SQLite lives under `api/data/` with `.htaccess` deny rules. Session HMAC key is `api/data/app.key` (0600), generated on first use.

### Favorites
- Only when signed in; otherwise the star opens sign-in.
- Stored in SQLite so they persist across devices.
- `unit_id` must match `^[A-Za-z0-9._-]{1,64}$`.
- Unique on `(user_id, unit_id)`. Queries are scoped to the session user.
- Star control on the unit drawer and hunt-report rows. **Saved** lists favorited units; a click opens the map.

## Multi-state data builds

```bash
python3 scripts/oregon_build.py
python3 scripts/nm_build.py
python3 scripts/co_build.py
python3 scripts/la_build.py
python3 scripts/ar_build.py
python3 scripts/ok_build.py
python3 scripts/corps_multi.py --state la   # also ar, ok, nm, co, or
python3 scripts/test_states.py
python3 scripts/test_in_season.py
```

Texas remains `scripts/fetch.py` + `scripts/build.py`. Each state folder under `data/<state>/` is mirrored to `web/public/data/<state>/`.

## Accounts

An account's stored `role` is the source of truth. Emails in `AUTH_ADMIN_EMAILS` (comma-separated) or, for local PHP, `api/data/admins.txt` are promoted to admin on the next sign-in. From the Users screen an admin can promote another account or delete another account. An admin cannot delete the account they are signed in with.

## License / attribution

Hunt regulations and maps remain © the publishing wildlife agencies and USACE districts. This repository only stores derived JSON/GeoJSON for an unofficial planning aid and links back to official publications.
