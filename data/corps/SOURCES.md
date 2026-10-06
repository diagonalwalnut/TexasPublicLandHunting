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

The Fort Worth District mobile hunting maps (`usace-swf.maps.arcgis.com` and
the Whitney Experience Builder app) return 403. Those services are not used.

Whitney and Aquilla polygons are the hatched hunting areas on the 2025 scans,
georeferenced from town labels and clipped to the PAD-US project:

- Whitney: <https://www.swf-wc.usace.army.mil/whitney/maps/WH_2025_Map.pdf>
- Aquilla: <https://www.swf-wc.usace.army.mil/whitney/maps/AQ_2025_Map.pdf>

Both lakes share the Recreation.gov permit
<https://www.recreation.gov/permits/5303030>, which also links the locked
interactive map <https://arcg.is/0uS01W2>. Whitney entry points B1–B9 are the
access labels on that scan. Georgetown’s printable hunting map is
<https://www.swf-wc.usace.army.mil/georgetown/maps/NFHuntingPolicy_MapandRules.pdf>.
Other lakes keep a link to the locked web map and the district hunting guide.

The outer project land, used where no hunt scan could be traced, is the USGS
PAD-US 4.1 fee layer (`Mang_Name='USACE'`, Texas) from
<https://edits.nationalmap.gov/arcgis/rest/services/PAD-US/PAD_US_Landforms/MapServer/0>.
`scripts/corps_gis.py` matches each lake and writes `data/corps/<id>.geojson`.
`scripts/corps_places.py` then removes a named state park when OpenStreetMap
has a polygon inside the project (Lake Whitney State Park, Atlanta State Park,
and the Nails Creek and Birch Creek units at Somerville). Parks that cannot be
matched stay inside the project. Hunters still confirm compartments on the
official map.

## Access points

`data/corps/access.json` lists Corps-published parks, ramps, and access roads.
Street addresses are geocoded once with the Census one-line geocoder, then
Nominatim, and kept only when they fall on the project. Wright Patman points
are the published degree-minute coordinates in
<https://www.swf-wc.usace.army.mil/wrightpatman/pdf/WP_Hunting_GPS_Coordinates.pdf>.
Results are committed in `data/corps/access.geojson` so the site does not
geocode at runtime.
