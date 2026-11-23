import { useEffect, useMemo, useState } from "react";
import ExternalLink from "../../ExternalLink";
import InSeasonPage from "../../shared/InSeasonPage";
import LicenseGuideView from "../../shared/LicenseGuideView";
import type { LicenseGuide, RegulationGuide } from "../../shared/licenseTypes";
import type { InSeasonSourceRow } from "../../shared/inSeason";
import { datasetHasResidencyRestrictions } from "../../shared/residency";
import type { StateInfo } from "../../states/catalog";
import { formatDay, formatRange, huntMatches, huntsForUnit, matchingUnitIds } from "./filters";
import type { GridFilters, GridHunt, GridMeta, GridUnit } from "./types";
import UnitGridMap from "./UnitGridMap";

type Pane = "map" | "hunts" | "in-season" | "licenses" | "rules";

const ACCESS_LABEL: Record<string, string> = {
  general_otc: "Over the counter",
  controlled_draw: "Controlled / limited draw",
  youth_draw: "Youth draw",
  youth: "Youth season",
  premium: "Premium draw",
  additional: "Additional tag",
  no_tag: "No tag",
  validation: "Validation or stamp",
  lottery: "Lottery",
  corps_permit: "Corps permit",
  wma_permit: "WMA / public-land permit",
};

const BOUNDS: Record<string, [[number, number], [number, number]]> = {
  or: [
    [-124.7, 41.9],
    [-116.4, 46.4],
  ],
  nm: [
    [-109.2, 31.2],
    [-102.9, 37.1],
  ],
  co: [
    [-109.2, 36.9],
    [-102.0, 41.1],
  ],
};

