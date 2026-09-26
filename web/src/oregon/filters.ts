import type { OregonFilters, OregonHunt, OregonMethod, OregonUnit } from "./types";

const METHOD_EXPAND: Record<OregonMethod, OregonMethod[]> = {
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

export function huntMatches(hunt: OregonHunt, filters: OregonFilters): boolean {
  if (filters.species.length && !filters.species.includes(hunt.species)) return false;
  if (filters.access.length && !filters.access.includes(hunt.access)) return false;
  if (filters.methods.length) {
    const allowed = new Set(filters.methods.flatMap((method) => METHOD_EXPAND[method] ?? [method]));
    if (!hunt.methods.some((method) => allowed.has(method))) return false;
  }
  if (!overlaps(hunt.start, hunt.end, filters.start, filters.end)) return false;
  const q = filters.query.trim().toLowerCase();
  if (q) {
    const hay = `${hunt.name} ${hunt.huntNumber ?? ""} ${hunt.speciesLabel} ${hunt.bagLimit} ${hunt.tag}`.toLowerCase();
    if (!hay.includes(q)) return false;
  }
  return true;
}

export function matchingUnitIds(units: OregonUnit[], hunts: OregonHunt[], filters: OregonFilters): Set<string> {
  const active = hunts.filter((hunt) => huntMatches(hunt, filters));
  const needsHunt =
    filters.species.length > 0 ||
    filters.methods.length > 0 ||
    filters.access.length > 0 ||
    Boolean(filters.start) ||
    Boolean(filters.end) ||
    Boolean(filters.query.trim());
  const ids = new Set<string>();
  if (!needsHunt) {
    for (const unit of units) {
      if (unit.kind === filters.layer) ids.add(unit.id);
    }
    return ids;
  }
  const allowed = new Set(units.filter((unit) => unit.kind === filters.layer).map((unit) => unit.id));
  for (const hunt of active) {
    for (const id of hunt.unitIds) {
      if (allowed.has(id)) ids.add(id);
    }
  }
  return ids;
}

export function huntsForUnit(unitId: string, hunts: OregonHunt[], filters: OregonFilters): OregonHunt[] {
  return hunts
    .filter((hunt) => hunt.unitIds.includes(unitId) && huntMatches(hunt, { ...filters, query: filters.query }))
    .sort((a, b) => a.start.localeCompare(b.start) || a.species.localeCompare(b.species) || a.name.localeCompare(b.name));
}

export function formatDay(iso: string | null): string {
  if (!iso) return "None";
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function formatRange(start: string, end: string): string {
  if (start === end) return formatDay(start);
  return `${formatDay(start)} – ${formatDay(end)}`;
}
