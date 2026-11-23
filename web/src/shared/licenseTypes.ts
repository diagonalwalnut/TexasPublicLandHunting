export type LicenseBuyChannel = {
  id: string;
  title: string;
  body: string;
};

export type LicenseDeadline = {
  name: string;
  date: string | null;
  detail: string;
};

export type LicenseFeeRow = {
  item: string;
  resident: string;
  nonresident: string;
};

export type LicenseGuide = {
  title: string;
  seasonYear: string;
  intro: string;
  whereToBuy: LicenseBuyChannel[];
  deadlines: LicenseDeadline[];
  huntSeries?: { id: string; label: string; points: boolean }[];
  preferencePoints?: string[];
  fees: LicenseFeeRow[];
  sources: { name: string; url: string }[];
};

export type RegulationGuide = {
  title: string;
  methods?: { id: string; label: string; summary: string }[];
  prohibited: string[];
  unitRules: string[];
  sources: { name: string; url: string }[];
};
