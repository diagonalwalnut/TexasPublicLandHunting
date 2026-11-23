import { useEffect, useMemo, useState } from "react";
import ExternalLink from "../../ExternalLink";
import InSeasonPage from "../../shared/InSeasonPage";
import LicenseGuideView from "../../shared/LicenseGuideView";
import type { LicenseGuide, RegulationGuide } from "../../shared/licenseTypes";
import type { InSeasonSourceRow } from "../../shared/inSeason";
import type { StateInfo } from "../../states/catalog";
import type { Opportunity, Unit } from "../../types";
import { METHOD_LABEL } from "../../filters";
import UnitGridMap from "../unitGrid/UnitGridMap";

type Pane = "map" | "report" | "in-season" | "licenses" | "rules";

const ACCESS_LABEL: Record<string, string> = {
  wma_permit: "WMA / public-land permit",
  lottery: "Lottery / drawn hunt",
  controlled_draw: "Controlled draw",
  corps_permit: "Corps permit",
  aph_walk_in: "Walk-in public hunting",
  e_postcard: "E-postcard",
  regular_permit: "Daily / regular permit",
  drawn: "Drawn hunt",
};

const BOUNDS: Record<string, [[number, number], [number, number]]> = {
  la: [
    [-94.2, 28.8],
    [-88.7, 33.1],
  ],
  ar: [
    [-94.7, 33.0],
    [-89.6, 36.6],
  ],
  ok: [
    [-103.1, 33.5],
    [-94.4, 37.1],
  ],
};

type ZonePage = {
  id: string;
  name: string;
  label?: string;
  animals?: {
    species: string;
    label: string;
    seasons: { methods: string[]; access?: string; windows: { start: string; end: string }[] }[];
  }[];
};

