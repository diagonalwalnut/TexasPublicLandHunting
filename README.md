# Texas Public Land Hunting

Unofficial 2026–27 explorer for Texas Parks and Wildlife Department **Annual Public Hunting (APH)** walk-in units and dove/small-game leases.

Use the **map** to click hunt regions and units, or open the **report** for a filterable list of where and when a hunt is legal. Example: **Whitetail + rifle** lists matching regions and units with county season dates.

**This is not an official TPWD product.** Dates, methods, and boundaries change. Confirm every hunt with the [current unit PDF / Map Booklet](https://tpwd.texas.gov/huntwild/hunt/public/annual_public_hunting/) and the [Outdoor Annual](https://tpwd.texas.gov/regulations/outdoor-annual/hunting/2026-2027-hunting-season-dates) before you go.

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

## Oregon beta

Accounts with the Oregon beta get an **Oregon beta** button. It maps ODFW wildlife management units and 2026 eastern deer hunt areas, filters by animal, season, and method (any legal weapon, centerfire, archery, muzzleloader, shotgun), and lists controlled hunts, general seasons, and game-bird dates. A licenses section covers over-the-counter, agent, internet, and draw purchases, plus preference points.

An account's stored `role` is the source of truth. Emails in `AUTH_ADMIN_EMAILS` (comma-separated) or, for local PHP, `api/data/admins.txt` are promoted to admin on the next sign-in and are never demoted by that list. Admins can open every beta. From the Users screen an admin can promote another account or grant the Oregon beta to a regular account. Rebuild the dataset with `python3 scripts/oregon_build.py` after placing the 2026 regulations text or letting the script download the booklet PDF.

## License / attribution

Hunt regulations and maps remain © Texas Parks and Wildlife Department and, for the Oregon beta, © Oregon Department of Fish and Wildlife. This repository only stores derived JSON/GeoJSON for an unofficial planning aid and links back to official publications.
