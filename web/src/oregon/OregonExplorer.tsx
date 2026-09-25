import { useEffect, useMemo, useState } from "react";
import ExternalLink from "../ExternalLink";
import OregonMap from "./OregonMap";
import { formatDay, formatRange, huntMatches, huntsForUnit, matchingUnitIds } from "./filters";
import type {
  LicenseGuide,
  OregonAccess,
  OregonFilters,
  OregonHunt,
  OregonMeta,
  OregonMethod,
  OregonUnit,
  RegulationGuide,
} from "./types";

const EMPTY: OregonFilters = {
  species: [],
  methods: [],
  access: [],
  query: "",
  start: "",
  end: "",
  layer: "wmu",
};

type Pane = "map" | "hunts" | "licenses" | "rules";

const ACCESS_LABEL: Record<string, string> = {
  general_otc: "Over the counter",
  controlled_draw: "Controlled draw",
  youth_draw: "Youth draw",
  youth: "Youth season",
  premium: "Premium draw",
  additional: "Additional tag",
  no_tag: "No tag",
  validation: "Validation or stamp",
};

function toggle<T extends string>(list: T[], value: T): T[] {
  return list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
}

export default function OregonExplorer({ onClose }: { onClose: () => void }) {
  const [units, setUnits] = useState<OregonUnit[]>([]);
  const [hunts, setHunts] = useState<OregonHunt[]>([]);
  const [meta, setMeta] = useState<OregonMeta | null>(null);
  const [licenses, setLicenses] = useState<LicenseGuide | null>(null);
  const [rules, setRules] = useState<RegulationGuide | null>(null);
  const [wmuMap, setWmuMap] = useState<GeoJSON.FeatureCollection | null>(null);
  const [deerMap, setDeerMap] = useState<GeoJSON.FeatureCollection | null>(null);
  const [filters, setFilters] = useState<OregonFilters>(EMPTY);
  const [pane, setPane] = useState<Pane>("map");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [satellite, setSatellite] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async (path: string) => {
      const res = await fetch(path);
      if (!res.ok) throw new Error(path);
      return res.json();
    };
    Promise.all([
      load("data/oregon/units.json"),
      load("data/oregon/hunts.json"),
      load("data/oregon/meta.json"),
      load("data/oregon/licenses.json"),
      load("data/oregon/regulations.json"),
      load("data/oregon/wmu.geojson"),
      load("data/oregon/deer-areas.geojson"),
    ])
      .then(([u, h, m, lic, reg, wmu, deer]) => {
        setUnits(u);
        setHunts(h);
        setMeta(m);
        setLicenses(lic);
        setRules(reg);
        setWmuMap(wmu);
        setDeerMap(deer);
      })
      .catch(() => setError("Could not load the Oregon beta."));
  }, []);

  const layerUnits = useMemo(
    () => units.filter((unit) => unit.kind === filters.layer),
    [units, filters.layer],
  );
  const matchIds = useMemo(
    () => matchingUnitIds(units, hunts, filters),
    [units, hunts, filters],
  );
  const listed = useMemo(() => {
    return hunts
      .filter((hunt) => huntMatches(hunt, filters))
      .sort((a, b) => a.start.localeCompare(b.start) || a.name.localeCompare(b.name));
  }, [hunts, filters]);
  const selected = units.find((unit) => unit.id === selectedId) ?? null;
  const selectedHunts = selected ? huntsForUnit(selected.id, hunts, filters) : [];
  const geojson = filters.layer === "wmu" ? wmuMap : deerMap;

  return (
    <div className="relative z-20 flex min-h-0 flex-1 flex-col bg-sand text-ink">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-black/10 bg-pine px-4 py-2 text-sand">
        <div>
          <p className="text-xs uppercase tracking-wide text-gold">Admin beta</p>
          <h2 className="font-serif text-lg font-semibold">Oregon hunting, {meta?.seasonYear ?? "2026"}</h2>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {(["map", "hunts", "licenses", "rules"] as Pane[]).map((item) => (
            <button
              key={item}
              type="button"
              className={`rounded-full px-3 py-1 capitalize ${pane === item ? "bg-gold text-pine" : "text-sand/80"}`}
              onClick={() => setPane(item)}
            >
              {item === "hunts" ? "Hunts" : item}
            </button>
          ))}
          <button type="button" className="rounded-full border border-sand/30 px-3 py-1" onClick={onClose}>
            Back to Texas
          </button>
        </div>
      </div>

      {error ? (
        <p className="p-6 text-red-800">{error}</p>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          <aside className="scrollbar-thin order-2 max-h-[40vh] w-full shrink-0 overflow-y-auto border-t border-black/10 p-4 md:order-1 md:max-h-none md:w-80 md:border-r md:border-t-0">
            <FilterColumn
              filters={filters}
              meta={meta}
              matchCount={matchIds.size}
              layerCount={layerUnits.length}
              onChange={(next) => {
                setFilters(next);
                setSelectedId(null);
              }}
            />
            <p className="mt-4 text-xs leading-relaxed text-muted">{meta?.disclaimer}</p>
          </aside>

          <div className="relative order-1 min-h-[46vh] min-w-0 flex-1 md:order-2">
            <div className={pane === "map" ? "absolute inset-0" : "hidden"}>
              <OregonMap
                geojson={geojson}
                matchingIds={matchIds}
                selectedId={selectedId}
                satellite={satellite}
                active={pane === "map"}
                onSelect={setSelectedId}
              />
              <div className="pointer-events-none absolute left-3 top-3 z-10 max-w-sm rounded-md bg-white/90 px-3 py-2 text-sm shadow">
                <div className="font-semibold">
                  {filters.layer === "wmu" ? "Wildlife management units" : "Eastern deer hunt areas"}
                </div>
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
            {pane === "licenses" && licenses && <LicensePanel guide={licenses} />}
            {pane === "rules" && rules && <RulesPanel guide={rules} />}
          </div>

          {pane === "map" && selected && (
            <aside className="scrollbar-thin order-3 max-h-[36vh] w-full shrink-0 overflow-y-auto border-t border-black/10 bg-white p-4 md:max-h-none md:w-96 md:border-l md:border-t-0">
              <div className="mb-2 flex items-start justify-between gap-2">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted">
                    {selected.kind === "wmu" ? `Unit ${selected.code}` : selected.code} · {selected.region}
                  </p>
                  <h3 className="font-serif text-xl font-semibold">{selected.name}</h3>
                  {selected.acres ? (
                    <p className="text-sm text-muted">{selected.acres.toLocaleString()} acres</p>
                  ) : null}
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
  matchCount,
  layerCount,
  onChange,
}: {
  filters: OregonFilters;
  meta: OregonMeta | null;
  matchCount: number;
  layerCount: number;
  onChange: (filters: OregonFilters) => void;
}) {
  return (
    <div className="space-y-4 text-sm">
      <div>
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted">Map layer</p>
        <div className="flex rounded-full bg-white p-0.5 ring-1 ring-black/10">
          <button
            type="button"
            className={`flex-1 rounded-full px-2 py-1 ${filters.layer === "wmu" ? "bg-moss text-white" : ""}`}
            onClick={() => onChange({ ...filters, layer: "wmu" })}
          >
            All units
          </button>
          <button
            type="button"
            className={`flex-1 rounded-full px-2 py-1 ${filters.layer === "deer_hunt_area" ? "bg-moss text-white" : ""}`}
            onClick={() => onChange({ ...filters, layer: "deer_hunt_area" })}
          >
            Deer areas
          </button>
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
        onToggle={(id) => onChange({ ...filters, methods: toggle(filters.methods, id as OregonMethod) })}
      />
      <ChipGroup
        label="How the tag is issued"
        options={meta?.access ?? []}
        selected={filters.access}
        onToggle={(id) => onChange({ ...filters, access: toggle(filters.access, id as OregonAccess) })}
      />
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
      <button type="button" className="text-xs text-moss underline" onClick={() => onChange(EMPTY)}>
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

function UnitHunts({ hunts }: { hunts: OregonHunt[] }) {
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

function HuntBody({ hunt }: { hunt: OregonHunt }) {
  return (
    <>
      <p className="font-semibold">
        {hunt.huntNumber ? `${hunt.huntNumber} · ` : ""}
        {hunt.name}
      </p>
      <p>
        {hunt.speciesLabel} · {hunt.methods.map((method) => method.replace("_", " ")).join(", ")} ·{" "}
        {ACCESS_LABEL[hunt.access] ?? hunt.access}
      </p>
      <p>{formatRange(hunt.start, hunt.end)}</p>
      <p className="text-muted">{hunt.bagLimit}</p>
      <p className="text-xs text-muted">
        Tag: {hunt.tag}
        {hunt.tagSaleDeadline ? ` · buy by ${formatDay(hunt.tagSaleDeadline)}` : ""}
        {hunt.applicationDeadline ? ` · apply by ${formatDay(hunt.applicationDeadline)}` : ""}
        {hunt.tags2026 != null ? ` · ${hunt.tags2026.toLocaleString()} tags` : ""}
      </p>
      {hunt.notes ? <p className="text-xs text-muted">{hunt.notes}</p> : null}
      {hunt.restrictions.map((note) => (
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
  hunts: OregonHunt[];
  units: OregonUnit[];
  onOpenUnit: (id: string) => void;
}) {
  const byId = useMemo(() => new Map(units.map((unit) => [unit.id, unit])), [units]);
  return (
    <div className="scrollbar-thin absolute inset-0 overflow-y-auto bg-sand p-4">
      <p className="mb-3 text-sm text-muted">{hunts.length} hunts match. Zone seasons without a unit polygon stay in this list.</p>
      <ul className="space-y-3">
        {hunts.map((hunt) => (
          <li key={hunt.id} className="rounded-md bg-white p-3 text-sm shadow-sm">
            <HuntBody hunt={hunt} />
            {hunt.unitIds.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1">
                {hunt.unitIds.slice(0, 8).map((id) => {
                  const unit = byId.get(id);
                  return (
                    <button key={id} type="button" className="rounded bg-sand px-2 py-0.5 text-xs text-moss" onClick={() => onOpenUnit(id)}>
                      {unit ? `${unit.code} ${unit.name}` : id}
                    </button>
                  );
                })}
                {hunt.unitIds.length > 8 ? (
                  <span className="text-xs text-muted">+{hunt.unitIds.length - 8} areas</span>
                ) : null}
              </div>
            ) : (
              <p className="mt-1 text-xs text-muted">Shown in the hunt list. This season uses a migratory zone, not a wildlife unit.</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function LicensePanel({ guide }: { guide: LicenseGuide }) {
  return (
    <div className="scrollbar-thin absolute inset-0 overflow-y-auto bg-sand p-4 md:p-6">
      <h3 className="font-serif text-2xl font-semibold">{guide.title}</h3>
      <p className="mt-2 max-w-3xl text-sm leading-relaxed">{guide.intro}</p>
      <div className="mt-4 grid gap-3 md:grid-cols-2">
        {guide.whereToBuy.map((item) => (
          <section key={item.id} className="rounded-md bg-white p-3">
            <h4 className="font-semibold">{item.title}</h4>
            <p className="mt-1 text-sm leading-relaxed text-muted">{item.body}</p>
          </section>
        ))}
      </div>
      <h4 className="mt-6 font-semibold">Deadlines</h4>
      <ul className="mt-2 space-y-2">
        {guide.deadlines.map((row) => (
          <li key={row.name} className="rounded-md bg-white px-3 py-2 text-sm">
            <span className="font-medium">{row.name}</span>
            {row.date ? ` · ${formatDay(row.date)}` : ""}
            <span className="block text-muted">{row.detail}</span>
          </li>
        ))}
      </ul>
      <h4 className="mt-6 font-semibold">Preference points</h4>
      <ul className="mt-2 list-disc space-y-2 pl-5 text-sm leading-relaxed">
        {guide.preferencePoints.map((point) => (
          <li key={point}>{point}</li>
        ))}
      </ul>
      <h4 className="mt-6 font-semibold">Hunt series</h4>
      <ul className="mt-2 flex flex-wrap gap-2 text-sm">
        {guide.huntSeries.map((series) => (
          <li key={series.id} className="rounded-full bg-white px-3 py-1 ring-1 ring-black/10">
            {series.id} {series.label}
            {series.points ? "" : " · no points"}
          </li>
        ))}
      </ul>
      <h4 className="mt-6 font-semibold">2026 fees</h4>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full min-w-[28rem] text-left text-sm">
          <thead>
            <tr className="border-b border-black/10">
              <th className="py-1 pr-3 font-semibold">Item</th>
              <th className="py-1 pr-3 font-semibold">Resident</th>
              <th className="py-1 font-semibold">Nonresident</th>
            </tr>
          </thead>
          <tbody>
            {guide.fees.map((fee) => (
              <tr key={fee.item} className="border-b border-black/5">
                <td className="py-1 pr-3">{fee.item}</td>
                <td className="py-1 pr-3">{fee.resident}</td>
                <td className="py-1">{fee.nonresident}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <SourceList sources={guide.sources} />
    </div>
  );
}

function RulesPanel({ guide }: { guide: RegulationGuide }) {
  return (
    <div className="scrollbar-thin absolute inset-0 overflow-y-auto bg-sand p-4 md:p-6">
      <h3 className="font-serif text-2xl font-semibold">{guide.title}</h3>
      <div className="mt-4 space-y-3">
        {guide.methods.map((method) => (
          <section key={method.id} className="rounded-md bg-white p-3">
            <h4 className="font-semibold">{method.label}</h4>
            <p className="mt-1 text-sm leading-relaxed text-muted">{method.summary}</p>
          </section>
        ))}
      </div>
      <h4 className="mt-6 font-semibold">What can be hunted on a unit</h4>
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
      <SourceList sources={guide.sources} />
    </div>
  );
}

function SourceList({ sources }: { sources: { name: string; url: string }[] }) {
  return (
    <p className="mt-6 flex flex-wrap gap-3 text-sm">
      {sources.map((source) => (
        <ExternalLink key={source.url} className="text-moss underline" href={source.url}>
          {source.name}
        </ExternalLink>
      ))}
    </p>
  );
}
