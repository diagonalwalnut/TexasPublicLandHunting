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
npm run dev
```

Optional: `python3 scripts/fetch.py --pdfs` downloads unit map PDFs so `build.py` can attach Legal Game text.

## Project layout

- `scripts/` — fetch and join TPWD sources
- `data/` — compiled GeoJSON/JSON checked in for the static site
- `web/` — Vite + React + MapLibre map and filterable hunt report
- `.github/workflows/pages.yml` — GitHub Pages build
- `.github/workflows/hostgator.yml` — optional FTP upload to HostGator

## Accounts and saved units

The static site can attach **Supabase Auth + Postgres** so hunters create an account (email/password, Google, or Microsoft) and **save units** for later. If `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` are missing, the map and report still work; the sign-in dialog explains that accounts are not configured yet.

1. Create a project at [supabase.com](https://supabase.com).
2. **Authentication → Providers**
   - **Email**: enable. Recommended: turn on **Confirm email**. Set the minimum password length to 12 if the dashboard allows it.
   - **Google**: enable and add the client ID/secret from Google Cloud (OAuth consent + Web client). Authorized redirect: `https://YOUR_PROJECT.supabase.co/auth/v1/callback`.
   - **Azure (Microsoft)**: enable and add the Azure app (Accounts in any org + personal Microsoft accounts). Redirect: `https://YOUR_PROJECT.supabase.co/auth/v1/callback`. Request the `email` scope.
3. **Authentication → URL configuration** — add redirect URLs:
   - `http://localhost:5173/**`
   - `https://huntpubliclandintexas.com/**`
   - `https://<github-user>.github.io/TexasPublicLandHunting/**`
4. **SQL editor**: paste and run `supabase/schema.sql` (profiles, favorites, RLS, `username_taken`, trigger on `auth.users`).
5. Copy `web/.env.example` to `web/.env.local` and set:
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY` (the **anon/public** key only — never the service role key)
6. For GitHub Pages and HostGator builds, add the same two values as Actions secrets named `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`. Vite inlines them at **build** time.

Email is the login identifier. Username is a public handle, not the login.

## Account security

Controls used for usernames, passwords, sessions, OAuth, and favorites:

### Username (public handle, not the login id)
- Normalized: trim + lowercase before store or compare.
- Allowlist: 3–20 characters, `^[a-z][a-z0-9_]+$` (must start with a letter).
- Unique case-insensitive unique index in Postgres.
- Reserved names blocked in the client and with a SQL check (`admin`, `tpwd`, `official`, …).
- Rendered as React text nodes (not `dangerouslySetInnerHTML`) so the handle cannot inject HTML.
- Row Level Security: a user can only `select`/`insert`/`update` their own `profiles` row. There is no public `select` on all usernames.
- Availability is checked with the `username_taken` **security definer** RPC (returns boolean), not a wide-open table read.

### Email and password
- Email is the login identifier; trim + lowercase; format check; max length 254.
- This app **never stores or logs passwords**. They are sent only over HTTPS to Supabase Auth (GoTrue), which hashes with **bcrypt** and a unique salt per user.
- Minimum 12 characters. Maximum **72 bytes** because bcrypt silently truncates after 72 bytes; the client rejects longer secrets so the hash matches what the user typed.
- Common passwords are rejected. Password may not equal the email, the email local-part, or the username.
- Sign-in errors are generic (`Email or password is incorrect`) to reduce email enumeration. Sign-up errors similarly avoid confirming whether an email is already registered.
- Password fields use `type="password"`, `autocomplete="current-password"` / `new-password`, and **allow paste**.
- Enable **email confirmation** in the Supabase dashboard (recommended). After sign-up the UI tells the user to check email when no session is returned.
- Client-side cooldown after failed logins (sessionStorage; delay grows after 3 failures, capped at 60s). Supabase also **rate-limits** Auth endpoints (sign-in, sign-up, recover) by IP — keep that enabled.
- Optional dashboard setting: raise GoTrue’s minimum password length to 12 so server policy matches the client.

### OAuth (Google and Microsoft)
- PKCE (`flowType: "pkce"`). Redirect flow (`skipBrowserRedirect: false`), not a popup, so **Cross-Origin-Opener-Policy: same-origin** can stay on (`web/public/.htaccess` and the Vite preview headers).
- `redirectTo` is the deployed origin + Vite `BASE_URL` (localhost, HostGator domain, or GitHub Pages subpath).

### Session
- `persistSession` + `autoRefreshToken` (local session only).
- Sign out calls `supabase.auth.signOut()`, which clears the local session (and refresh token on the server when the project is configured for that).

### Browser / hosting
- CSP `connect-src` allows `https://*.supabase.co` and `wss://*.supabase.co` in `web/index.html`.
- COOP remains `same-origin` because OAuth uses a top-level redirect, not `window.open`.
- The **anon key is public by design** (it ships in the static bundle). Data protection is **RLS**, not key secrecy. **Never commit the service role key.**

### Favorites
- Only when signed in; otherwise the star opens sign-in.
- Stored in Postgres (`favorites`) so they persist across devices.
- `unit_id` must match `^[A-Za-z0-9._-]{1,64}$`.
- Unique on `(user_id, unit_id)`.
- RLS: users can only read/insert/delete their own rows.
- Star control on the unit drawer and hunt-report rows. **Saved** lists favorited units; a click opens the map.

## License / attribution

Hunt regulations and maps remain © Texas Parks and Wildlife Department. This repository only stores derived JSON/GeoJSON for an unofficial planning aid and links back to official PDFs.
