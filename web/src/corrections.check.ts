import assert from "node:assert/strict";
import { applyCorrections, rewriteMethods } from "./corrections.ts";
import type { Opportunity, Unit } from "./types.ts";

const ban = {
  unitId: "2547",
  forbidMethods: ["firearm"],
  speciesMethods: { white_tailed_deer: ["archery"], feral_hog: ["archery"] },
  note: "rifles prohibited",
};

assert.deepEqual(rewriteMethods(["any_legal"], "feral_hog", ban), ["archery"]);
assert.deepEqual(rewriteMethods(["firearm"], "white_tailed_deer", ban), []);
assert.deepEqual(rewriteMethods(["archery"], "white_tailed_deer", ban), ["archery"]);
assert.deepEqual(rewriteMethods(["shotgun"], "dove", ban), ["shotgun"]);
assert.deepEqual(rewriteMethods(["any_legal"], "squirrel", ban), []);

const unit = {
  id: "733",
  unitIds: ["733"],
  name: "Big Lake Bottom WMA",
  counties: ["Anderson"],
  region: "Pineywoods",
  acres: 1,
  type: "wma",
  pdfUrl: "",
  aerialPdfUrl: "",
  registration: "none",
  legalGameTags: [],
  legalGameText: "",
  species: ["white_tailed_deer", "feral_hog"],
  methods: ["archery", "firearm", "any_legal"],
  access: ["e_postcard"],
  complexes: [],
  hasEpostcard: true,
  hasRegularPermit: false,
  epostcardUrl: "",
  lon: 0,
  lat: 0,
} satisfies Unit;

const opportunities: Opportunity[] = [
  {
    id: "deer-gun",
    unitId: "733",
    species: "white_tailed_deer",
    speciesLabel: "White-tailed deer",
    methods: ["firearm"],
    access: "e_postcard",
    start: "2026-11-07",
    end: "2027-01-03",
    dateSource: "county",
    notes: "E-Postcard General Deer",
  },
  {
    id: "deer-bow",
    unitId: "733",
    species: "white_tailed_deer",
    speciesLabel: "White-tailed deer",
    methods: ["archery"],
    access: "e_postcard",
    start: "2026-10-03",
    end: "2026-11-06",
    dateSource: "county",
    notes: "E-Postcard Archery Deer",
  },
  {
    id: "hog",
    unitId: "733",
    species: "feral_hog",
    speciesLabel: "Feral hog",
    methods: ["any_legal"],
    access: "e_postcard",
    start: "2026-11-07",
    end: "2027-01-03",
    dateSource: "county",
    notes: "Feral Hog",
  },
];

const corrected = applyCorrections(
  [unit],
  opportunities,
  [{ unitId: "733", speciesMethods: { white_tailed_deer: ["archery"] }, note: "No season-long rifle deer" }],
);
assert.deepEqual(
  corrected.opportunities.filter((opp) => opp.species === "white_tailed_deer").map((opp) => opp.methods),
  [["archery"]],
);
assert.equal(corrected.opportunities.some((opp) => opp.id === "deer-gun"), false);
assert.deepEqual(corrected.opportunities.find((opp) => opp.id === "hog")?.methods, ["any_legal"]);
const deer = corrected.opportunities.filter((opp) => opp.species === "white_tailed_deer");
const rifle = deer.some((opp) => opp.methods.includes("firearm") || opp.methods.includes("any_legal"));
assert.equal(rifle, false);

console.log("corrections check ok");
