/** Structured hunt/opportunity eligibility by hunter residency. */
export type HuntEligibility = "any" | "resident_only" | "nonresident_only";

/** Filter value: empty string means Any (no residency filter). */
export type HunterResidency = "" | "resident" | "nonresident";

export type ResidencyRow = {
  eligibility?: HuntEligibility | string | null;
  restrictions?: string[] | string | null;
  notes?: string | null;
};

const RESIDENT_ONLY_RE = /residents?\s+only/i;
const NONRESIDENT_ONLY_RE = /non[-\s]?residents?\s+only/i;

function textBlob(row: ResidencyRow): string {
  const parts: string[] = [];
  if (typeof row.notes === "string") parts.push(row.notes);
  if (Array.isArray(row.restrictions)) parts.push(...row.restrictions);
  else if (typeof row.restrictions === "string") parts.push(row.restrictions);
  return parts.join(" ");
}

/** Resolve eligibility from structured field or restrictions/notes text. */
export function rowEligibility(row: ResidencyRow): HuntEligibility {
  const raw = (row.eligibility || "").toString().trim().toLowerCase();
  if (raw === "resident_only" || raw === "nonresident_only" || raw === "any") {
    return raw;
  }
  const blob = textBlob(row);
  if (NONRESIDENT_ONLY_RE.test(blob)) return "nonresident_only";
  if (RESIDENT_ONLY_RE.test(blob)) return "resident_only";
  return "any";
}

/** Whether a hunt/opportunity row is allowed for the selected hunter residency. */
export function rowAllowedForHunter(row: ResidencyRow, hunterResidency: HunterResidency): boolean {
  if (!hunterResidency) return true;
  const eligibility = rowEligibility(row);
  if (eligibility === "any") return true;
  if (hunterResidency === "resident") return eligibility !== "nonresident_only";
  if (hunterResidency === "nonresident") return eligibility !== "resident_only";
  return true;
}

/** True when the dataset has at least one residency-restricted row. */
export function datasetHasResidencyRestrictions(rows: ResidencyRow[]): boolean {
  return rows.some((row) => rowEligibility(row) !== "any");
}
