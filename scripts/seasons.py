"""2026-27 Outdoor Annual default calendars used when a unit follows county seasons."""

from __future__ import annotations

# Approximate APH-region mapping onto Outdoor Annual zones.
# Always shown as county_default — hunters must confirm the unit PDF and Outdoor Annual.

DEER_SOUTH_REGIONS = {"San Antonio/Corpus Christi"}
DOVE_NORTH_REGIONS = {"Panhandle", "Dallas/Ft. Worth", "Trans-Pecos"}
DOVE_SOUTH_REGIONS = {"Houston/Beaumont", "San Antonio/Corpus Christi"}
SQUIRREL_EAST_REGIONS = {"Pineywoods", "Houston/Beaumont"}
MULE_PANHANDLE_REGIONS = {"Panhandle"}
JAVELINA_SOUTH_REGIONS = {"San Antonio/Corpus Christi", "Trans-Pecos"}
WATERFOWL_SOUTH_REGIONS = {"Houston/Beaumont", "San Antonio/Corpus Christi"}
WATERFOWL_HPMMU_REGIONS = {"Panhandle"}

SEASON_YEAR = "2026-27"
LICENSE_YEAR_START = "2026-09-01"
LICENSE_YEAR_END = "2027-08-31"


def _win(start: str, end: str) -> dict[str, str]:
    return {"start": start, "end": end}


def windows_for(species: str, method: str, region: str, access: str) -> list[dict[str, str]]:
    """Return one or more date windows for a species/method on a unit in an APH region."""
    if species in {"feral_hog", "exotic_mammals", "furbearers", "coyote", "rabbit"}:
        return [_win(LICENSE_YEAR_START, LICENSE_YEAR_END)]

    if species == "white_tailed_deer":
        if method == "archery":
            return [_win("2026-10-03", "2026-11-06")]
        if method == "muzzleloader":
            return [_win("2027-01-04", "2027-01-17")]
        if access in {"youth", "youth_adult"}:
            late = (
                _win("2027-01-18", "2027-01-31")
                if region in DEER_SOUTH_REGIONS
                else _win("2027-01-04", "2027-01-17")
            )
            return [_win("2026-10-30", "2026-11-01"), late]
        if region in DEER_SOUTH_REGIONS:
            return [_win("2026-11-07", "2027-01-17")]
        return [_win("2026-11-07", "2027-01-03")]

    if species == "mule_deer":
        if region in MULE_PANHANDLE_REGIONS:
            if method == "archery":
                return [_win("2026-10-03", "2026-11-20")]
            return [_win("2026-11-21", "2026-12-06")]
        if method == "archery":
            return [_win("2026-10-03", "2026-11-26")]
        return [_win("2026-11-27", "2026-12-13")]

    if species == "javelina":
        if region in JAVELINA_SOUTH_REGIONS:
            return [_win(LICENSE_YEAR_START, LICENSE_YEAR_END)]
        return [_win("2026-10-01", "2027-02-28")]

    if species == "turkey":
        if method == "archery":
            return [_win("2026-10-03", "2026-11-06")]
        if access in {"youth", "youth_adult"}:
            if region in DEER_SOUTH_REGIONS:
                return [
                    _win("2026-10-30", "2026-11-01"),
                    _win("2027-01-18", "2027-01-31"),
                    _win("2027-03-13", "2027-03-14"),
                    _win("2027-05-08", "2027-05-09"),
                ]
            return [
                _win("2026-10-30", "2026-11-01"),
                _win("2027-01-04", "2027-01-17"),
                _win("2027-03-27", "2027-03-28"),
                _win("2027-05-22", "2027-05-23"),
            ]
        fall = (
            _win("2026-11-07", "2027-01-17")
            if region in DEER_SOUTH_REGIONS
            else _win("2026-11-07", "2027-01-03")
        )
        spring = (
            _win("2027-03-20", "2027-05-02")
            if region in DEER_SOUTH_REGIONS
            else _win("2027-04-03", "2027-05-16")
        )
        return [fall, spring]

    if species == "squirrel":
        wins = []
        if access in {"youth", "youth_adult"}:
            wins.append(_win("2026-09-25", "2026-09-27"))
        if region in SQUIRREL_EAST_REGIONS:
            wins.extend([_win("2026-10-01", "2027-02-28"), _win("2027-05-01", "2027-05-31")])
        else:
            wins.append(_win(LICENSE_YEAR_START, LICENSE_YEAR_END))
        return wins

    if species == "dove":
        if region in DOVE_NORTH_REGIONS:
            return [_win("2026-09-01", "2026-11-08"), _win("2026-12-18", "2027-01-07")]
        if region in DOVE_SOUTH_REGIONS:
            return [_win("2026-09-01", "2026-10-25"), _win("2026-12-18", "2027-01-21")]
        return [_win("2026-09-01", "2026-10-25"), _win("2026-12-11", "2027-01-14")]

    if species == "quail":
        return [_win("2026-11-01", "2027-02-28")]

    if species == "pheasant":
        return [_win("2026-12-05", "2027-01-03")]

    if species == "chachalaca":
        return [_win("2026-11-01", "2027-02-28")]

    if species == "teal":
        return [_win("2026-09-19", "2026-09-27")]

    if species == "sandhill_crane":
        return [_win("2026-10-31", "2027-01-31")]

    if species == "other_migratory":
        return [_win("2026-09-19", "2027-01-31")]

    if species == "waterfowl":
        if region in WATERFOWL_HPMMU_REGIONS:
            return [_win("2026-10-24", "2026-10-25"), _win("2026-10-30", "2027-01-31")]
        if region in WATERFOWL_SOUTH_REGIONS:
            return [_win("2026-11-07", "2026-11-29"), _win("2026-12-12", "2027-01-31")]
        return [_win("2026-11-14", "2026-11-29"), _win("2026-12-05", "2027-01-31")]

    if species == "fishing":
        return [_win(LICENSE_YEAR_START, LICENSE_YEAR_END)]

    return [_win(LICENSE_YEAR_START, LICENSE_YEAR_END)]


