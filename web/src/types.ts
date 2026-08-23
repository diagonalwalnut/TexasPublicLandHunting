export type MethodId = "archery" | "firearm" | "muzzleloader" | "shotgun" | "any_legal";
export type AccessId =
  | "aph_walk_in"
  | "youth"
  | "youth_adult"
  | "e_postcard"
  | "regular_permit"
  | "drawn";

export type Unit = {
  id: string;
  unitIds: string[];
  name: string;
  counties: string[];
  region: string;
  acres: number | null;
  type: string;
  pdfUrl: string;
  aerialPdfUrl: string;
  registration: string;
  legalGameTags: string[];
  legalGameText: string;
  species: string[];
  methods: string[];
  access: string[];
  complexes: string[];
  hasEpostcard: boolean;
  hasRegularPermit: boolean;
  epostcardUrl: string;
  lon: number | null;
  lat: number | null;
};

export type Opportunity = {
  id: string;
  unitId: string;
  species: string;
  speciesLabel: string;
  methods: MethodId[];
  access: AccessId;
  start: string;
  end: string;
  dateSource: "county_default" | "unit_pdf";
  notes: string;
};

export type Meta = {
  seasonYear: string;
  generatedAt: string;
  unitCount: number;
  opportunityCount: number;
  polygonCount: number;
  disclaimer: string;
  sources: { name: string; url: string }[];
  species: { id: string; label: string }[];
  methods: { id: MethodId; label: string }[];
  access: { id: AccessId; label: string }[];
  regions: string[];
  counties: string[];
};

export type Filters = {
  species: string[];
  methods: MethodId[];
  access: AccessId[];
  region: string;
  county: string;
  query: string;
  start: string;
  end: string;
};

export type UnitFeatureProperties = Unit;
