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
      const hay = `${unit.name} ${unit.unitIds.join(" ")} ${unit.counties.join(" ")} ${unit.bookletPage ?? ""}`.toLowerCase();
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

export function matchingOpportunities(
  units: Unit[],
  opportunities: Opportunity[],
  filters: Filters,
): Opportunity[] {
  const ids = matchingUnitIds(units, opportunities, filters);
  return opportunities.filter((opp) => ids.has(opp.unitId) && opportunityMatches(opp, filters));
}

export type ReportUnitRow = {
  unit: Unit;
  opportunities: Opportunity[];
};

export type RegionReport = {
  region: string;
  unitCount: number;
  rows: ReportUnitRow[];
};

export function buildHuntReport(
  units: Unit[],
  opportunities: Opportunity[],
  filters: Filters,
): RegionReport[] {
  const byId = new Map(units.map((u) => [u.id, u]));
  const grouped = new Map<string, Map<string, Opportunity[]>>();
  for (const opp of matchingOpportunities(units, opportunities, filters)) {
    const unit = byId.get(opp.unitId);
    if (!unit) continue;
    const region = unit.region || "Unknown region";
    if (!grouped.has(region)) grouped.set(region, new Map());
    const unitsMap = grouped.get(region)!;
    const list = unitsMap.get(unit.id) ?? [];
    list.push(opp);
    unitsMap.set(unit.id, list);
  }
  return [...grouped.entries()]
    .map(([region, unitsMap]) => ({
      region,
      unitCount: unitsMap.size,
      rows: [...unitsMap.entries()]
        .map(([id, opps]) => ({ unit: byId.get(id)!, opportunities: opps }))
        .sort((a, b) => a.unit.name.localeCompare(b.unit.name)),
    }))
    .sort((a, b) => a.region.localeCompare(b.region));
}

export function regionMatchCounts(
  units: Unit[],
  matchIds: Set<string>,
): { region: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const unit of units) {
    if (!matchIds.has(unit.id)) continue;
    counts.set(unit.region, (counts.get(unit.region) ?? 0) + 1);
  }
  return [...counts.entries()]
    .map(([region, count]) => ({ region, count }))
    .sort((a, b) => b.count - a.count || a.region.localeCompare(b.region));
}

export function filterHeadline(
  filters: Filters,
  speciesLabels: Record<string, string>,
): string {
  const animals = filters.species.map((id) => speciesLabels[id] ?? id);
  const methods = filters.methods.map((id) => METHOD_LABEL[id] ?? id);
  const parts = [...animals, ...methods];
  if (filters.access.length) parts.push(...filters.access.map((id) => ACCESS_LABEL[id] ?? id));
  if (filters.region) parts.push(filters.region);
  if (filters.county) parts.push(`${filters.county} County`);
  if (filters.start || filters.end) {
    parts.push(formatRange(filters.start || "2026-09-01", filters.end || "2027-08-31"));
  }
  return parts.length ? parts.join(" · ") : "All public hunt areas";
}

export function uniqueDateRanges(opps: Opportunity[]): { start: string; end: string }[] {
  const seen = new Set<string>();
  const out: { start: string; end: string }[] = [];
  for (const opp of opps) {
    const key = `${opp.start}|${opp.end}`;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ start: opp.start, end: opp.end });
  }
  return out.sort((a, b) => a.start.localeCompare(b.start));
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
  corps_permit: "Corps / USACE permit",
};

export const TYPE_LABEL: Record<string, string> = {
  wma: "Wildlife Management Area",
  state_park: "State park",
  dove_lease: "Dove / small-game lease",
  phl: "Public hunting land",
  corps_lake: "Corps of Engineers lake",
  other: "Public hunt area",
};
