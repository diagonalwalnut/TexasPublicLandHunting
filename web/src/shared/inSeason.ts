export type InSeasonMethod = string;

export type InSeasonPlace = {
  id: string;
  label: string;
  methods: InSeasonMethod[];
  accessLabels: string[];
  windows: { start: string; end: string }[];
  /** Zone / portion notes for this place (e.g. "North Zone"). */
  notes: string[];
};

export type InSeasonSpecies = {
  species: string;
  label: string;
  /** True when every place in the current scope shares methods, windows, and access. */
  statewide: boolean;
  methods: InSeasonMethod[];
  accessLabels: string[];
  windows: { start: string; end: string }[];
  places: InSeasonPlace[];
  /** Notes that apply to the whole card when uniform (e.g. county is North Zone). */
  notes: string[];
};

export type InSeasonSourceRow = {
  species: string;
  speciesLabel: string;
  methods: string[];
  accessLabel: string;
  start: string;
  end: string;
  placeId: string;
  placeLabel: string;
  /** Optional county scope for Texas-style county filtering. */
  countyId?: string;
  countyLabel?: string;
  /** Zone or portion text that applies to this row. */
  zoneNote?: string;
  /** Who may hunt; omit or "any" = both. */
  eligibility?: "any" | "resident_only" | "nonresident_only";
  restrictions?: string[];
  notes?: string;
};

function covers(date: string, start: string, end: string): boolean {
  return start <= date && date <= end;
}

function uniq(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}

function keyMethods(methods: string[]): string {
  return [...methods].sort().join("|");
}

function keyWindows(windows: { start: string; end: string }[]): string {
  return windows.map((w) => `${w.start}:${w.end}`).sort().join("|");
}

/** Roll season rows into species cards, flagging place differences. */
export function buildInSeason(rows: InSeasonSourceRow[], date: string): InSeasonSpecies[] {
  const open = rows.filter((row) => covers(date, row.start, row.end));

  // Group by species id + label so Texas waterfowl (Duck vs Goose) stay separate cards.
  const byCard = new Map<string, InSeasonSourceRow[]>();
  for (const row of open) {
    const key = `${row.species}::${row.speciesLabel}`;
    const list = byCard.get(key) ?? [];
    list.push(row);
    byCard.set(key, list);
  }

  const cards: InSeasonSpecies[] = [];
  for (const list of byCard.values()) {
    const species = list[0]?.species || "";
    const placeMap = new Map<string, InSeasonPlace>();
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
    const methods = uniq(places.flatMap((place) => place.methods));
    const accessLabels = uniq(places.flatMap((place) => place.accessLabels));
    const windows = places.flatMap((place) => place.windows);
    const uniqueWindows = windows.filter(
      (window, index) =>
        windows.findIndex((other) => other.start === window.start && other.end === window.end) === index,
    );
    const notes = statewide ? uniq(places.flatMap((place) => place.notes)) : [];
    cards.push({
      species,
      label: list[0]?.speciesLabel || species,
      statewide,
      methods,
      accessLabels,
      windows: uniqueWindows.sort((a, b) => a.start.localeCompare(b.start)),
      places: statewide ? [] : places,
      notes,
    });
  }

  return cards.sort((a, b) => a.label.localeCompare(b.label));
}

export function methodLabel(id: string, labels?: Record<string, string>): string {
  return labels?.[id] ?? id.replaceAll("_", " ");
}

/** Unique counties from source rows, for a simple county dropdown. */
export function countyOptionsFromRows(
  rows: InSeasonSourceRow[],
): { id: string; label: string }[] {
  const map = new Map<string, string>();
  for (const row of rows) {
    if (!row.countyId || !row.countyLabel) continue;
    map.set(row.countyId, row.countyLabel);
  }
  return [...map.entries()]
    .map(([id, label]) => ({ id, label }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

/**
 * Keep only one county's rows, then re-label places as zone/portion inside that county.
 * Zone seasons (e.g. North Zone) become that county's rules — no other counties involved.
 */
export function scopeRowsToCounty(
  rows: InSeasonSourceRow[],
  countyId: string,
): InSeasonSourceRow[] {
  return rows
    .filter((row) => row.countyId === countyId)
    .map((row) => {
      const zoneParts = [row.zoneNote].filter(Boolean);
      const zone = zoneParts.join(" · ") || "Entire county";
      return {
        ...row,
        placeId: `${row.countyId}:${zone}`,
        placeLabel: zone,
      };
    });
}

/**
 * When no county is selected in county mode, roll places up to the county so the
 * overview does not explode into county·zone·portion combinations.
 */
export function rollupRowsByCounty(rows: InSeasonSourceRow[]): InSeasonSourceRow[] {
  return rows.map((row) => {
    if (!row.countyId || !row.countyLabel) return row;
    return {
      ...row,
      placeId: row.countyId,
      placeLabel: row.countyLabel,
    };
  });
}