function toggle(list: string[], value: string): string[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

function defaultLayer(units: GridUnit[], layers?: { id: string }[]): string {
  if (layers?.[0]?.id) return layers[0].id;
  const kinds = [...new Set(units.map((unit) => unit.kind))];
  if (kinds.includes("wmu")) return "wmu";
  if (kinds.includes("gmu")) return "gmu";
  return kinds[0] || "wmu";
}

export default function UnitGridExplorer({ state }: { state: StateInfo }) {
  const [units, setUnits] = useState<GridUnit[]>([]);
  const [hunts, setHunts] = useState<GridHunt[]>([]);
  const [meta, setMeta] = useState<GridMeta | null>(null);
  const [licenses, setLicenses] = useState<LicenseGuide | null>(null);
  const [rules, setRules] = useState<RegulationGuide | null>(null);
  const [primaryMap, setPrimaryMap] = useState<GeoJSON.FeatureCollection | null>(null);
  const [secondaryMap, setSecondaryMap] = useState<GeoJSON.FeatureCollection | null>(null);
  const [filters, setFilters] = useState<GridFilters>({
    species: [],
    methods: [],
    access: [],
    query: "",
    start: "",
    end: "",
    layer: "gmu",
    hunterResidency: "",
  });
  const [pane, setPane] = useState<Pane>("map");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [satellite, setSatellite] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPane("map");
    setSelectedId(null);
    setError(null);
    const load = async (path: string) => {
      const res = await fetch(path);
      if (!res.ok) throw new Error(path);
      return res.json();
    };
    const prefix = state.dataPrefix;
    const primaryPaths =
      state.id === "or"
        ? [`${prefix}/wmu.geojson`, `${prefix}/units.geojson`]
        : [`${prefix}/primary.geojson`, `${prefix}/units.geojson`, `${prefix}/wmu.geojson`];
    const secondaryPaths =
      state.id === "or"
        ? [`${prefix}/deer-areas.geojson`, `${prefix}/public-land.geojson`]
        : [`${prefix}/public-land.geojson`, `${prefix}/deer-areas.geojson`];
    const loadFirst = async (paths: string[]) => {
      for (const path of paths) {
        try {
          return await load(path);
        } catch {
          /* try next */
        }
      }
      return null;
    };
    Promise.all([
      load(`${prefix}/units.json`),
      load(`${prefix}/hunts.json`),
      load(`${prefix}/meta.json`),
      load(`${prefix}/licenses.json`),
      load(`${prefix}/regulations.json`),
      loadFirst(primaryPaths),
      loadFirst(secondaryPaths),
    ])
      .then(([u, h, m, lic, reg, primary, secondary]) => {
        if (!primary) throw new Error("primary map");
        setUnits(u);
        setHunts(h);
        setMeta(m);
        setLicenses(lic);
        setRules(reg);
        setPrimaryMap(primary);
        setSecondaryMap(secondary);
        setFilters((current) => ({
          ...current,
          layer: defaultLayer(u, m.layers),
          species: [],
          methods: [],
          access: [],
          query: "",
          start: "",
          end: "",
          hunterResidency: "",
        }));
      })
      .catch(() => setError(`Could not load ${state.name} hunting data.`));
  }, [state]);

  const layerOptions = useMemo(() => {
    if (meta?.layers?.length) return meta.layers;
    const kinds = [...new Set(units.map((unit) => unit.kind))];
    return kinds.map((id) => ({
      id,
      label:
        id === "wmu"
          ? "Wildlife units"
          : id === "deer_hunt_area"
            ? "Deer areas"
            : id === "gmu"
              ? "Game management units"
              : id === "public_land" || id === "corps" || id === "wma"
                ? "Public land / Corps"
                : id,
    }));
  }, [meta, units]);

  const layerUnits = useMemo(() => {
    if (filters.layer === "public_land") {
      return units.filter((unit) => ["public_land", "corps", "wma", "swa"].includes(unit.kind));
    }
    return units.filter((unit) => unit.kind === filters.layer);
  }, [units, filters.layer]);

  const matchIds = useMemo(() => matchingUnitIds(layerUnits, hunts, filters), [layerUnits, hunts, filters]);
  const listed = useMemo(
    () =>
      hunts
        .filter((hunt) => huntMatches(hunt, filters))
        .sort((a, b) => a.start.localeCompare(b.start) || a.name.localeCompare(b.name)),
    [hunts, filters],
  );
  const selected = units.find((unit) => unit.id === selectedId) ?? null;
  const selectedHunts = selected ? huntsForUnit(selected.id, hunts, filters) : [];
  const geojson =
    filters.layer === "deer_hunt_area" || filters.layer === "public_land" ? secondaryMap || primaryMap : primaryMap;

  const inSeasonRows: InSeasonSourceRow[] = useMemo(
    () =>
      hunts.flatMap((hunt) => {
        const placeIds = hunt.unitIds.length ? hunt.unitIds : [`scope:${hunt.scope || "statewide"}`];
        return placeIds.map((placeId) => {
          const unit = units.find((item) => item.id === placeId);
          return {
            species: hunt.species,
            speciesLabel: hunt.speciesLabel,
            methods: hunt.methods,
            accessLabel: ACCESS_LABEL[hunt.access] ?? hunt.access,
            start: hunt.start,
            end: hunt.end,
            placeId,
            placeLabel: unit
              ? `${unit.code} ${unit.name}${unit.region ? ` (${unit.region})` : ""}`
              : hunt.scope || "Statewide / zone season",
            eligibility: hunt.eligibility,
            restrictions: hunt.restrictions,
            notes: hunt.notes,
          };
        });
      }),
    [hunts, units],
  );

  const showHunterResidency = useMemo(() => datasetHasResidencyRestrictions(hunts), [hunts]);

  const methodLabels = Object.fromEntries((meta?.methods ?? []).map((row) => [row.id, row.label]));
  const bounds = BOUNDS[state.id] ?? BOUNDS.nm;

  return (
    <div className="relative z-10 flex min-h-0 flex-1 flex-col bg-sand text-ink">
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-black/10 bg-white/40 px-4 py-2 text-sm">
        {(["map", "hunts", "in-season", "licenses", "rules"] as Pane[]).map((item) => (
          <button
            key={item}
            type="button"
            className={`rounded-full px-3 py-1 capitalize ${pane === item ? "bg-moss text-white" : "text-pine"}`}
            onClick={() => setPane(item)}
          >
            {item === "in-season" ? "In Season" : item === "hunts" ? "Hunts" : item}
          </button>
        ))}
        <ExternalLink className="rounded-full border border-pine/20 px-3 py-1 text-moss" href={state.agencyUrl}>
          {state.agencyLabel}
        </ExternalLink>
      </div>

      {error ? (
        <p className="p-6 text-red-800">{error}</p>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          <aside className="scrollbar-thin order-2 max-h-[40vh] w-full shrink-0 overflow-y-auto border-t border-black/10 p-4 md:order-1 md:max-h-none md:w-80 md:border-r md:border-t-0">
            <FilterColumn
              filters={filters}
              meta={meta}
              layers={layerOptions}
              matchCount={matchIds.size}
              layerCount={layerUnits.length}
              showHunterResidency={showHunterResidency}
              onChange={(next) => {
                setFilters(next);
                setSelectedId(null);
              }}
            />
            <p className="mt-4 text-xs leading-relaxed text-muted">{meta?.disclaimer}</p>
          </aside>

          <div className="relative order-1 min-h-[46vh] min-w-0 flex-1 md:order-2">
            <div className={pane === "map" ? "absolute inset-0" : "hidden"}>
              <UnitGridMap
                geojson={geojson}
                matchingIds={matchIds}
                selectedId={selectedId}
                satellite={satellite}
                active={pane === "map"}
                bounds={bounds}
                onSelect={setSelectedId}
              />
              <div className="pointer-events-none absolute left-3 top-3 z-10 max-w-sm rounded-md bg-white/90 px-3 py-2 text-sm shadow">
                <div className="font-semibold">{layerOptions.find((row) => row.id === filters.layer)?.label ?? "Units"}</div>
                <p className="text-xs text-muted">
                  {matchIds.size} of {layerUnits.length} areas match. Click an area for seasons and methods.
                </p>
              </div>
              <button
                type="button"
                className="absolute right-3 top-14 z-10 rounded-md bg-white/90 px-2 py-1 text-xs shadow"
                onClick={() => setSatellite((value) => !value)}
              >
                {satellite ? "Map" : "Satellite"}
              </button>
            </div>
            {pane === "hunts" && (
              <HuntList
                hunts={listed}
                units={units}
                onOpenUnit={(id) => {
                  const unit = units.find((item) => item.id === id);
                  if (unit) setFilters((current) => ({ ...current, layer: unit.kind }));
                  setSelectedId(id);
                  setPane("map");
                }}
              />
            )}
            {pane === "in-season" && (
              <InSeasonPage
                rows={inSeasonRows}
                timezone={state.timezone}
                stateName={state.name}
                methodLabels={methodLabels}
                speciesLabels={Object.fromEntries((meta?.species ?? []).map((row) => [row.id, row.label]))}
                placeFilterLabel="Unit / region"
                shared={{
                  species: filters.species,
                  methods: filters.methods,
                  access: filters.access,
                  query: filters.query,
                  place: selected
                    ? `${selected.code} ${selected.name}${selected.region ? ` (${selected.region})` : ""}`
                    : "",
                  start: filters.start,
                  end: filters.end,
                  date: filters.start || undefined,
                  hunterResidency: filters.hunterResidency,
                }}
                onSharedChange={(next) => {
                  const place = (next.place || "").trim();
                  const matched = place
                    ? units.find((unit) => {
                        const label = `${unit.code} ${unit.name}${unit.region ? ` (${unit.region})` : ""}`;
                        return label === place || unit.name === place || unit.code === place;
                      })
                    : null;
                  setFilters((current) => ({
                    ...current,
                    species: next.species ?? [],
                    methods: next.methods ?? [],
                    access: next.access ?? current.access,
                    query: next.query ?? (matched ? "" : place || current.query),
                    start: next.date || next.start || "",
                    end: next.date || next.end || "",
                    layer: matched?.kind || current.layer,
                    hunterResidency:
                      (next.hunterResidency as GridFilters["hunterResidency"] | undefined) ??
                      current.hunterResidency,
                  }));
                  if (matched) setSelectedId(matched.id);
                  else if (place) setSelectedId(null);
                }}
              />
            )}
            {pane === "licenses" && licenses && <LicenseGuideView guide={licenses} />}
            {pane === "rules" && rules && <RulesPanel guide={rules} />}
          </div>

          {pane === "map" && selected && (
            <aside className="scrollbar-thin order-3 max-h-[36vh] w-full shrink-0 overflow-y-auto border-t border-black/10 bg-white p-4 md:max-h-none md:w-96 md:border-l md:border-t-0">
              <div className="mb-2 flex items-start justify-between gap-2">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted">
                    {selected.code} · {selected.region}
                  </p>
                  <h3 className="font-serif text-xl font-semibold">{selected.name}</h3>
                  {selected.acres ? <p className="text-sm text-muted">{selected.acres.toLocaleString()} acres</p> : null}
                </div>
                <button type="button" className="text-muted" onClick={() => setSelectedId(null)} aria-label="Close">
                  ✕
                </button>
              </div>
              <UnitHunts hunts={selectedHunts} />
            </aside>
          )}
        </div>
      )}
    </div>
  );
}

