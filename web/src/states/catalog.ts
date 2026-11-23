export type StateId = "tx" | "or" | "nm" | "co" | "la" | "ar" | "ok";

export type StateProfile = "publicLand" | "unitGrid";

export type StateInfo = {
  id: StateId;
  name: string;
  shortName: string;
  profile: StateProfile;
  timezone: string;
  dataPrefix: string;
  agencyLabel: string;
  agencyUrl: string;
  licenseBuyUrl: string;
};

export const STATES: StateInfo[] = [
  {
    id: "tx",
    name: "Texas",
    shortName: "TX",
    profile: "publicLand",
    timezone: "America/Chicago",
    dataPrefix: "data",
    agencyLabel: "TPWD",
    agencyUrl: "https://tpwd.texas.gov/huntwild/hunt/public/annual_public_hunting/",
    licenseBuyUrl: "https://tpwd.texas.gov/business/licenses/",
  },
  {
    id: "or",
    name: "Oregon",
    shortName: "OR",
    profile: "unitGrid",
    timezone: "America/Los_Angeles",
    dataPrefix: "data/oregon",
    agencyLabel: "ODFW",
    agencyUrl: "https://myodfw.com/big-game-hunting/seasons",
    licenseBuyUrl: "https://myodfw.com",
  },
  {
    id: "nm",
    name: "New Mexico",
    shortName: "NM",
    profile: "unitGrid",
    timezone: "America/Denver",
    dataPrefix: "data/nm",
    agencyLabel: "NMDGF",
    agencyUrl: "https://wildlife.dgf.nm.gov/hunting/",
    licenseBuyUrl: "https://onlinesales.wildlife.dgf.nm.gov/",
  },
  {
    id: "co",
    name: "Colorado",
    shortName: "CO",
    profile: "unitGrid",
    timezone: "America/Denver",
    dataPrefix: "data/co",
    agencyLabel: "CPW",
    agencyUrl: "https://cpw.state.co.us/activities/hunting/big-game",
    licenseBuyUrl: "https://www.cpwshop.com/",
  },
  {
    id: "la",
    name: "Louisiana",
    shortName: "LA",
    profile: "publicLand",
    timezone: "America/Chicago",
    dataPrefix: "data/la",
    agencyLabel: "LDWF",
    agencyUrl: "https://www.wlf.louisiana.gov/page/hunting",
    licenseBuyUrl: "https://louisianaoutdoors.com/",
  },
  {
    id: "ar",
    name: "Arkansas",
    shortName: "AR",
    profile: "publicLand",
    timezone: "America/Chicago",
    dataPrefix: "data/ar",
    agencyLabel: "AGFC",
    agencyUrl: "https://www.agfc.com/hunting/",
    licenseBuyUrl: "https://www.agfc.com/licenses/",
  },
  {
    id: "ok",
    name: "Oklahoma",
    shortName: "OK",
    profile: "publicLand",
    timezone: "America/Chicago",
    dataPrefix: "data/ok",
    agencyLabel: "ODWC",
    agencyUrl: "https://www.wildlifedepartment.com/hunting",
    licenseBuyUrl: "https://gooutdoorsoklahoma.com/",
  },
];

export const STATE_BY_ID: Record<StateId, StateInfo> = Object.fromEntries(
  STATES.map((state) => [state.id, state]),
) as Record<StateId, StateInfo>;

const STORAGE_KEY = "tplh.state";

export function isStateId(value: string | null | undefined): value is StateId {
  return !!value && value in STATE_BY_ID;
}

export function readStoredState(): StateId {
  if (typeof window === "undefined") return "tx";
  const fromQuery = new URLSearchParams(window.location.search).get("state");
  if (isStateId(fromQuery)) return fromQuery;
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (isStateId(stored)) return stored;
  } catch {
    /* ignore */
  }
  return "tx";
}

export function writeStoredState(id: StateId): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, id);
  } catch {
    /* ignore */
  }
  const url = new URL(window.location.href);
  url.searchParams.set("state", id);
  window.history.replaceState({}, "", url.toString());
}

/** Local calendar YYYY-MM-DD for a timezone. */
export function todayInTimezone(timeZone: string, when = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(when);
  const year = parts.find((part) => part.type === "year")?.value ?? "1970";
  const month = parts.find((part) => part.type === "month")?.value ?? "01";
  const day = parts.find((part) => part.type === "day")?.value ?? "01";
  return `${year}-${month}-${day}`;
}
