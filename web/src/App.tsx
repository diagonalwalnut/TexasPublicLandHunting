import { useEffect, useMemo, useState } from "react";
import HuntMap from "./HuntMap";
import type { AccessId, CountyHunting, Filters, Meta, MethodId, Opportunity, Unit } from "./types";
import {
  ACCESS_LABEL,
  METHOD_LABEL,
  TYPE_LABEL,
  formatRange,
  matchingUnitIds,
  unitOpportunities,
} from "./filters";

const EMPTY_FILTERS: Filters = {
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

export default function App() {
  const [units, setUnits] = useState<Unit[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [counties, setCounties] = useState<Record<string, CountyHunting>>({});
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [satellite, setSatellite] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch("data/units.json").then((r) => r.json()),
      fetch("data/opportunities.json").then((r) => r.json()),
      fetch("data/meta.json").then((r) => r.json()),
      fetch("data/counties.json").then((r) => r.json()),
    ])
      .then(([u, o, m, c]) => {
        setUnits(u);
        setOpportunities(o);
        setMeta(m);
        setCounties(c);
      })
      .catch(() => setError("Could not load hunt data."));
  }, []);

  const matchIds = useMemo(
    () => matchingUnitIds(units, opportunities, filters),
    [units, opportunities, filters],
  );
  const selected = units.find((u) => u.id === selectedId) ?? null;
  const selectedCountyPages = useMemo(() => {
    if (!selected?.countySlugs) return [];
    return selected.countySlugs.map((slug) => counties[slug]).filter(Boolean);
  }, [selected, counties]);
  const selectedOpps = selected ? unitOpportunities(selected.id, opportunities, filters) : [];

  const groupedOpps = useMemo(() => {
    const map = new Map<string, Opportunity[]>();
    for (const opp of selectedOpps) {
      const list = map.get(opp.species) ?? [];
      list.push(opp);
      map.set(opp.species, list);
    }
    return [...map.entries()];
  }, [selectedOpps]);

  return (
    <div className="flex h-full min-h-0 flex-col bg-sand text-ink">
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-black/10 bg-pine px-4 py-3 text-sand">
        <div>
          <h1 className="font-serif text-xl font-semibold tracking-tight md:text-2xl">
            Texas Public Land Hunting
          </h1>
          <p className="text-sm text-sand/80">
            {meta ? `${meta.seasonYear} APH / walk-in units` : "Loading…"} · unofficial planning map
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="rounded-full bg-gold/20 px-3 py-1 text-gold">
            {matchIds.size} of {units.length} areas
          </span>
          <a
            className="rounded-full border border-sand/30 px-3 py-1 hover:bg-white/10"
            href="https://tpwd.texas.gov/huntwild/hunt/public/annual_public_hunting/"
            target="_blank"
            rel="noreferrer"
          >
            TPWD APH
          </a>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <aside className="scrollbar-thin order-2 max-h-[42vh] shrink-0 overflow-y-auto border-t border-black/10 bg-sand p-4 md:order-1 md:max-h-none md:w-80 md:border-r md:border-t-0">
          <label className="mb-3 block text-sm">
            Search
            <input
              className="mt-1 w-full rounded-md border border-black/15 bg-white px-2 py-1.5"
              placeholder="Unit name, number, county"
              value={filters.query}
              onChange={(e) => setFilters((f) => ({ ...f, query: e.target.value }))}
            />
          </label>

          <div className="mb-3 grid grid-cols-2 gap-2">
            <label className="text-sm">
              From
              <input
                type="date"
                className="mt-1 w-full rounded-md border border-black/15 bg-white px-2 py-1.5"
                value={filters.start}
                onChange={(e) => setFilters((f) => ({ ...f, start: e.target.value }))}
              />
            </label>
            <label className="text-sm">
              To
              <input
                type="date"
                className="mt-1 w-full rounded-md border border-black/15 bg-white px-2 py-1.5"
                value={filters.end}
                onChange={(e) => setFilters((f) => ({ ...f, end: e.target.value }))}
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
                    onClick={() => setFilters((f) => ({ ...f, species: toggleValue(f.species, s.id) }))}
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
                      setFilters((f) => ({ ...f, methods: toggleValue(f.methods, m.id as MethodId) }))
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
                      setFilters((f) => ({ ...f, access: toggleValue(f.access, a.id as AccessId) }))
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
              onChange={(e) => setFilters((f) => ({ ...f, region: e.target.value }))}
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
              onChange={(e) => setFilters((f) => ({ ...f, county: e.target.value }))}
            >
              <option value="">All counties</option>
              {(meta?.counties ?? []).map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>

          <button
            type="button"
            className="text-sm text-moss underline"
            onClick={() => {
              setFilters(EMPTY_FILTERS);
              setSelectedId(null);
            }}
          >
            Clear filters
          </button>

          <p className="mt-4 text-xs leading-relaxed text-muted">{meta?.disclaimer}</p>
        </aside>

        <main className="relative order-1 min-h-[46vh] flex-1 md:order-2">
          {error ? (
            <p className="p-6 text-red-800">{error}</p>
          ) : (
            <HuntMap
              matchingIds={matchIds}
              selectedId={selectedId}
              regionFilter={filters.region}
              satellite={satellite}
              onSelectUnit={setSelectedId}
              onSelectRegion={(region) => {
                setFilters((f) => ({ ...f, region: f.region === region ? "" : region }));
              }}
            />
          )}
          <div className="absolute right-3 top-14 z-10 flex flex-col gap-2">
            <button
              type="button"
              className="rounded-md bg-white/90 px-2 py-1 text-xs shadow"
              onClick={() => setSatellite((s) => !s)}
            >
              {satellite ? "Map" : "Satellite"}
            </button>
          </div>
        </main>

        {selected && (
          <aside className="scrollbar-thin order-3 max-h-[40vh] w-full shrink-0 overflow-y-auto border-t border-black/10 bg-white p-4 md:max-h-none md:w-96 md:border-l md:border-t-0">
            <div className="mb-2 flex items-start justify-between gap-2">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted">
                  Unit {selected.unitIds.join(", ") || selected.id} · {selected.region}
                </p>
                <h2 className="font-serif text-xl font-semibold">{selected.name}</h2>
                <p className="text-sm text-muted">
                  {TYPE_LABEL[selected.type] ?? selected.type}
                  {selected.acres ? ` · ${Math.round(selected.acres).toLocaleString()} acres` : ""}
                  {selected.counties.length ? ` · ${selected.counties.join(", ")} County` : ""}
                </p>
              </div>
              <button type="button" className="text-muted" onClick={() => setSelectedId(null)} aria-label="Close">
                ✕
              </button>
            </div>

            {selected.complexes.length > 0 && (
              <p className="mb-2 text-sm">Includes: {selected.complexes.join(", ")}</p>
            )}

            <div className="mb-3 flex flex-wrap gap-2 text-sm">
              {selected.pdfUrl && (
                <a className="text-moss underline" href={selected.pdfUrl} target="_blank" rel="noreferrer">
                  Official unit PDF
                </a>
              )}
              {selected.aerialPdfUrl && (
                <a className="text-moss underline" href={selected.aerialPdfUrl} target="_blank" rel="noreferrer">
                  Aerial map
                </a>
              )}
              <a
                className="text-moss underline"
                href={
                  selectedCountyPages[0]?.url ||
                  "https://tpwd.texas.gov/regulations/outdoor-annual/hunting/seasons-by-county"
                }
                target="_blank"
                rel="noreferrer"
              >
                Outdoor Annual county
              </a>
              {selected.epostcardUrl && (
                <a className="text-moss underline" href={selected.epostcardUrl} target="_blank" rel="noreferrer">
                  E-Postcard hunts
                </a>
              )}
            </div>

            {selected.legalGameTags.length > 0 && (
              <div className="mb-3">
                <h3 className="text-sm font-semibold">Legal game (APH search)</h3>
                <ul className="mt-1 flex flex-wrap gap-1">
                  {selected.legalGameTags.map((tag) => (
                    <li key={tag} className="rounded bg-sand px-2 py-0.5 text-xs">
                      {tag}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {selected.legalGameText && (
              <p className="mb-3 text-sm leading-relaxed text-muted">{selected.legalGameText}</p>
            )}

            {selectedCountyPages.length > 0 && (
              <div className="mb-4">
                <h3 className="text-sm font-semibold">County seasons (Outdoor Annual)</h3>
                <p className="mb-2 text-xs text-muted">
                  Public-land hunts follow these county dates unless the unit Legal Game box says otherwise.
                  A species is only legal on this unit if it is listed in Legal game above.
                </p>
                {selectedCountyPages.map((page) => (
                  <div key={page.county} className="mb-3">
                    <a className="text-sm font-semibold text-moss underline" href={page.url} target="_blank" rel="noreferrer">
                      {page.county} County
                    </a>
                    <ul className="mt-1 space-y-2">
                      {page.animals.map((animal) => (
                        <li key={`${page.county}-${animal.label}`} className="rounded bg-sand px-2 py-1.5 text-sm">
                          <div className="font-medium">
                            {animal.label}
                            {animal.zone ? <span className="font-normal text-muted"> · {animal.zone}</span> : null}
                          </div>
                          {animal.bagLimit ? <p className="text-xs text-muted">{animal.bagLimit}</p> : null}
                          <ul className="mt-1 space-y-0.5 text-xs">
                            {animal.seasons.map((season, i) => (
                              <li key={`${season.title}-${i}`}>
                                {season.title}: {season.windows.map((w) => formatRange(w.start, w.end)).join("; ")}
                              </li>
                            ))}
                          </ul>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}

            <h3 className="text-sm font-semibold">Seasons & methods on this unit</h3>
            <p className="mb-2 text-xs text-muted">
              Dates are county/zone defaults unless a unit PDF says otherwise. Confirm before hunting.
            </p>
            {groupedOpps.length === 0 ? (
              <p className="text-sm text-muted">No opportunities match the current filters.</p>
            ) : (
              groupedOpps.map(([species, rows]) => (
                <div key={species} className="mb-3 border-b border-black/5 pb-2">
                  <h4 className="text-sm font-semibold">{rows[0].speciesLabel}</h4>
                  <ul className="mt-1 space-y-1 text-sm">
                    {rows.map((row) => (
                      <li key={row.id}>
                        <span className="font-medium">{METHOD_LABEL[row.methods[0]] ?? row.methods[0]}</span>
                        {" · "}
                        {ACCESS_LABEL[row.access] ?? row.access}
                        {" · "}
                        {formatRange(row.start, row.end)}
                        <span className="text-xs text-muted">
                          {" "}
                          (
                          {row.dateSource === "unit_pdf"
                            ? "unit PDF"
                            : row.dateSource === "county"
                              ? `${row.county || "county"} Outdoor Annual`
                              : "region default"}
                          )
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))
            )}
          </aside>
        )}
      </div>
    </div>
  );
}
