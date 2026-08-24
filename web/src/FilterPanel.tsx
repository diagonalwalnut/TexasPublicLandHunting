import type { AccessId, DrawnMeta, Filters, Meta, MethodId } from "./types";

export type FilterPreset = {
  label: string;
  species: string[];
  methods: MethodId[];
  access?: AccessId[];
};

export const PRESETS: FilterPreset[] = [
  { label: "Whitetail + rifle", species: ["white_tailed_deer"], methods: ["firearm"] },
  { label: "Whitetail + archery", species: ["white_tailed_deer"], methods: ["archery"] },
  { label: "Dove + shotgun", species: ["dove"], methods: ["shotgun"] },
  { label: "Feral hog", species: ["feral_hog"], methods: [] },
  { label: "Squirrel", species: ["squirrel"], methods: [] },
];

export const DRAWN_PRESETS: FilterPreset[] = [
  { label: "Whitetail + rifle", species: ["white_tailed_deer"], methods: ["firearm"] },
  { label: "Youth hunts", species: [], methods: [], access: ["youth", "youth_adult"] },
  { label: "Alligator", species: ["alligator"], methods: [] },
  { label: "Exotic", species: ["exotic_mammals"], methods: [] },
  { label: "Waterfowl", species: ["waterfowl"], methods: [] },
];

const EMPTY: Filters = {
  species: [],
  methods: [],
  access: [],
  region: "",
  county: "",
  query: "",
  start: "",
  end: "",
};

function toggleValue<T extends string>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

type Props = {
  filters: Filters;
  meta: Pick<Meta, "species" | "methods" | "access" | "regions" | "counties"> | Pick<DrawnMeta, "species" | "methods" | "access" | "regions" | "counties"> | null;
  onChange: (filters: Filters) => void;
  onPreset?: (filters: Filters) => void;
  presets?: FilterPreset[];
  searchPlaceholder?: string;
};

export default function FilterPanel({
  filters,
  meta,
  onChange,
  onPreset,
  presets = PRESETS,
  searchPlaceholder = "Unit name, number, county, booklet page",
}: Props) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Quick reports</p>
      <div className="mb-3 flex flex-wrap gap-1">
        {presets.map((preset) => {
          const presetAccess = preset.access ?? [];
          const active =
            JSON.stringify(filters.species) === JSON.stringify(preset.species) &&
            JSON.stringify(filters.methods) === JSON.stringify(preset.methods) &&
            JSON.stringify(filters.access) === JSON.stringify(presetAccess);
          return (
            <button
              key={preset.label}
              type="button"
              className={`rounded-full px-2 py-0.5 text-xs ${
                active ? "bg-moss text-white" : "bg-white text-muted ring-1 ring-black/10 hover:bg-moss hover:text-white"
              }`}
              onClick={() => {
                const next = {
                  ...EMPTY,
                  species: preset.species,
                  methods: preset.methods,
                  access: presetAccess,
                };
                onChange(next);
                onPreset?.(next);
              }}
            >
              {preset.label}
            </button>
          );
        })}
      </div>

      <label className="mb-3 block text-sm">
        Search
        <input
          className="mt-1 w-full rounded-md border border-black/15 bg-white px-2 py-1.5"
          placeholder={searchPlaceholder}
          value={filters.query}
          onChange={(e) => onChange({ ...filters, query: e.target.value })}
        />
      </label>

      <div className="mb-3 grid grid-cols-2 gap-2">
        <label className="text-sm">
          From
          <input
            type="date"
            className="mt-1 w-full rounded-md border border-black/15 bg-white px-2 py-1.5"
            value={filters.start}
            onChange={(e) => onChange({ ...filters, start: e.target.value })}
          />
        </label>
        <label className="text-sm">
          To
          <input
            type="date"
            className="mt-1 w-full rounded-md border border-black/15 bg-white px-2 py-1.5"
            value={filters.end}
            onChange={(e) => onChange({ ...filters, end: e.target.value })}
          />
        </label>
      </div>

      <fieldset className="mb-3">
        <legend className="mb-1 text-sm font-semibold">Animal</legend>
        <div className="flex flex-wrap gap-1">
          {(meta?.species ?? []).map((s) => {
            const on = filters.species.includes(s.id);
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => onChange({ ...filters, species: toggleValue(filters.species, s.id) })}
                className={`rounded-full px-2 py-0.5 text-xs ${on ? "bg-moss text-white" : "bg-white text-muted ring-1 ring-black/10"}`}
              >
                {s.label}
              </button>
            );
          })}
        </div>
      </fieldset>

      <fieldset className="mb-3">
        <legend className="mb-1 text-sm font-semibold">Method</legend>
        <div className="flex flex-wrap gap-1">
          {(meta?.methods ?? []).map((m) => {
            const on = filters.methods.includes(m.id);
            return (
              <button
                key={m.id}
                type="button"
                onClick={() =>
                  onChange({ ...filters, methods: toggleValue(filters.methods, m.id as MethodId) })
                }
                className={`rounded-full px-2 py-0.5 text-xs ${on ? "bg-moss text-white" : "bg-white text-muted ring-1 ring-black/10"}`}
              >
                {m.label}
              </button>
            );
          })}
        </div>
      </fieldset>

      <fieldset className="mb-3">
        <legend className="mb-1 text-sm font-semibold">Access</legend>
        <div className="flex flex-wrap gap-1">
          {(meta?.access ?? []).map((a) => {
            const on = filters.access.includes(a.id);
            return (
              <button
                key={a.id}
                type="button"
                onClick={() =>
                  onChange({ ...filters, access: toggleValue(filters.access, a.id as AccessId) })
                }
                className={`rounded-full px-2 py-0.5 text-xs ${on ? "bg-moss text-white" : "bg-white text-muted ring-1 ring-black/10"}`}
              >
                {a.label}
              </button>
            );
          })}
        </div>
      </fieldset>

      <label className="mb-2 block text-sm">
        Region
        <select
          className="mt-1 w-full rounded-md border border-black/15 bg-white px-2 py-1.5"
          value={filters.region}
          onChange={(e) => onChange({ ...filters, region: e.target.value })}
        >
          <option value="">All regions</option>
          {(meta?.regions ?? []).map((r) => (
            <option key={r}>{r}</option>
          ))}
        </select>
      </label>

      <label className="mb-3 block text-sm">
        County
        <select
          className="mt-1 w-full rounded-md border border-black/15 bg-white px-2 py-1.5"
          value={filters.county}
          onChange={(e) => onChange({ ...filters, county: e.target.value })}
        >
          <option value="">All counties</option>
          {(meta?.counties ?? []).map((c) => (
            <option key={c}>{c}</option>
          ))}
        </select>
      </label>

      <button type="button" className="text-sm text-moss underline" onClick={() => onChange(EMPTY)}>
        Clear filters
      </button>
    </div>
  );
}
