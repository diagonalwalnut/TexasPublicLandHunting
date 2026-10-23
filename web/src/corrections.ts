import type { MethodCorrection, MethodId, Opportunity, Unit } from "./types";

/** Same shape as data/unit_overrides.json and POST /api/corrections. */
export type UnitCorrection = MethodCorrection & { unitId: string };

const METHOD_ORDER = ["archery", "firearm", "muzzleloader", "shotgun", "any_legal"];

function ordered(methods: string[]): string[] {
  const rank = new Map(METHOD_ORDER.map((method, index) => [method, index]));
  const seen: string[] = [];
  for (const method of methods) {
    if (!seen.includes(method)) seen.push(method);
  }
  return seen.sort((a, b) => (rank.get(a) ?? 99) - (rank.get(b) ?? 99));
}

function forbidSet(override: UnitCorrection): Set<string> {
  const forbid = new Set(override.forbidMethods ?? []);
  if (forbid.has("firearm")) forbid.add("any_legal");
  return forbid;
}

/** Keep in step with rewrite_methods in scripts/overrides.py. */
export function rewriteMethods(methods: string[], species: string, override: UnitCorrection): string[] {
  const forbid = forbidSet(override);
  const allowed = override.speciesMethods?.[species];
  if (allowed !== undefined) {
    const allowedList = ordered(allowed.filter((method) => !forbid.has(method) && method !== "any_legal"));
    const explicit = methods.filter((method) => method !== "any_legal");
    if (explicit.length && !explicit.some((method) => allowedList.includes(method))) return [];
    return allowedList;
  }
  return ordered(methods.filter((method) => !forbid.has(method)));
}

export function applyCorrections(
  units: Unit[],
  opportunities: Opportunity[],
  corrections: UnitCorrection[],
): { units: Unit[]; opportunities: Opportunity[] } {
  const byId = new Map(corrections.filter((row) => row.unitId).map((row) => [row.unitId, row]));
  if (!byId.size) return { units, opportunities };

  const kept: Opportunity[] = [];
  for (const opp of opportunities) {
    const override = byId.get(opp.unitId);
    if (!override) {
      kept.push(opp);
      continue;
    }
    const methods = rewriteMethods(opp.methods, opp.species, override);
    if (!methods.length) continue;
    kept.push({ ...opp, methods: methods as MethodId[] });
  }

  const byUnit = new Map<string, Opportunity[]>();
  for (const opp of kept) {
    const list = byUnit.get(opp.unitId) ?? [];
    list.push(opp);
    byUnit.set(opp.unitId, list);
  }

  const nextUnits = units.map((unit) => {
    const override = byId.get(unit.id);
    if (!override) return unit;
    const rows = byUnit.get(unit.id) ?? [];
    const forbid = forbidSet(override);
    const speciesMethods: Partial<Record<string, MethodId[]>> = {};
    for (const [species, list] of Object.entries(override.speciesMethods ?? {})) {
      speciesMethods[species] = ordered(
        (list ?? []).filter((method) => !forbid.has(method) && method !== "any_legal"),
      ) as MethodId[];
    }
    const note = (override.note ?? "").trim();
    return {
      ...unit,
      methods: ordered(rows.flatMap((row) => row.methods)),
      species: [...new Set(rows.map((row) => row.species).filter((id) => id && id !== "fishing"))].sort(),
      correctionNote: note || undefined,
      methodCorrection: {
        speciesMethods,
        forbidMethods: ordered(override.forbidMethods ?? []) as MethodId[],
        note,
      },
    };
  });
  return { units: nextUnits, opportunities: kept };
}