function FilterColumn({
  filters,
  meta,
  layers,
  matchCount,
  layerCount,
  onChange,
  showHunterResidency = false,
}: {
  filters: GridFilters;
  meta: GridMeta | null;
  layers: { id: string; label: string }[];
  matchCount: number;
  layerCount: number;
  onChange: (filters: GridFilters) => void;
  showHunterResidency?: boolean;
}) {
  return (
    <div className="space-y-4 text-sm">
      <div>
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Map layer</p>
        <div className="flex flex-wrap gap-1">
          {layers.map((layer) => (
            <button
              key={layer.id}
              type="button"
              className={`rounded-full px-2 py-1 ${filters.layer === layer.id ? "bg-moss text-white" : "bg-white ring-1 ring-black/10"}`}
              onClick={() => onChange({ ...filters, layer: layer.id })}
            >
              {layer.label}
            </button>
          ))}
        </div>
        <p className="mt-1 text-xs text-muted">
          {matchCount} of {layerCount} shown
        </p>
      </div>
      <label className="block">
        <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted">Search</span>
        <input
          className="w-full rounded border border-black/10 bg-white px-2 py-1"
          value={filters.query}
          placeholder="Hunt, unit, or species"
          onChange={(event) => onChange({ ...filters, query: event.target.value })}
        />
      </label>
      <ChipGroup
        label="Animals"
        options={meta?.species ?? []}
        selected={filters.species}
        onToggle={(id) => onChange({ ...filters, species: toggle(filters.species, id) })}
      />
      <ChipGroup
        label="Method"
        options={meta?.methods ?? []}
        selected={filters.methods}
        onToggle={(id) => onChange({ ...filters, methods: toggle(filters.methods, id) })}
      />
      <ChipGroup
        label="How the tag is issued"
        options={meta?.access ?? []}
        selected={filters.access}
        onToggle={(id) => onChange({ ...filters, access: toggle(filters.access, id) })}
      />
      {showHunterResidency ? (
        <label className="block">
          <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted">Hunter</span>
          <select
            className="w-full rounded border border-black/10 bg-white px-2 py-1"
            value={filters.hunterResidency}
            onChange={(event) =>
              onChange({
                ...filters,
                hunterResidency: event.target.value as GridFilters["hunterResidency"],
              })
            }
          >
            <option value="">Any</option>
            <option value="resident">Resident</option>
            <option value="nonresident">Nonresident</option>
          </select>
        </label>
      ) : null}
      <div className="grid grid-cols-2 gap-2">
        <label className="block">
          <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted">Season from</span>
          <input
            type="date"
            className="w-full rounded border border-black/10 bg-white px-2 py-1"
            value={filters.start}
            onChange={(event) => onChange({ ...filters, start: event.target.value })}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted">Season to</span>
          <input
            type="date"
            className="w-full rounded border border-black/10 bg-white px-2 py-1"
            value={filters.end}
            onChange={(event) => onChange({ ...filters, end: event.target.value })}
          />
        </label>
      </div>
      <button
        type="button"
        className="text-xs text-moss underline"
        onClick={() =>
          onChange({
            species: [],
            methods: [],
            access: [],
            query: "",
            start: "",
            end: "",
            layer: filters.layer,
            hunterResidency: "",
          })
        }
      >
        Clear filters
      </button>
    </div>
  );
}

