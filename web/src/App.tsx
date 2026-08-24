import { useEffect, useMemo, useState } from "react";
import HuntMap from "./HuntMap";
import HuntReport from "./HuntReport";
import DrawnReport from "./DrawnReport";
import ExternalLink from "./ExternalLink";
import FilterPanel, { DRAWN_PRESETS, PRESETS } from "./FilterPanel";
import AccountBar from "./auth/AccountBar";
import AuthModal from "./auth/AuthModal";
import BetaSwitch from "./auth/BetaSwitch";
import { useAuth } from "./auth/AuthContext";
import FavoriteButton from "./auth/FavoriteButton";
import FavoritesView from "./FavoritesView";
import UsersView from "./UsersView";
import type { CountyHunting, DrawnHunt, DrawnMeta, Filters, Meta, Opportunity, Unit } from "./types";
import {
  ACCESS_LABEL,
  METHOD_LABEL,
  TYPE_LABEL,
  drawnRegionMatchCounts,
  drawnSpeciesLegend,
  filterHeadline,
  formatRange,
  matchingDrawnHuntIds,
  matchingUnitIds,
  regionMatchCounts,
  unitOpportunities,
} from "./filters";
import { safeExternalUrl } from "./urls";
import { loadDrawnCatalog } from "./loadDrawn";

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

type View = "map" | "report" | "saved" | "users";
type Dataset = "public" | "drawn";

function feeText(hunt: DrawnHunt): string {
  const parts: string[] = [];
  if (hunt.feeAdult != null) parts.push(`$${hunt.feeAdult.toFixed(0)} adult`);
  if (hunt.feeYouth != null) parts.push(`$${hunt.feeYouth.toFixed(0)} youth`);
  return parts.join(" · ");
}

