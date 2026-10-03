export type MethodId = "archery" | "firearm" | "muzzleloader" | "shotgun" | "any_legal";
export type AccessId =
  | "aph_walk_in"
  | "youth"
  | "youth_adult"
  | "e_postcard"
  | "regular_permit"
  | "drawn"
  | "corps_permit";

export type UnitLink = { label: string; url: string };

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
  countySlugs?: string[];
  bookletPage?: string | null;
  bookletPdfPage?: number | null;
  bookletUrl?: string;
  lon: number | null;
  lat: number | null;
  source?: "tpwd" | "usace";
  managingAgency?: string;
  permitRequired?: boolean;
  permitInfo?: string;
  permitCost?: string;
  means?: string;
  links?: UnitLink[];
  mapPdfUrl?: string;
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
  dateSource: "county_default" | "unit_pdf" | "county";
  county?: string;
  notes: string;
};

export type CountySeason = {
  title: string;
  methods: MethodId[];
  access: AccessId;
  windows: { start: string; end: string }[];
  rawDates: string;
  notes: string;
};

export type CountyAnimal = {
  species: string;
  label: string;
  zone: string;
  bagLimit: string;
  antlerRestrictions: string;
  seasons: CountySeason[];
};

export type CountyHunting = {
  county: string;
  slug?: string;
  url: string;
  animals: CountyAnimal[];
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
  countiesWithCalendars?: number;
  unitsWithBookletPage?: number;
  bookletUrl?: string;
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
