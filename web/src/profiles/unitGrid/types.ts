export type GridMethod = "any_legal" | "firearm" | "archery" | "muzzleloader" | "shotgun";

export type GridAccess =
  | "general_otc"
  | "controlled_draw"
  | "youth_draw"
  | "youth"
  | "premium"
  | "additional"
  | "no_tag"
  | "validation"
  | "lottery"
  | "corps_permit"
  | "wma_permit";

export type GridUnit = {
  id: string;
  kind: string;
  code: string;
  name: string;
  region: string;
  acres: number | null;
  herdRange?: string;
  lon?: number | null;
  lat?: number | null;
};

export type GridHunt = {
  id: string;
  huntNumber: string | null;
  name: string;
  species: string;
  speciesLabel: string;
  series: string;
  methods: GridMethod[];
  access: GridAccess | string;
  bagLimit: string;
  start: string;
  end: string;
  tag: string;
  tagSaleDeadline: string | null;
  applicationDeadline: string | null;
  tags2026?: number | null;
  firstChoiceApplicants2025?: number | null;
  scope: string;
  unitIds: string[];
  restrictions: string[];
  notes: string;
  /** Who may hunt this opportunity; omit or "any" = both. */
  eligibility?: "any" | "resident_only" | "nonresident_only";
};

export type GridMeta = {
  seasonYear: string;
  generatedAt?: string;
  unitCount: number;
  huntCount?: number;
  disclaimer: string;
  species: { id: string; label: string }[];
  methods: { id: string; label: string }[];
  access: { id: string; label: string }[];
  sources: { name: string; url: string }[];
  layers?: { id: string; label: string }[];
};

export type GridFilters = {
  species: string[];
  methods: string[];
  access: string[];
  query: string;
  start: string;
  end: string;
  layer: string;
  /** Empty = Any; filters resident-only / nonresident-only rows when set. */
  hunterResidency: "" | "resident" | "nonresident";
};
