# Defensive security assessment — Texas Public Land Hunting

**Date:** 2026-11-23  
**Scope:** Application source + local PHP accounts API (`web/public/api`). No production host probing. No exploit PoCs or attack payload corpora.  
**Verification:** `python3 scripts/test_auth.py`, `python3 scripts/test_security_defensive.py` (both passed).

## Executive summary

Search boxes and map filters are **not** an injection path into SQL or the accounts API—they only substring-match static JSON in the browser. The privilege boundary is the **PHP/DynamoDB accounts API**. Prepared statements, CSRF on authenticated mutations, Argon2id passwords, and allowlisted outbound links look solid. The highest practical risk is **admin bootstrap via email allowlist without email verification**.

## Architecture (relevant)

| Layer | Role | Injection relevance |
| --- | --- | --- |
| React filters (`FilterPanel`, `filters.ts`, In Season, UnitGrid/PublicLand) | Client-only `hay.includes(query)` | No API/SQL |
| Static `data/*.json` | Public hunt/geo data | Read-only fetch |
| `/api/*` PHP (local SQLite / AWS DynamoDB) | Accounts, favorites, corrections, admin | Primary attack surface |
| `safeExternalUrl` / `ExternalLink` | HTTPS + host allowlist | Blocks `javascript:` / open redirects |

## Findings (by severity)

### High — Admin role via unverified email allowlist

**Where:** `web/public/api/lib/store.php` (`tplh_sync_role`, `tplh_admin_emails`); mirrored in `deploy/aws/src/lib/store.php`.  
**What:** Open `/signup` creates an account. If the submitted email matches `AUTH_ADMIN_EMAILS` or `admins.txt`, the user is promoted to admin on first use of `tplh_sync_role` (including signup response). There is no email verification.  
**Impact:** Anyone who can register an allowlisted address string (or who learns/controls that mailbox) gets admin APIs: list user emails, change roles, post public corrections.  
**Evidence:** `scripts/test_auth.py` and `scripts/test_security_defensive.py` both assert signup as `rangeboss@example.com` yields `role: admin`.  
**Recommendation:** Require verified email (or invite-only admin), remove auto-promote on signup, or gate admin with a second factor / break-glass process. Prefer demotion when removed from allowlist if that is intended policy.

### Medium — SQLite under `web/public/api/data/` if static hosting misconfigured

**Where:** `web/public/api/data/` (local `accounts.sqlite` may exist); `.htaccess` denies all; Vite `stripAuthDatabase` removes DB files from `dist/`.  
**What:** Apache with `.htaccess` honored is fine. A static server that serves `public/` (or accidentally commits/publishes `accounts.sqlite`) without blocking that directory would expose password hashes and emails.  
**Local Vite/PHP:** `/api` is proxied to the PHP router, which does not serve the SQLite file as a static download.  
**Recommendation:** Keep DB outside the web root in all deploys; ensure CI fails if `*.sqlite` appears under publish artifacts; document that GitHub Pages / naive `serve public` must never host `api/data`.

### Low — `POST /signout` without CSRF

**Where:** `web/public/api/index.php` (signout before CSRF gate); client `web/src/auth/api.ts` skips CSRF for signout.  
**Impact:** Cross-site logout nuisance if a victim’s browser sends the session cookie (SameSite=Lax reduces this for many cross-site POSTs from third-party sites).  
**Recommendation:** Require CSRF on signout for consistency, or use `SameSite=Strict` if UX allows.

### Low — Empty Origin/Referer allowed

**Where:** `web/public/api/lib/http.php` `tplh_origin_allowed`; AWS twin allows empty source as same-origin/non-browser.  
**Impact:** Non-browser clients can call the API without Origin. CSRF on cookie-authenticated mutations remains the main browser defense.  
**Recommendation:** Keep CSRF mandatory (already true for post-login mutations). Optionally require Origin on cookie-authenticated browser requests.

### Low — Public `GET /corrections` + admin-stored notes

**Where:** `GET /corrections` unauthenticated; notes ≤500 chars; rendered as React text (`App.tsx` `correctionNote`).  
**Impact:** Operator notes are world-readable. Stored XSS risk is low today (no `dangerouslySetInnerHTML`).  
**Recommendation:** Keep React text rendering; avoid map HTML popups for notes; consider auth if notes become sensitive.

### Info — CSP allows `style-src 'unsafe-inline'`

**Where:** `web/index.html` CSP meta.  
**Impact:** Weakens XSS mitigation for style-based attacks if an HTML injection sink appears later. Scripts are `'self'` only.  
**Recommendation:** Prefer hashed/nonced styles when practical.

### Info — Admin `GET /admin/users` has no CSRF (GET)

**Where:** `web/public/api/index.php`.  
**Impact:** Returns emails for admins. Cross-site GET with cookies is constrained by SameSite=Lax.  
**Recommendation:** Acceptable for GET; ensure no state change on GET (already true).

## Surfaces explicitly checked and found safe

| Surface | Result |
| --- | --- |
| Map/search query → SQL/API | No path; client substring only |
| XSS sinks (`dangerouslySetInnerHTML`, `innerHTML`, `eval`) | None in `web/src` |
| SQL | PDO prepared statements; fixed `exec` DDL only |
| Command / path traversal file reads | None with user paths |
| Favorites / corrections unit IDs | Regex allowlist `^[A-Za-z0-9._-]{1,64}$` |
| Username / email / password | Strict validation + Argon2id |
| Outbound links | HTTPS + host allowlist (`web/src/urls.ts`) |
| CSRF on `/favorites`, `/username`, `/corrections` POST, admin mutations | Required; missing token → 403 |
| Non-admin → admin/corrections mutate | 403 |
| Bad Origin | 403 |
| Oversized JSON body (>8KB) | 413 |
| Malformed JSON | 400 |

## Safe verification commands

```bash
python3 scripts/test_auth.py
python3 scripts/test_security_defensive.py
```

## Hardening priorities (if you want follow-up patches)

1. Email verification or invite-only admin (addresses the High finding).  
2. Keep account DB off any publicly served path; CI guard for `*.sqlite` in artifacts.  
3. CSRF on signout.  
4. Tighten CSP styles when feasible.
