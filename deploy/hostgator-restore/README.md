# HostGator restore files

Use these files to repair https://huntpubliclandintexas.com/ from **cPanel File Manager**. Do not upload `web/index.html` from the repo (that is the Vite **dev** page and points at `/src/main.tsx`, which Apache cannot serve).

Cursor chat **.zip attachments often fail to download**. Get the files from GitHub instead.

## Download (GitHub, not the chat zip)

Folder:

https://github.com/diagonalwalnut/TexasPublicLandHunting/tree/cursor/hostgator-restore-packages-9ae6/deploy/hostgator-restore

Direct files (click, then **Download raw file** if the browser tries to display them):

- Homepage zip: https://github.com/diagonalwalnut/TexasPublicLandHunting/raw/cursor/hostgator-restore-packages-9ae6/deploy/hostgator-restore/homepage.zip
- Homepage tar.gz: https://github.com/diagonalwalnut/TexasPublicLandHunting/raw/cursor/hostgator-restore-packages-9ae6/deploy/hostgator-restore/homepage.tar.gz
- Full site zip: https://github.com/diagonalwalnut/TexasPublicLandHunting/raw/cursor/hostgator-restore-packages-9ae6/deploy/hostgator-restore/full-site.zip
- Full site tar.gz: https://github.com/diagonalwalnut/TexasPublicLandHunting/raw/cursor/hostgator-restore-packages-9ae6/deploy/hostgator-restore/full-site.tar.gz

## Fastest repair (no archive)

Upload these four items into `public_html` (overwrite when asked):

1. `index.html` → `public_html/index.html`
2. `htaccess.txt` → `public_html/.htaccess` (rename after upload; File Manager hides names that start with a dot)
3. `assets/index-BVMFCN11.js` → `public_html/assets/index-BVMFCN11.js` (create `assets` if needed)
4. `assets/index-CiQZZOqP.css` → `public_html/assets/index-CiQZZOqP.css`

The repaired `index.html` must contain `/assets/index-BVMFCN11.js`. If it still mentions `/src/main.tsx`, the wrong file was uploaded.

Then extract `full-site.zip` into `public_html` for data JSON, icons, and the PHP API. Do **not** overwrite `public_html/api/data/*.sqlite` or `*.key` if those already exist.

## Check

After upload, https://huntpubliclandintexas.com/ should load the map. View source and confirm `assets/index-BVMFCN11.js`.
