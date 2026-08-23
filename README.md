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

## Deploy to HostGator

This is a static site. Upload the **contents** of `web/dist` into `public_html` (or the document root for your addon domain). The homepage file must be `index.html` at that root, not inside a nested `dist` folder.

```bash
cd web
npm ci
npm run build
# web/dist now includes index.html, assets/, data/, and .htaccess
```

**Automatic (GitHub Actions):** in the GitHub repo, **Settings → Secrets and variables → Actions**, add:

| Secret | Example |
|---|---|
| `FTP_HOST` | `ftp.yourdomain.com` (from cPanel → FTP Accounts) |
| `FTP_USER` | cPanel or FTP username |
| `FTP_PASSWORD` | that account’s password |
| `FTP_REMOTE_DIR` | `public_html` (optional; this is the default) |
| `FTP_PORT` | `21` (optional) |

Then **Actions → Deploy to HostGator → Run workflow**. The workflow builds with Vite `base: '/'` (domain root), not the GitHub Pages subpath.

**From your machine:**

```bash
export FTP_HOST=ftp.yourdomain.com
export FTP_USER=yourcpaneluser
export FTP_PASSWORD='…'
# optional: export FTP_REMOTE_DIR=public_html
python3 scripts/deploy-hostgator.py
```

Or use FileZilla / cPanel File Manager and copy everything inside `web/dist/` into `public_html`.

`.htaccess` (copied from `web/public/.htaccess`) turns on HTTPS, JSON/GeoJSON MIME types, and a few security headers on Apache. If AutoSSL is not active yet, comment out the HTTPS rewrite block in that file.

If the site lives in a subdirectory (for example `public_html/hunt/`), rebuild with `BASE_PATH=/hunt/` so asset URLs match that path.

## License / attribution

Hunt regulations and maps remain © Texas Parks and Wildlife Department. This repository only stores derived JSON/GeoJSON for an unofficial planning aid and links back to official PDFs.
