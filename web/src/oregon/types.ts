export type OregonMethod = "any_legal" | "firearm" | "archery" | "muzzleloader" | "shotgun";

export type OregonAccess =
  | "general_otc"
  | "controlled_draw"
  | "youth_draw"
  | "youth"
  | "premium"
  | "additional"
  | "no_tag"
  | "validation";

export type OregonUnit = {
  id: string;
  kind: "wmu" | "deer_hunt_area";
  code: string;
  name: string;
  region: string;
  acres: number | null;
  herdRange?: string;
};

export type OregonHunt = {
  id: string;
  huntNumber: string | null;
  name: string;
  species: string;
  speciesLabel: string;
  series: string;
  methods: OregonMethod[];
  access: OregonAccess;
  bagLimit: string;
  start: string;
  end: string;
  tag: string;
  tagSaleDeadline: string | null;
  applicationDeadline: string | null;
  tags2026: number | null;
  firstChoiceApplicants2025: number | null;
  scope: string;
  unitIds: string[];
  restrictions: string[];
  notes: string;
};

export type OregonMeta = {
  seasonYear: string;
  generatedAt: string;
  unitCount: number;
  wmuCount: number;
  deerHuntAreaCount: number;
  huntCount: number;
  controlledCount: number;
  disclaimer: string;
  species: { id: string; label: string }[];
  methods: { id: OregonMethod; label: string }[];
  access: { id: OregonAccess; label: string }[];
  sources: { name: string; url: string }[];
};

export type OregonFilters = {
  species: string[];
  methods: OregonMethod[];
  access: OregonAccess[];
  query: string;
  start: string;
  end: string;
  layer: "wmu" | "deer_hunt_area";
};

export type LicenseGuide = {
  title: string;
  seasonYear: string;
  intro: string;
  whereToBuy: { id: string; title: string; body: string }[];
  deadlines: { name: string; date: string | null; detail: string }[];
  huntSeries: { id: string; label: string; points: boolean }[];
  preferencePoints: string[];
  fees: { item: string; resident: string; nonresident: string }[];
  sources: { name: string; url: string }[];
};

export type RegulationGuide = {
  title: string;
  methods: { id: string; label: string; summary: string }[];
  prohibited: string[];
  unitRules: string[];
  sources: { name: string; url: string }[];
};