export default function PublicLandExplorer({ state }: { state: StateInfo }) {
  const [units, setUnits] = useState<Unit[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [meta, setMeta] = useState<{ seasonYear?: string; disclaimer?: string; species?: { id: string; label: string }[] } | null>(
    null,
  );
  const [licenses, setLicenses] = useState<LicenseGuide | null>(null);
  const [rules, setRules] = useState<RegulationGuide | null>(null);
  const [geojson, setGeojson] = useState<GeoJSON.FeatureCollection | null>(null);
  const [zones, setZones] = useState<ZonePage[]>([]);
  const [pane, setPane] = useState<Pane>("map");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [species, setSpecies] = useState("");
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
    Promise.all([
      load(`${prefix}/units.json`),
      load(`${prefix}/opportunities.json`),
      load(`${prefix}/meta.json`),
      load(`${prefix}/licenses.json`),
      load(`${prefix}/regulations.json`),
      load(`${prefix}/units.geojson`),
      load(`${prefix}/zones.json`).catch(() => []),
    ])
      .then(([u, o, m, lic, reg, gj, z]) => {
        setUnits(u);
        setOpportunities(o);
        setMeta(m);
        setLicenses(lic);
        setRules(reg);
        setGeojson(gj);
        setZones(Array.isArray(z) ? z : Object.values(z));
      })
      .catch(() => setError(`Could not load ${state.name} public hunting data.`));
  }, [state]);

  const filteredUnits = useMemo(() => {
    const q = query.trim().toLowerCase();
    return units.filter((unit) => {
      if (species && !unit.species.includes(species)) return false;
      if (!q) return true;
      return `${unit.name} ${unit.counties.join(" ")} ${unit.region}`.toLowerCase().includes(q);
    });
  }, [units, query, species]);

  const matchIds = useMemo(() => new Set(filteredUnits.map((unit) => unit.id)), [filteredUnits]);
  const selected = units.find((unit) => unit.id === selectedId) ?? null;
  const selectedOpps = opportunities.filter((opp) => opp.unitId === selectedId);

  const inSeasonRows: InSeasonSourceRow[] = useMemo(() => {
    const fromOpps = opportunities.map((opp) => {
      const unit = units.find((item) => item.id === opp.unitId);
      return {
        species: opp.species,
        speciesLabel: opp.speciesLabel,
        methods: opp.methods,
        accessLabel: ACCESS_LABEL[opp.access] ?? opp.access,
        start: opp.start,
        end: opp.end,
        placeId: opp.unitId,
        placeLabel: unit?.name || opp.county || opp.unitId,
      };
    });
    const fromZones = zones.flatMap((zone) =>
      (zone.animals ?? []).flatMap((animal) =>
        animal.seasons.flatMap((season) =>
          season.windows.map((window) => ({
            species: animal.species,
            speciesLabel: animal.label,
            methods: season.methods,
            accessLabel: ACCESS_LABEL[season.access || ""] || "Zone season",
            start: window.start,
            end: window.end,
            placeId: zone.id,
            placeLabel: zone.label || zone.name,
          })),
        ),
      ),
    );
    return [...fromZones, ...fromOpps];
  }, [opportunities, units, zones]);

  return (
    <div className="relative z-10 flex min-h-0 flex-1 flex-col bg-sand text-ink">
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-black/10 bg-white/40 px-4 py-2 text-sm">
        {(["map", "report", "in-season", "licenses", "rules"] as Pane[]).map((item) => (
          <button
            key={item}
            type="button"
            className={`rounded-full px-3 py-1 capitalize ${pane === item ? "bg-moss text-white" : "text-pine"}`}
            onClick={() => setPane(item)}
          >
            {item === "in-season" ? "In Season" : item === "report" ? "Report" : item}
          </button>
        ))}
        <span className="rounded-full bg-gold/20 px-3 py-1 text-pine">
          {filteredUnits.length} of {units.length} areas
        </span>
        <ExternalLink className="rounded-full border border-pine/20 px-3 py-1 text-moss" href={state.agencyUrl}>
          {state.agencyLabel}
        </ExternalLink>
      </div>

      {error ? (
        <p className="p-6 text-red-800">{error}</p>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          <aside className="scrollbar-thin order-2 max-h-[40vh] w-full shrink-0 overflow-y-auto border-t border-black/10 p-4 md:order-1 md:max-h-none md:w-80 md:border-r md:border-t-0">
            <label className="mb-3 block text-sm">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted">Search</span>
              <input
                className="w-full rounded border border-black/10 bg-white px-2 py-1"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Area or county"
              />
            </label>
            <label className="mb-3 block text-sm">
              <span className="mb-1 block text-xs font-semibold uppercase tracking-wide text-muted">Animal</span>
              <select
                className="w-full rounded border border-black/10 bg-white px-2 py-1"
                value={species}
                onChange={(event) => setSpecies(event.target.value)}
              >
                <option value="">All</option>
                {(meta?.species ?? []).map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.label}
                  </option>
                ))}
              </select>
            </label>
            <p className="text-xs leading-relaxed text-muted">{meta?.disclaimer}</p>
          </aside>

          <div className="relative order-1 min-h-[46vh] min-w-0 flex-1 md:order-2">
            <div className={pane === "map" ? "absolute inset-0" : "hidden"}>
              <UnitGridMap
                geojson={geojson}
                matchingIds={matchIds}
                selectedId={selectedId}
                satellite={satellite}
                active={pane === "map"}
                bounds={BOUNDS[state.id] ?? BOUNDS.la}
                onSelect={setSelectedId}
              />
              <button
                type="button"
                className="absolute right-3 top-14 z-10 rounded-md bg-white/90 px-2 py-1 text-xs shadow"
                onClick={() => setSatellite((value) => !value)}
              >
                {satellite ? "Map" : "Satellite"}
              </button>
            </div>
            {pane === "report" && (
              <div className="scrollbar-thin absolute inset-0 overflow-y-auto p-4">
                <h3 className="font-serif text-xl font-semibold text-pine">Public hunting areas</h3>
                <ul className="mt-3 space-y-2">
                  {filteredUnits.map((unit) => (
                    <li key={unit.id}>
                      <button
                        type="button"
                        className="w-full rounded-md bg-white px-3 py-2 text-left text-sm shadow-sm"
                        onClick={() => {
                          setSelectedId(unit.id);
                          setPane("map");
                        }}
                      >
                        <div className="font-medium">{unit.name}</div>
                        <div className="text-xs text-muted">
                          {unit.type}
                          {unit.source === "usace" ? " · Corps" : ""}
                          {unit.counties?.length ? ` · ${unit.counties.join(", ")}` : ""}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {pane === "in-season" && (
              <InSeasonPage
                rows={inSeasonRows}
                timezone={state.timezone}
                stateName={state.name}
                methodLabels={METHOD_LABEL}
                speciesLabels={Object.fromEntries((meta?.species ?? []).map((row) => [row.id, row.label]))}
                placeFilterLabel={state.id === "ar" ? "Zone / area" : "Area / parish / county"}
                shared={{
                  species: species ? [species] : [],
                  query,
                  place: selected?.name || "",
                }}
                onSharedChange={(next) => {
                  setSpecies(next.species?.[0] || "");
                  const place = (next.place || "").trim();
                  const matched = place
                    ? units.find((unit) => unit.name === place || unit.id === place)
                    : null;
                  if (matched) {
                    setSelectedId(matched.id);
                    setQuery("");
                  } else if (place) {
                    setQuery(place);
                    setSelectedId(null);
                  } else if (next.place === "") {
                    setQuery(next.query ?? "");
                  } else if (next.query != null) {
                    setQuery(next.query);
                  }
                }}
              />
            )}
            {pane === "licenses" && licenses && <LicenseGuideView guide={licenses} />}
            {pane === "rules" && rules && (
              <div className="scrollbar-thin absolute inset-0 overflow-y-auto p-4 md:p-6">
                <h3 className="font-serif text-2xl font-semibold">{rules.title}</h3>
                <ul className="mt-4 list-disc space-y-2 pl-5 text-sm">
                  {rules.unitRules.map((rule) => (
                    <li key={rule}>{rule}</li>
                  ))}
                </ul>
                <h4 className="mt-6 font-semibold">Restrictions</h4>
                <ul className="mt-2 list-disc space-y-2 pl-5 text-sm">
                  {rules.prohibited.map((rule) => (
                    <li key={rule}>{rule}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {pane === "map" && selected && (
            <aside className="scrollbar-thin order-3 max-h-[36vh] w-full shrink-0 overflow-y-auto border-t border-black/10 bg-white p-4 md:max-h-none md:w-96 md:border-l md:border-t-0">
              <div className="mb-2 flex items-start justify-between gap-2">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted">
                    {selected.type}
                    {selected.source === "usace" ? " · Corps" : ""}
                  </p>
                  <h3 className="font-serif text-xl font-semibold">{selected.name}</h3>
                  {selected.acres ? <p className="text-sm text-muted">{Math.round(selected.acres).toLocaleString()} acres</p> : null}
                </div>
                <button type="button" className="text-muted" onClick={() => setSelectedId(null)}>
                  ✕
                </button>
              </div>
              {selected.permitInfo ? <p className="mb-2 text-sm">{selected.permitInfo}</p> : null}
              {selected.means ? <p className="mb-2 text-sm text-muted">Means: {selected.means}</p> : null}
              <ul className="space-y-2 text-sm">
                {selectedOpps.slice(0, 12).map((opp) => (
                  <li key={opp.id} className="rounded bg-sand px-2 py-1.5">
                    <div className="font-medium">{opp.speciesLabel}</div>
                    <div className="text-xs text-muted">
                      {opp.methods.map((method) => METHOD_LABEL[method] ?? method).join(", ")} ·{" "}
                      {ACCESS_LABEL[opp.access] ?? opp.access}
                    </div>
                    <div className="text-xs">
                      {opp.start} – {opp.end}
                    </div>
                    {(opp.restrictions || []).map((line) => (
                      <div key={line} className="text-xs text-pine">
                        {line}
                      </div>
                    ))}
                  </li>
                ))}
              </ul>
              {(selected.links ?? []).map((link) => (
                <ExternalLink key={link.url} className="mt-2 block text-sm text-moss underline" href={link.url}>
                  {link.label}
                </ExternalLink>
              ))}
            </aside>
          )}
        </div>
      )}
    </div>
  );
}