function ChipGroup({
  label,
  options,
  selected,
  onToggle,
}: {
  label: string;
  options: { id: string; label: string }[];
  selected: string[];
  onToggle: (id: string) => void;
}) {
  return (
    <div>
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
      <div className="flex flex-wrap gap-1">
        {options.map((option) => {
          const on = selected.includes(option.id);
          return (
            <button
              key={option.id}
              type="button"
              className={`rounded-full px-2 py-0.5 text-xs ${on ? "bg-moss text-white" : "bg-white ring-1 ring-black/10"}`}
              onClick={() => onToggle(option.id)}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function UnitHunts({ hunts }: { hunts: GridHunt[] }) {
  if (hunts.length === 0) {
    return <p className="text-sm text-muted">No hunts on this area match the current filters.</p>;
  }
  return (
    <ul className="space-y-3">
      {hunts.map((hunt) => (
        <li key={hunt.id} className="border-b border-black/5 pb-2 text-sm">
          <HuntBody hunt={hunt} />
        </li>
      ))}
    </ul>
  );
}

function HuntBody({ hunt }: { hunt: GridHunt }) {
  return (
    <>
      <p className="font-semibold">
        {hunt.huntNumber ? `${hunt.huntNumber} · ` : ""}
        {hunt.name}
      </p>
      <p>
        {hunt.speciesLabel} · {hunt.methods.map((method) => method.replaceAll("_", " ")).join(", ")} ·{" "}
        {ACCESS_LABEL[hunt.access] ?? hunt.access}
      </p>
      <p>{formatRange(hunt.start, hunt.end)}</p>
      {hunt.bagLimit ? <p className="text-muted">{hunt.bagLimit}</p> : null}
      <p className="text-xs text-muted">
        Tag: {hunt.tag || "See regulations"}
        {hunt.tagSaleDeadline ? ` · buy by ${formatDay(hunt.tagSaleDeadline)}` : ""}
        {hunt.applicationDeadline ? ` · apply by ${formatDay(hunt.applicationDeadline)}` : ""}
      </p>
      {hunt.notes ? <p className="text-xs text-muted">{hunt.notes}</p> : null}
      {(hunt.restrictions || []).map((note) => (
        <p key={note} className="text-xs text-muted">
          {note}
        </p>
      ))}
    </>
  );
}

function HuntList({
  hunts,
  units,
  onOpenUnit,
}: {
  hunts: GridHunt[];
  units: GridUnit[];
  onOpenUnit: (id: string) => void;
}) {
  const byId = useMemo(() => new Map(units.map((unit) => [unit.id, unit])), [units]);
  return (
    <div className="scrollbar-thin absolute inset-0 overflow-y-auto bg-sand p-4">
      <p className="mb-3 text-sm text-muted">
        {hunts.length} hunts match. Zone seasons without a unit polygon stay in this list.
      </p>
      <ul className="space-y-3">
        {hunts.map((hunt) => (
          <li key={hunt.id} className="rounded-md bg-white p-3 text-sm shadow-sm">
            <HuntBody hunt={hunt} />
            {hunt.unitIds.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1">
                {hunt.unitIds.slice(0, 8).map((id) => {
                  const unit = byId.get(id);
                  return (
                    <button
                      key={id}
                      type="button"
                      className="rounded bg-sand px-2 py-0.5 text-xs text-moss"
                      onClick={() => onOpenUnit(id)}
                    >
                      {unit ? `${unit.code} ${unit.name}` : id}
                    </button>
                  );
                })}
                {hunt.unitIds.length > 8 ? (
                  <span className="text-xs text-muted">+{hunt.unitIds.length - 8} areas</span>
                ) : null}
              </div>
            ) : (
              <p className="mt-1 text-xs text-muted">Listed by season scope, not a single unit polygon.</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function RulesPanel({ guide }: { guide: RegulationGuide }) {
  return (
    <div className="scrollbar-thin absolute inset-0 overflow-y-auto bg-sand p-4 md:p-6">
      <h3 className="font-serif text-2xl font-semibold">{guide.title}</h3>
      <div className="mt-4 space-y-3">
        {(guide.methods ?? []).map((method) => (
          <section key={method.id} className="rounded-md bg-white p-3">
            <h4 className="font-semibold">{method.label}</h4>
            <p className="mt-1 text-sm leading-relaxed text-muted">{method.summary}</p>
          </section>
        ))}
      </div>
      <h4 className="mt-6 font-semibold">Unit and area rules</h4>
      <ul className="mt-2 list-disc space-y-2 pl-5 text-sm">
        {guide.unitRules.map((rule) => (
          <li key={rule}>{rule}</li>
        ))}
      </ul>
      <h4 className="mt-6 font-semibold">Restrictions</h4>
      <ul className="mt-2 list-disc space-y-2 pl-5 text-sm">
        {guide.prohibited.map((rule) => (
          <li key={rule}>{rule}</li>
        ))}
      </ul>
      <p className="mt-6 flex flex-wrap gap-3 text-sm">
        {guide.sources.map((source) => (
          <ExternalLink key={source.url} className="text-moss underline" href={source.url}>
            {source.name}
          </ExternalLink>
        ))}
      </p>
    </div>
  );
}
