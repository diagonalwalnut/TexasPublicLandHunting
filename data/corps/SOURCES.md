# USACE (Army Corps of Engineers) hunting areas — sources

This dataset covers U.S. Army Corps of Engineers (USACE) public hunting areas in
Texas. All Texas Corps lakes with public hunting are administered by the
**USACE Fort Worth District (SWF)**. The data is an unofficial compilation;
the Corps lake offices and the TPWD Outdoor Annual remain authoritative.

## Primary source

- USACE Fort Worth District **Public Hunting Guide** (2025-2026), the authoritative
  per-lake document for legal game, means and methods, permit requirements, costs,
  seasons, and contacts.
  <https://www.swf-wc.usace.army.mil/>
- TPWD **Outdoor Annual** hunting seasons (used for date windows by county):
  <https://tpwd.texas.gov/regulations/outdoor-annual/hunting/>

## Season windows

Corps lakes follow the Texas Outdoor Annual seasons for the county(ies) of each
lake unless the Corps further restricts them. Date windows in this dataset are
derived from the same county Outdoor Annual calendars used for TPWD units
(`scripts/county_seasons.py`), falling back to the regional default calendar
(`scripts/seasons.py`) where a county calendar is unavailable. Corps lottery and
quota hunts (e.g. Belton, Grapevine, Georgetown, Lewisville deer) have specific
dates set each year by the lake office — confirm with the lake before hunting.

## Per-lake sources (USACE Fort Worth District project pages)

| Area | Counties | Corps permit | Official page |
| --- | --- | --- | --- |
| Aquilla Lake | Hill | Required (Recreation.gov) | <https://www.swf-wc.usace.army.mil/aquilla/> |
| Bardwell Lake | Ellis | Not required | <https://www.swf-wc.usace.army.mil/bardwell/> |
| Belton Lake | Bell, Coryell | Required for deer | <https://www.swf-wc.usace.army.mil/belton/> |
| Benbrook Lake | Tarrant | Required | <https://www.swf-wc.usace.army.mil/benbrook/> |
| Lake Georgetown | Williamson | Required (fee) | <https://www.swf-wc.usace.army.mil/georgetown/> |
| Grapevine Lake | Denton | Required | <https://www.swf-wc.usace.army.mil/grapevine/> |
| Lake O' the Pines | Camp, Harrison, Marion, Morris, Upshur | Not required | <https://www.swf-wc.usace.army.mil/lakeopines/> |
| Lavon Lake | Collin | Required | <https://www.swf-wc.usace.army.mil/lavon/> |
| Lewisville Lake | Denton | Required | <https://www.swf-wc.usace.army.mil/lewisville/> |
| Navarro Mills Lake | Hill, Navarro | Required for deer | <https://www.swf-wc.usace.army.mil/navarro/> |
| Proctor Lake | Comanche | Required (free) | <https://www.swf-wc.usace.army.mil/proctor/> |
| Sam Rayburn Reservoir | Angelina, Jasper, Nacogdoches, San Augustine, Sabine | Not required | <https://www.swf-wc.usace.army.mil/samray/> |
| Somerville Lake | Burleson, Washington | Required (blind fee) | <https://www.swf-wc.usace.army.mil/somerville/> |
| Stillhouse Hollow Lake | Bell | Not required | <https://www.swf-wc.usace.army.mil/stillhouse/> |
| Town Bluff / B.A. Steinhagen Lake | Jasper, Tyler | Not required | <https://www.swf-wc.usace.army.mil/townbluff/> |
| Waco Lake | McLennan | Required for all | <https://www.swf-wc.usace.army.mil/waco/> |
| Whitney Lake | Bosque, Hill | Required (Recreation.gov) | <https://www.swf-wc.usace.army.mil/whitney/> |
| Wright Patman Lake | Bowie, Cass | ATV permit ($20) | <https://www.swf-wc.usace.army.mil/wrightpatman/> |

## Excluded Corps lakes

The following Corps lakes are intentionally **not** included as USACE hunting
areas:

- **Closed to hunting:** Canyon Lake, Hords Creek Lake, Joe Pool Lake.
- **Licensed to TPWD** (these appear in the TPWD Annual Public Hunting / WMA
  catalog, not as Corps-administered areas): Cooper Lake / Jim Chapman (Cooper
  WMA), Granger Lake (Granger WMA), O.C. Fisher (San Angelo SP / TPWD + ASU),
  Ray Roberts Lake WMA, Somerville WMA, and the Angelina-Neches / Dam B WMA at
  B.A. Steinhagen.

## Geometry

Hunt-unit boundary maps on the Corps mobile hunting-map viewer are currently
offline (updated security requirements), so authoritative GIS for most hunt
units is unavailable. Per the project's geometry policy (reuse GIS where it
exists, hand-digitize where reliable, otherwise fall back to a point + official
link), every Corps area is published as a point (`geometry: "point"`, tier 0)
with a link to the official lake page where the detailed hunt map and permit
application are posted. Individual areas can be upgraded to digitized or GIS
polygons later by changing the `geometry` field and adding
`data/corps/<id>.geojson`.
