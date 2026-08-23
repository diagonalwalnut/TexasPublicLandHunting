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

## License / attribution

Hunt regulations and maps remain © Texas Parks and Wildlife Department. This repository only stores derived JSON/GeoJSON for an unofficial planning aid and links back to official PDFs.
