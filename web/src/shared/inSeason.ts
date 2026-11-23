export type InSeasonMethod = string;

export type InSeasonPlace = {
  id: string;
  label: string;
  methods: InSeasonMethod[];
  accessLabels: string[];
  windows: { start: string; end: string }[];
};

export type InSeasonSpecies = {
  species: string;
  label: string;
  statewide: boolean;
  methods: InSeasonMethod[];
  accessLabels: string[];
  windows: { start: string; end: string }[];
  places: InSeasonPlace[];
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
  const bySpecies = new Map<string, InSeasonSourceRow[]>();
  for (const row of open) {
    const list = bySpecies.get(row.species) ?? [];
    list.push(row);
    bySpecies.set(row.species, list);
  }

  const cards: InSeasonSpecies[] = [];
  for (const [species, list] of bySpecies) {
    const placeMap = new Map<string, InSeasonPlace>();
    for (const row of list) {
      const existing = placeMap.get(row.placeId);
      if (!existing) {
        placeMap.set(row.placeId, {
          id: row.placeId,
          label: row.placeLabel,
          methods: uniq(row.methods),
          accessLabels: uniq([row.accessLabel]),
          windows: [{ start: row.start, end: row.end }],
        });
        continue;
      }
      existing.methods = uniq([...existing.methods, ...row.methods]);
      existing.accessLabels = uniq([...existing.accessLabels, row.accessLabel]);
      if (!existing.windows.some((w) => w.start === row.start && w.end === row.end)) {
        existing.windows.push({ start: row.start, end: row.end });
      }
    }
    const places = [...placeMap.values()].sort((a, b) => a.label.localeCompare(b.label));
    const signature = places.map(
      (place) => `${keyMethods(place.methods)}::${keyWindows(place.windows)}::${place.accessLabels.sort().join(",")}`,
    );
    const statewide = signature.length > 0 && signature.every((item) => item === signature[0]);
    const methods = uniq(places.flatMap((place) => place.methods));
    const accessLabels = uniq(places.flatMap((place) => place.accessLabels));
    const windows = places.flatMap((place) => place.windows);
    const uniqueWindows = windows.filter(
      (window, index) =>
        windows.findIndex((other) => other.start === window.start && other.end === window.end) === index,
    );
    cards.push({
      species,
      label: list[0]?.speciesLabel || species,
      statewide,
      methods,
      accessLabels,
      windows: uniqueWindows.sort((a, b) => a.start.localeCompare(b.start)),
      places: statewide ? [] : places,
    });
  }

  return cards.sort((a, b) => a.label.localeCompare(b.label));
}

export function methodLabel(id: string, labels?: Record<string, string>): string {
  return labels?.[id] ?? id.replaceAll("_", " ");
}
