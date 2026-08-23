import type { Filters, MethodId, Opportunity, Unit } from "./types";

const METHOD_EXPAND: Record<MethodId, MethodId[]> = {
  archery: ["archery", "any_legal"],
  firearm: ["firearm", "any_legal"],
  muzzleloader: ["muzzleloader", "any_legal"],
  shotgun: ["shotgun", "any_legal"],
  any_legal: ["any_legal", "archery", "firearm", "muzzleloader", "shotgun"],
};

function overlaps(start: string, end: string, filterStart: string, filterEnd: string): boolean {
  if (!filterStart && !filterEnd) return true;
  const a = filterStart || "0000-01-01";
  const b = filterEnd || "9999-12-31";
  return start <= b && end >= a;
}

export function opportunityMatches(opp: Opportunity, filters: Filters): boolean {
  if (filters.species.length && !filters.species.includes(opp.species)) return false;
  if (filters.access.length && !filters.access.includes(opp.access)) return false;
  if (filters.methods.length) {
    const allowed = new Set(filters.methods.flatMap((m) => METHOD_EXPAND[m] ?? [m]));
    if (!opp.methods.some((m) => allowed.has(m))) return false;
  }
  if (!overlaps(opp.start, opp.end, filters.start, filters.end)) return false;
  return true;
}

export function matchingUnitIds(units: Unit[], opportunities: Opportunity[], filters: Filters): Set<string> {
  const q = filters.query.trim().toLowerCase();
  const byUnit = new Map<string, Opportunity[]>();
  for (const opp of opportunities) {
    const list = byUnit.get(opp.unitId) ?? [];
    list.push(opp);
    byUnit.set(opp.unitId, list);
  }

  const ids = new Set<string>();
  for (const unit of units) {
    if (filters.region && unit.region !== filters.region) continue;
    if (filters.county && !unit.counties.includes(filters.county)) continue;
    if (q) {
      const hay = `${unit.name} ${unit.unitIds.join(" ")} ${unit.counties.join(" ")}`.toLowerCase();
      if (!hay.includes(q)) continue;
    }
    const opps = byUnit.get(unit.id) ?? [];
    const needsOppFilter =
      filters.species.length > 0 ||
      filters.methods.length > 0 ||
      filters.access.length > 0 ||
      Boolean(filters.start) ||
      Boolean(filters.end);
    if (!needsOppFilter) {
      ids.add(unit.id);
      continue;
    }
    if (opps.some((opp) => opportunityMatches(opp, filters))) ids.add(unit.id);
  }
  return ids;
}

export function unitOpportunities(
  unitId: string,
  opportunities: Opportunity[],
  filters: Filters,
): Opportunity[] {
  return opportunities
    .filter((opp) => opp.unitId === unitId)
    .filter((opp) => {
      const slim: Filters = {
        ...filters,
        region: "",
        county: "",
        query: "",
      };
      const needs =
        slim.species.length > 0 ||
        slim.methods.length > 0 ||
        slim.access.length > 0 ||
        Boolean(slim.start) ||
        Boolean(slim.end);
      return needs ? opportunityMatches(opp, slim) : true;
    })
    .sort((a, b) => a.start.localeCompare(b.start) || a.species.localeCompare(b.species));
}

export function formatRange(start: string, end: string): string {
  const fmt = (iso: string) =>
    new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  if (start === end) return fmt(start);
  return `${fmt(start)} – ${fmt(end)}`;
}

export const METHOD_LABEL: Record<string, string> = {
  archery: "Archery",
  firearm: "Firearm / rifle",
  muzzleloader: "Muzzleloader",
  shotgun: "Shotgun",
  any_legal: "Any legal means",
};

export const ACCESS_LABEL: Record<string, string> = {
  aph_walk_in: "APH walk-in",
  youth: "Youth",
  youth_adult: "Youth/adult",
  e_postcard: "E-Postcard",
  regular_permit: "Regular (daily) permit",
  drawn: "Drawn / special permit",
};

export const TYPE_LABEL: Record<string, string> = {
  wma: "Wildlife Management Area",
  state_park: "State park",
  dove_lease: "Dove / small-game lease",
  phl: "Public hunting land",
  other: "Public hunt area",
};
