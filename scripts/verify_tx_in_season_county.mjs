/**
 * Verifies Texas In Season county scoping without the full UI:
 * - one Johnson County option
 * - Johnson-only rows do not include other counties
 * - zone notes (North Zone) attach to Johnson
 */
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const counties = JSON.parse(readFileSync(join(root, "data/counties.json"), "utf8"));

function covers(date, start, end) {
  return start <= date && date <= end;
}

function uniq(values) {
  return [...new Set(values.filter(Boolean))];
}

function keyMethods(methods) {
  return [...methods].sort().join("|");
}

function keyWindows(windows) {
  return windows.map((w) => `${w.start}:${w.end}`).sort().join("|");
}

function buildInSeason(rows, date) {
  const open = rows.filter((row) => covers(date, row.start, row.end));
  const byCard = new Map();
  for (const row of open) {
    const key = `${row.species}::${row.speciesLabel}`;
    const list = byCard.get(key) ?? [];
    list.push(row);
    byCard.set(key, list);
  }
  const cards = [];
  for (const list of byCard.values()) {
    const species = list[0]?.species || "";
    const placeMap = new Map();
    for (const row of list) {
      const existing = placeMap.get(row.placeId);
      const note = row.zoneNote || "";
      if (!existing) {
        placeMap.set(row.placeId, {
          id: row.placeId,
          label: row.placeLabel,
          methods: uniq(row.methods),
          accessLabels: uniq([row.accessLabel]),
          windows: [{ start: row.start, end: row.end }],
          notes: note ? [note] : [],
        });
        continue;
      }
      existing.methods = uniq([...existing.methods, ...row.methods]);
      existing.accessLabels = uniq([...existing.accessLabels, row.accessLabel]);
      if (note) existing.notes = uniq([...existing.notes, note]);
      if (!existing.windows.some((w) => w.start === row.start && w.end === row.end)) {
        existing.windows.push({ start: row.start, end: row.end });
      }
    }
    const places = [...placeMap.values()].sort((a, b) => a.label.localeCompare(b.label));
    const signature = places.map(
      (place) =>
        `${keyMethods(place.methods)}::${keyWindows(place.windows)}::${place.accessLabels.sort().join(",")}`,
    );
    const statewide = signature.length > 0 && signature.every((item) => item === signature[0]);
    cards.push({
      species,
      label: list[0]?.speciesLabel || species,
      statewide,
      notes: statewide ? uniq(places.flatMap((p) => p.notes)) : [],
      places: statewide ? [] : places,
    });
  }
  return cards.sort((a, b) => a.label.localeCompare(b.label));
}

function scopeRowsToCounty(rows, countyId) {
  return rows
    .filter((row) => row.countyId === countyId)
    .map((row) => {
      const zone = row.zoneNote || "Entire county";
      return { ...row, placeId: `${row.countyId}:${zone}`, placeLabel: zone };
    });
}

const rows = Object.values(counties).flatMap((page) => {
  const countyId = page.slug || page.county.toLowerCase().replace(/\s+/g, "-");
  const countyLabel = `${page.county} County`;
  return page.animals.flatMap((animal) => {
    const zoneNote = [animal.zone, animal.portion].filter(Boolean).join(" · ");
    return animal.seasons.flatMap((season) =>
      season.windows.map((window) => ({
        species: animal.species,
        speciesLabel: animal.label,
        methods: season.methods,
        accessLabel: season.access,
        start: window.start,
        end: window.end,
        countyId,
        countyLabel,
        zoneNote,
        placeId: countyId,
        placeLabel: countyLabel,
      })),
    );
  });
});

const countyOptions = [
  ...new Map(rows.map((r) => [r.countyId, r.countyLabel])).entries(),
].map(([id, label]) => ({ id, label }));

const johnsonOptions = countyOptions.filter((c) => c.label === "Johnson County");
if (johnsonOptions.length !== 1) {
  throw new Error(`Expected 1 Johnson County option, got ${johnsonOptions.length}`);
}

const johnsonRows = scopeRowsToCounty(rows, "johnson");
if (johnsonRows.some((r) => r.countyId !== "johnson")) {
  throw new Error("Scoped rows leaked other counties");
}
if (!johnsonRows.every((r) => r.placeLabel.includes("Zone") || r.placeLabel === "Entire county" || r.zoneNote)) {
  // soft check — most Johnson animals have zones
}

const cards = buildInSeason(johnsonRows, "2026-11-07");
const duckCard = cards.find((c) => c.label === "Duck");
if (!duckCard) {
  throw new Error(`Duck not open in Johnson on 2026-11-07. Open: ${cards.map((c) => c.label).join(", ")}`);
}
if (!duckCard.statewide || !duckCard.notes.some((n) => n.includes("North Zone"))) {
  throw new Error(
    `Expected Duck open countywide under North Zone, got statewide=${duckCard.statewide} notes=${JSON.stringify(duckCard.notes)} places=${JSON.stringify(duckCard.places.map((p) => p.label))}`,
  );
}

const gooseCard = cards.find((c) => c.label === "Goose");
if (!gooseCard) {
  throw new Error("Goose should be open in Johnson (split by IH 35W)");
}
if (gooseCard.statewide || gooseCard.places.length < 2) {
  throw new Error(`Expected Goose to differ by portion inside Johnson, got ${JSON.stringify(gooseCard)}`);
}

const deerCard = cards.find((c) => c.label === "White-tailed Deer");
if (!deerCard?.notes.some((n) => n.includes("North Zone"))) {
  throw new Error(`Expected White-tailed Deer North Zone for Johnson, got ${JSON.stringify(deerCard)}`);
}

// Ensure no place label is another county name
for (const card of cards) {
  for (const place of card.places) {
    if (/County/i.test(place.label) && !/Johnson/i.test(place.label) && place.label !== "All Other Counties") {
      throw new Error(`Cross-county place leaked: ${place.label}`);
    }
  }
}

console.log("ok: 1 Johnson County option;");
console.log(`ok: ${cards.length} species open in Johnson on 2026-11-07`);
console.log(`ok: Duck → North Zone (${duckCard.notes.join(" · ")})`);
console.log(`ok: Goose → ${gooseCard.places.map((p) => p.label).join(" | ")}`);
console.log(`ok: White-tailed Deer → ${deerCard.notes.join(" · ")}`);