export default function App() {
  const { isAdmin, betaEnabled } = useAuth();
  const [units, setUnits] = useState<Unit[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [counties, setCounties] = useState<Record<string, CountyHunting>>({});
  const [drawnHunts, setDrawnHunts] = useState<DrawnHunt[]>([]);
  const [drawnMeta, setDrawnMeta] = useState<DrawnMeta | null>(null);
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDrawnId, setSelectedDrawnId] = useState<string | null>(null);
  const [satellite, setSatellite] = useState(false);
  const [view, setView] = useState<View>("map");
  const [dataset, setDataset] = useState<Dataset>("public");
  const [error, setError] = useState<string | null>(null);

  const showDrawn = Boolean(betaEnabled && dataset === "drawn");

  useEffect(() => {
    if (!isAdmin && view === "users") setView("map");
  }, [isAdmin, view]);

  useEffect(() => {
    if (betaEnabled) {
      setDataset("drawn");
      setFilters(EMPTY_FILTERS);
      setSelectedId(null);
      setSelectedDrawnId(null);
    } else {
      setDataset("public");
      setSelectedDrawnId(null);
    }
  }, [betaEnabled]);

  useEffect(() => {
    Promise.all([
      fetch("data/units.json").then((r) => {
        if (!r.ok) throw new Error("units");
        return r.json();
      }),
      fetch("data/opportunities.json").then((r) => {
        if (!r.ok) throw new Error("opportunities");
        return r.json();
      }),
      fetch("data/meta.json").then((r) => {
        if (!r.ok) throw new Error("meta");
        return r.json();
      }),
      fetch("data/counties.json").then((r) => {
        if (!r.ok) throw new Error("counties");
        return r.json();
      }),
    ])
      .then(([u, o, m, c]) => {
        setUnits(u);
        setOpportunities(o);
        setMeta(m);
        setCounties(c);
      })
      .catch(() => setError("Could not load hunt data."));
  }, []);

  useEffect(() => {
    if (!betaEnabled || drawnHunts.length) return;
    let cancelled = false;
    void loadDrawnCatalog()
      .then(({ hunts, meta: dm }) => {
        if (cancelled) return;
        setDrawnHunts(hunts);
        setDrawnMeta(dm);
        setError((prev) => (prev === "Could not load drawn hunt data." ? null : prev));
      })
      .catch(() => {
        if (!cancelled) setError("Could not load drawn hunt data.");
      });
    return () => {
      cancelled = true;
    };
  }, [betaEnabled, drawnHunts.length]);

  const matchIds = useMemo(
    () => matchingUnitIds(units, opportunities, filters),
    [units, opportunities, filters],
  );
  const drawnMatchIds = useMemo(() => matchingDrawnHuntIds(drawnHunts, filters), [drawnHunts, filters]);
  const regionCounts = useMemo(() => regionMatchCounts(units, matchIds), [units, matchIds]);
  const drawnRegionCounts = useMemo(
    () => drawnRegionMatchCounts(drawnHunts, drawnMatchIds),
    [drawnHunts, drawnMatchIds],
  );
  const drawnLegend = useMemo(
    () => drawnSpeciesLegend(drawnHunts, drawnMatchIds),
    [drawnHunts, drawnMatchIds],
  );
  const selected = units.find((u) => u.id === selectedId) ?? null;
  const selectedDrawn = drawnHunts.find((h) => h.id === selectedDrawnId) ?? null;
  const selectedCountyPages = useMemo(() => {
    if (!selected?.countySlugs) return [];
    return selected.countySlugs.map((slug) => counties[slug]).filter(Boolean);
  }, [selected, counties]);
  const selectedOpps = selected ? unitOpportunities(selected.id, opportunities, filters) : [];
  const speciesLabels = useMemo(
    () => Object.fromEntries((meta?.species ?? []).map((s) => [s.id, s.label])),
    [meta],
  );
  const drawnSpeciesLabels = useMemo(
    () => Object.fromEntries((drawnMeta?.species ?? []).map((s) => [s.id, s.label])),
    [drawnMeta],
  );
  const headline = showDrawn
    ? filterHeadline(filters, drawnSpeciesLabels, "All drawn hunts")
    : filterHeadline(filters, speciesLabels);

  const groupedOpps = useMemo(() => {
    const map = new Map<string, Opportunity[]>();
    for (const opp of selectedOpps) {
      const list = map.get(opp.species) ?? [];
      list.push(opp);
      map.set(opp.species, list);
    }
    return [...map.entries()];
  }, [selectedOpps]);

  const openUnitOnMap = (id: string) => {
    setSelectedDrawnId(null);
    setSelectedId(id);
    setView("map");
  };

  const openDrawnOnMap = (id: string) => {
    setSelectedId(null);
    setSelectedDrawnId(id);
    setView("map");
  };

  const switchDataset = (next: Dataset) => {
    setDataset(next);
    setFilters(EMPTY_FILTERS);
    setSelectedId(null);
    setSelectedDrawnId(null);
  };

  const countLabel = showDrawn
    ? `${drawnMatchIds.size} of ${drawnHunts.length} hunts`
    : `${matchIds.size} of ${units.length} areas`;

  return (
    <div className="flex h-full min-h-0 flex-col bg-sand text-ink">
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-black/10 bg-pine px-4 py-3 text-sand">
        <div>
          <h1 className="font-serif text-xl font-semibold tracking-tight md:text-2xl">
            Texas Public Land Hunting
          </h1>
          <p className="text-sm text-sand/80">
            {showDrawn
              ? drawnMeta
                ? `${drawnMeta.seasonYear} drawn hunts`
                : "Loading drawn hunts…"
              : meta
                ? `${meta.seasonYear} APH / walk-in units`
                : "Loading…"}{" "}
            · map and hunt report · unofficial planning aid
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2 text-sm">
          <div className="flex rounded-full bg-black/20 p-0.5">
            <button
              type="button"
              className={`rounded-full px-3 py-1 ${view === "map" ? "bg-gold text-pine" : "text-sand/80"}`}
              onClick={() => setView("map")}
            >
              Map
            </button>
            <button
              type="button"
              className={`rounded-full px-3 py-1 ${view === "report" ? "bg-gold text-pine" : "text-sand/80"}`}
              onClick={() => setView("report")}
            >
              Report
            </button>
            <button
              type="button"
              className={`rounded-full px-3 py-1 ${view === "saved" ? "bg-gold text-pine" : "text-sand/80"}`}
              onClick={() => setView("saved")}
            >
              Saved
            </button>
            {isAdmin ? (
              <button
                type="button"
                className={`rounded-full px-3 py-1 ${view === "users" ? "bg-gold text-pine" : "text-sand/80"}`}
                onClick={() => setView("users")}
              >
                Users
              </button>
            ) : null}
          </div>
          {betaEnabled ? (
            <div className="flex rounded-full bg-black/20 p-0.5">
              <button
                type="button"
                className={`rounded-full px-3 py-1 ${dataset === "public" ? "bg-gold text-pine" : "text-sand/80"}`}
                onClick={() => switchDataset("public")}
              >
                Public land
              </button>
              <button
                type="button"
                className={`rounded-full px-3 py-1 ${dataset === "drawn" ? "bg-gold text-pine" : "text-sand/80"}`}
                onClick={() => switchDataset("drawn")}
              >
                Drawn hunts
              </button>
            </div>
          ) : null}
          <span className="rounded-full bg-gold/20 px-3 py-1 text-gold">{countLabel}</span>
          <ExternalLink
            className="rounded-full border border-sand/30 px-3 py-1 hover:bg-white/10"
            href={
              showDrawn
                ? "https://tpwd.texas.gov/huntwild/hunt/public/public_hunt_drawing/"
                : "https://tpwd.texas.gov/huntwild/hunt/public/annual_public_hunting/"
            }
          >
            {showDrawn ? "TPWD drawing" : "TPWD APH"}
          </ExternalLink>
          <AccountBar savedActive={view === "saved"} onOpenSaved={() => setView("saved")} />
          <BetaSwitch />
        </div>
      </header>

      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        {view !== "users" ? (
          <aside className="scrollbar-thin order-2 max-h-[42vh] shrink-0 overflow-y-auto border-t border-black/10 bg-sand p-4 md:order-1 md:max-h-none md:w-80 md:border-r md:border-t-0">
            <FilterPanel
              filters={filters}
              meta={showDrawn ? drawnMeta : meta}
              presets={showDrawn ? DRAWN_PRESETS : PRESETS}
              searchPlaceholder={
                showDrawn ? "Area, animal, county, or hunt category" : "Unit name, number, county, booklet page"
              }
              onChange={(next) => {
                setFilters(next);
                setSelectedId(null);
                setSelectedDrawnId(null);
              }}
            />
            <p className="mt-4 text-xs leading-relaxed text-muted">
              {showDrawn ? drawnMeta?.disclaimer : meta?.disclaimer}
            </p>
          </aside>
        ) : null}

        <main className="relative order-1 min-h-[46vh] min-w-0 flex-1 md:order-2">
          {error === "Could not load hunt data." ? (
            <p className="p-6 text-red-800">{error}</p>
          ) : (
            <>
              {error === "Could not load drawn hunt data." && showDrawn ? (
                <p className="absolute left-3 right-3 top-3 z-20 rounded-md bg-white/95 p-3 text-sm text-red-800 shadow">
                  {error}
                </p>
              ) : null}
              <div className={`absolute inset-0 ${view === "map" ? "z-10" : "invisible pointer-events-none"}`}>
                <HuntMap
                  matchingIds={matchIds}
                  selectedId={selectedId}
                  regionFilter={filters.region}
                  satellite={satellite}
                  active={view === "map"}
                  showDrawn={showDrawn}
                  drawnHunts={drawnHunts}
                  matchingDrawnIds={drawnMatchIds}
                  selectedDrawnId={selectedDrawnId}
                  onSelectUnit={(id) => {
                    setSelectedDrawnId(null);
                    setSelectedId(id);
                  }}
                  onSelectDrawn={(id) => {
                    setSelectedId(null);
                    setSelectedDrawnId(id);
                  }}
                  onSelectRegion={(region) => {
                    setSelectedId(null);
                    setSelectedDrawnId(null);
                    setFilters((f) => ({ ...f, region: f.region === region ? "" : region }));
                  }}
                />
                <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex flex-wrap items-start justify-between gap-2 p-3">
                  <div className="pointer-events-auto max-w-xl rounded-md bg-white/90 px-3 py-2 text-sm shadow">
                    <div className="font-semibold">{headline}</div>
                    <div className="text-xs text-muted">
                      {showDrawn
                        ? drawnMatchIds.size === 0
                          ? "No drawn hunts match these filters"
                          : drawnMatchIds.size === drawnHunts.length
                            ? "Click a color-coded pin for hunt details"
                            : `Showing ${drawnMatchIds.size} matching hunt${drawnMatchIds.size === 1 ? "" : "s"}`
                        : matchIds.size === 0
                          ? "No public hunt units match these filters"
                          : matchIds.size === units.length
                            ? "Click a colored region or a hunt unit"
                            : `Showing ${matchIds.size} matching unit${matchIds.size === 1 ? "" : "s"}`}
                    </div>
                  </div>
                  <button
                    type="button"
                    className="pointer-events-auto rounded-md bg-white/90 px-2 py-1 text-xs shadow"
                    onClick={() => setSatellite((s) => !s)}
                  >
                    {satellite ? "Map" : "Satellite"}
                  </button>
                </div>
                {showDrawn && drawnLegend.length > 0 ? (
                  <div className="pointer-events-none absolute top-24 left-3 z-10 max-w-[11rem] rounded-md bg-white/90 p-2 text-xs shadow">
                    <div className="mb-1 font-semibold">Animal</div>
                    <ul className="space-y-1">
                      {drawnLegend.map((row) => (
                        <li key={row.id} className="flex items-center gap-1.5">
                          <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: row.color }} />
                          {row.label}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <div className="pointer-events-none absolute inset-x-0 bottom-8 z-10 flex flex-wrap justify-center gap-1 px-3">
                  {(showDrawn ? drawnRegionCounts : regionCounts).map((row) => (
                    <button
                      key={row.region}
                      type="button"
                      className={`pointer-events-auto rounded-full px-2 py-1 text-xs shadow ${
                        filters.region === row.region ? "bg-moss text-white" : "bg-white/90"
                      }`}
                      onClick={() => {
                        setSelectedId(null);
                        setSelectedDrawnId(null);
                        setFilters((f) => ({ ...f, region: f.region === row.region ? "" : row.region }));
                      }}
                    >
                      {row.region} · {row.count}
                    </button>
                  ))}
                </div>
              </div>
              <div className={`absolute inset-0 ${view === "saved" ? "z-10" : "hidden"}`}>
                <FavoritesView units={units} onSelectUnit={openUnitOnMap} />
              </div>
              <div className={`absolute inset-0 ${view === "users" ? "z-10" : "hidden"}`}>
                {isAdmin ? <UsersView /> : null}
              </div>
              <div className={`absolute inset-0 ${view === "report" ? "z-10" : "hidden"}`}>
                {showDrawn ? (
                  <DrawnReport
                    hunts={drawnHunts}
                    filters={filters}
                    speciesLabels={drawnSpeciesLabels}
                    onSelectHunt={openDrawnOnMap}
                    onSelectRegion={(region) => {
                      setFilters((f) => ({ ...f, region }));
                      setSelectedDrawnId(null);
                      setView("map");
                    }}
                  />
                ) : (
                  <HuntReport
                    units={units}
                    opportunities={opportunities}
                    filters={filters}
                    speciesLabels={speciesLabels}
                    onSelectUnit={openUnitOnMap}
                    onSelectRegion={(region) => {
                      setFilters((f) => ({ ...f, region }));
                      setSelectedId(null);
                      setView("map");
                    }}
                  />
                )}
              </div>
            </>
          )}
        </main>

        {view === "map" && showDrawn && selectedDrawn ? (
          <aside className="scrollbar-thin order-3 max-h-[40vh] w-full shrink-0 overflow-y-auto border-t border-black/10 bg-white p-4 md:max-h-none md:w-96 md:border-l md:border-t-0">
            <div className="mb-2 flex items-start justify-between gap-2">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted">
                  {selectedDrawn.areaCode} · {ACCESS_LABEL[selectedDrawn.access] ?? selectedDrawn.access}
                  {selectedDrawn.region ? ` · ${selectedDrawn.region}` : ""}
                </p>
                <h2 className="font-serif text-xl font-semibold">{selectedDrawn.areaName}</h2>
                <p className="text-sm text-muted">
                  <span
                    className="mr-1 inline-block h-2.5 w-2.5 rounded-full align-middle"
                    style={{ background: selectedDrawn.color }}
                  />
                  {selectedDrawn.speciesLabel || selectedDrawn.categoryName}
                  {selectedDrawn.counties.length ? ` · ${selectedDrawn.counties.join(", ")} County` : ""}
                </p>
              </div>
              <button type="button" className="text-muted" onClick={() => setSelectedDrawnId(null)} aria-label="Close">
                ✕
              </button>
            </div>

            <p className="mb-3 text-sm">{selectedDrawn.categoryName}</p>

            <dl className="mb-3 space-y-1.5 text-sm">
              <div>
                <dt className="text-xs uppercase tracking-wide text-muted">Application deadline</dt>
                <dd>
                  {selectedDrawn.applicationDeadline
                    ? formatRange(selectedDrawn.applicationDeadline, selectedDrawn.applicationDeadline)
                    : "See catalog"}
                </dd>
              </div>
              <div>
                <dt className="text-xs uppercase tracking-wide text-muted">Hunt dates</dt>
                <dd>
                  {selectedDrawn.huntDates.length
                    ? selectedDrawn.huntDates.map((d) => (
                        <div key={`${d.start}-${d.end}`}>{formatRange(d.start, d.end)}</div>
                      ))
                    : "See catalog"}
                </dd>
              </div>
              {selectedDrawn.bagLimit ? (
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted">Bag limit</dt>
                  <dd>{selectedDrawn.bagLimit}</dd>
                </div>
              ) : null}
              {selectedDrawn.meansAllowed.length ? (
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted">Weapons / means allowed</dt>
                  <dd>{selectedDrawn.meansAllowed.join(", ")}</dd>
                </div>
              ) : (
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted">Method</dt>
                  <dd>{selectedDrawn.methods.map((m) => METHOD_LABEL[m] ?? m).join(", ")}</dd>
                </div>
              )}
              {selectedDrawn.meansNotAllowed.length ? (
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted">Means not allowed</dt>
                  <dd>{selectedDrawn.meansNotAllowed.join(", ")}</dd>
                </div>
              ) : null}
              {selectedDrawn.huntMethod ? (
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted">Hunt method</dt>
                  <dd>{selectedDrawn.huntMethod}</dd>
                </div>
              ) : null}
              {selectedDrawn.baiting ? (
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted">Baiting</dt>
                  <dd>{selectedDrawn.baiting}</dd>
                </div>
              ) : null}
              {selectedDrawn.restrictions ? (
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted">Restrictions</dt>
                  <dd>{selectedDrawn.restrictions}</dd>
                </div>
              ) : null}
              {selectedDrawn.permitsAvailable != null ? (
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted">Permits available</dt>
                  <dd>{selectedDrawn.permitsAvailable}</dd>
                </div>
              ) : null}
              {feeText(selectedDrawn) ? (
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted">Fee</dt>
                  <dd>{feeText(selectedDrawn)}</dd>
                </div>
              ) : null}
              {selectedDrawn.peoplePerApplication ? (
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted">Application</dt>
                  <dd>{selectedDrawn.peoplePerApplication}</dd>
                </div>
              ) : null}
              {selectedDrawn.ageRequirements ? (
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted">Age</dt>
                  <dd>{selectedDrawn.ageRequirements}</dd>
                </div>
              ) : null}
              {selectedDrawn.lastYearApplications != null || selectedDrawn.lastYearSuccess ? (
                <div>
                  <dt className="text-xs uppercase tracking-wide text-muted">Last year</dt>
                  <dd>
                    {selectedDrawn.lastYearApplications != null
                      ? `${selectedDrawn.lastYearApplications.toLocaleString()} applications`
                      : ""}
                    {selectedDrawn.lastYearPermits != null
                      ? ` · ${selectedDrawn.lastYearPermits.toLocaleString()} permits`
                      : ""}
                    {selectedDrawn.lastYearSuccess ? ` · ${selectedDrawn.lastYearSuccess} success` : ""}
                  </dd>
                </div>
              ) : null}
            </dl>

            <div className="mb-3 flex flex-wrap gap-2 text-sm">
              {safeExternalUrl(selectedDrawn.brochureUrl) ? (
                <ExternalLink className="text-moss underline" href={selectedDrawn.brochureUrl}>
                  Hunt brochure
                </ExternalLink>
              ) : null}
              {safeExternalUrl(selectedDrawn.applyUrl) ? (
                <ExternalLink className="text-moss underline" href={selectedDrawn.applyUrl}>
                  Apply
                </ExternalLink>
              ) : null}
              <ExternalLink
                className="text-moss underline"
                href="https://tpwd.texas.gov/huntwild/hunt/public/public_hunt_drawing/"
              >
                Drawn hunt catalog
              </ExternalLink>
            </div>

            {selectedDrawn.notes.length > 0 ? (
              <ul className="space-y-1 text-sm text-muted">
                {selectedDrawn.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            ) : null}
          </aside>
        ) : null}

        {view === "map" && !showDrawn && selected && (
          <aside className="scrollbar-thin order-3 max-h-[40vh] w-full shrink-0 overflow-y-auto border-t border-black/10 bg-white p-4 md:max-h-none md:w-96 md:border-l md:border-t-0">
            <div className="mb-2 flex items-start justify-between gap-2">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted">
                  Unit {selected.unitIds.join(", ") || selected.id} · {selected.region}
                  {selected.bookletPage ? ` · booklet p. ${selected.bookletPage}` : ""}
                </p>
                <h2 className="font-serif text-xl font-semibold">{selected.name}</h2>
                <p className="text-sm text-muted">
                  {TYPE_LABEL[selected.type] ?? selected.type}
                  {selected.acres ? ` · ${Math.round(selected.acres).toLocaleString()} acres` : ""}
                  {selected.counties.length ? ` · ${selected.counties.join(", ")} County` : ""}
                </p>
              </div>
              <div className="flex shrink-0 items-start gap-1">
                <FavoriteButton unitId={selected.id} />
                <button type="button" className="text-muted" onClick={() => setSelectedId(null)} aria-label="Close">
                  ✕
                </button>
              </div>
            </div>

            {selected.complexes.length > 0 && (
              <p className="mb-2 text-sm">Includes: {selected.complexes.join(", ")}</p>
            )}

            <div className="mb-3 flex flex-wrap gap-2 text-sm">
              <ExternalLink className="text-moss underline" href={selected.pdfUrl}>
                Official unit PDF
              </ExternalLink>
              <ExternalLink className="text-moss underline" href={selected.aerialPdfUrl}>
                Aerial map
              </ExternalLink>
              <ExternalLink className="text-moss underline" href={selected.bookletUrl}>
                {selected.bookletPage ? `Map booklet p. ${selected.bookletPage}` : "Map booklet"}
              </ExternalLink>
              <ExternalLink
                className="text-moss underline"
                href={
                  selectedCountyPages[0]?.url ||
                  "https://tpwd.texas.gov/regulations/outdoor-annual/hunting/seasons-by-county"
                }
              >
                Outdoor Annual county
              </ExternalLink>
              <ExternalLink className="text-moss underline" href={selected.epostcardUrl}>
                E-Postcard hunts
              </ExternalLink>
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
                    <ExternalLink className="text-sm font-semibold text-moss underline" href={page.url}>
                      {page.county} County
                    </ExternalLink>
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
      <AuthModal />
    </div>
  );
}