def default_calendar() -> dict:
    """Compact reference calendar stored in seasons.json for the UI."""
    return {
        "seasonYear": SEASON_YEAR,
        "source": "https://tpwd.texas.gov/regulations/outdoor-annual/hunting/2026-2027-hunting-season-dates",
        "note": (
            "County and zone dates from the 2026-27 Outdoor Annual. Public hunting units "
            "follow these dates unless the unit Legal Game box says otherwise."
        ),
        "species": {
            "white_tailed_deer": {
                "archery": "Oct 3 – Nov 6, 2026 (252 of 254 counties)",
                "firearm_north": "Nov 7, 2026 – Jan 3, 2027",
                "firearm_south": "Nov 7, 2026 – Jan 17, 2027",
                "muzzleloader": "Jan 4–17, 2027 (90 of 254 counties)",
                "youth_early": "Oct 30 – Nov 1, 2026",
            },
            "mule_deer": {
                "archery_panhandle": "Oct 3 – Nov 20, 2026",
                "general_panhandle": "Nov 21 – Dec 6, 2026",
                "archery_trans_pecos": "Oct 3 – Nov 26, 2026",
                "general_trans_pecos": "Nov 27 – Dec 13, 2026",
            },
            "dove": {
                "north": "Sep 1 – Nov 8, 2026 and Dec 18, 2026 – Jan 7, 2027",
                "central": "Sep 1 – Oct 25, 2026 and Dec 11, 2026 – Jan 14, 2027",
                "south": "Sep 1 – Oct 25, 2026 and Dec 18, 2026 – Jan 21, 2027",
            },
            "quail": {"statewide": "Nov 1, 2026 – Feb 28, 2027"},
            "squirrel": {
                "east_texas": "Oct 1, 2026 – Feb 28, 2027 and May 1–31, 2027",
                "other": "Sep 1, 2026 – Aug 31, 2027",
            },
            "rabbit": {"statewide": "No closed season"},
            "feral_hog": {"statewide": "No closed season (daylight hours on most public lands)"},
            "teal": {"statewide": "Sep 19–27, 2026"},
            "waterfowl": {"note": "Duck, goose, and coot seasons vary by zone; shotgun only."},
        },
    }
