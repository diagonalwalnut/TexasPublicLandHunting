# HostGator restore files

Use these files in **cPanel File Manager** for https://huntpubliclandintexas.com/. Do not upload repo `web/index.html` (that is the Vite **dev** page).

Cursor chat **.zip attachments often fail to download**. The repo is private: open GitHub **signed in** and use **Download raw file**.

## Sign-in (“accounts service on this host”)

The live `public_html/api/` folder is missing `index.php` and has 0-byte PHP files from a failed FTP upload. Upload this one file next to `index.html`:

1. `accounts.php` → `public_html/accounts.php`
2. `htaccess.txt` → `public_html/.htaccess` (rename after upload)

Then open https://huntpubliclandintexas.com/accounts.php once (it restores `api/*.php` and redirects home). Click **Sign in** again.

If Sign-in still shows the accounts-service popup, also upload the new `index.html` and `assets/` from this folder (the browser script must call `/accounts.php`).

Do **not** overwrite `public_html/api/data/*.sqlite` or `*.key`.

## Homepage files

Upload into `public_html` (overwrite when asked):

1. `index.html`
2. `htaccess.txt` → rename to `.htaccess`
3. `assets/` (hashed JS/CSS from the latest build)
4. `accounts.php`

The repaired `index.html` must reference `/assets/…js`, not `/src/main.tsx`.
