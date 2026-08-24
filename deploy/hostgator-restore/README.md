# HostGator restore files

Use these files in **cPanel File Manager** for https://huntpubliclandintexas.com/. Do not upload repo `web/index.html` (that is the Vite **dev** page).

Cursor chat **.zip attachments often fail to download**. The repo is private: open GitHub **signed in** and use **Download raw file**.

## Beta: “Could not load drawn hunt data.”

Live `public_html/data/` does not have `drawn_hunts.json` (only the older APH files). Upload either:

1. `drawn_payload.php` → `public_html/drawn_payload.php` **and** `htaccess.txt` → `.htaccess`, then open https://huntpubliclandintexas.com/drawn_payload.php once, **or**
2. The three files in `data/` → `public_html/data/drawn_hunts.json`, `drawn_meta.json`, `drawn_hunts.geojson`

Then turn **Beta** on again. Do not overwrite `api/data/*.sqlite` or `*.key`.

## Sign-in (“accounts service on this host”)

1. `accounts.php` → `public_html/accounts.php`
2. `htaccess.txt` → `public_html/.htaccess` (rename after upload)

Then open https://huntpubliclandintexas.com/accounts.php once.

## Homepage files

Upload into `public_html` (overwrite when asked):

1. `index.html`
2. `htaccess.txt` → rename to `.htaccess`
3. `assets/` (hashed JS/CSS from the latest build, including `drawn_hunts-*.js`)
4. `accounts.php` and `drawn_payload.php`
5. `data/drawn_*.json` (and `.geojson`)

The repaired `index.html` must reference `/assets/…js`, not `/src/main.tsx`.
