import { useEffect, useMemo, useState } from "react";
import HuntMap from "./HuntMap";
import OregonExplorer from "./oregon/OregonExplorer";
import { useAuth } from "./auth/AuthContext";
import HuntReport from "./HuntReport";
import ExternalLink from "./ExternalLink";
import FilterPanel from "./FilterPanel";
import AccountBar from "./auth/AccountBar";
import AuthModal from "./auth/AuthModal";
import FavoriteButton from "./auth/FavoriteButton";
import FavoritesView from "./FavoritesView";
import UsersView from "./UsersView";
import type { CountyAnimal, CountyHunting, CountySeason, Filters, Meta, Opportunity, Unit } from "./types";
import {
  ACCESS_LABEL,
  METHOD_LABEL,
  TYPE_LABEL,
  filterHeadline,
  formatRange,
  matchingUnitIds,
  regionMatchCounts,
  unitOpportunities,
} from "./filters";

const ACCESS_KIND_LABEL: Record<string, string> = {
  entry: "Entry",
  park: "Parking",
  boat_ramp: "Boat ramp",
};

function seasonFitsLake(season: CountySeason, allowed: Set<string>): boolean {
  if (season.access === "youth" || season.access === "youth_adult") return false;
  if (/dusky|veteran|falcon/i.test(season.title)) return false;
  if (season.methods.includes("any_legal") || allowed.has("any_legal")) return true;
  return season.methods.some((method) => allowed.has(method));
}

function CorpsLegalGame({
  unit,
  pages,
  opportunities,
  speciesLabels,
  speciesOrder,
}: {
  unit: Unit;
  pages: CountyHunting[];
  opportunities: Opportunity[];
  speciesLabels: Record<string, string>;
  speciesOrder: string[];
}) {
  const order = new Map(speciesOrder.map((id, index) => [id, index]));
  const speciesIds = [...unit.species].sort(
    (a, b) => (order.get(a) ?? 999) - (order.get(b) ?? 999) || a.localeCompare(b),
  );
  const cards = speciesIds.map((species) => {
    const opps = opportunities.filter((opp) => opp.species === species);
    const allowed = new Set(opps.flatMap((opp) => opp.methods));
    const animals: { page: CountyHunting; animal: CountyAnimal }[] = [];
    for (const page of pages) {
      const animal = page.animals.find((item) => item.species === species);
      if (animal) animals.push({ page, animal });
    }
    const label = animals[0]?.animal.label || speciesLabels[species] || opps[0]?.speciesLabel || species;
    const zone = animals.find((row) => row.animal.zone)?.animal.zone ?? "";
    const bagLimit = animals.find((row) => row.animal.bagLimit)?.animal.bagLimit ?? "";
    const lines: { key: string; text: string }[] = [];
    const severalCounties = animals.length > 1;
    for (const { page, animal } of animals) {
      animal.seasons.forEach((season, index) => {
        if (allowed.size > 0 && !seasonFitsLake(season, allowed)) return;
        const prefix = severalCounties ? `${page.county}: ` : "";
        const dates = season.windows.map((window) => formatRange(window.start, window.end)).join("; ");
        lines.push({ key: `${page.county}-${season.title}-${index}`, text: `${prefix}${season.title}: ${dates}` });
      });
    }
    if (lines.length === 0) {
      for (const opp of opps) {
        const method = METHOD_LABEL[opp.methods[0]] ?? opp.methods[0];
        lines.push({ key: opp.id, text: `${method}: ${formatRange(opp.start, opp.end)}` });
      }
    }
    const notes = [...new Set(opps.map((opp) => opp.notes.trim()).filter(Boolean))];
    return { species, label, zone, bagLimit, lines, notes };
  });

  if (cards.length === 0) return null;
  return (
    <div className="mb-4">
      <h3 className="text-sm font-semibold">Legal game</h3>
      <p className="mb-2 text-xs text-muted">
        These are the species this lake allows. Dates follow the county Outdoor Annual for the methods the Corps permits.
      </p>
      {pages.map((page) => (
        <ExternalLink
          key={page.slug ?? page.county}
          className="mb-1 block text-sm font-semibold text-moss underline"
          href={page.url}
        >
          {page.county} County
        </ExternalLink>
      ))}
      <ul className="mt-1 space-y-2">
        {cards.map((card) => (
          <li key={card.species} className="rounded bg-sand px-2 py-1.5 text-sm">
            <div className="font-medium">
              {card.label}
              {card.zone ? <span className="font-normal text-muted"> · {card.zone}</span> : null}
            </div>
            {card.bagLimit ? <p className="text-xs text-muted">{card.bagLimit}</p> : null}
            {card.notes.map((note) => (
              <p key={note} className="text-xs text-muted">
                {note}
              </p>
            ))}
            {card.lines.length > 0 && (
              <ul className="mt-1 space-y-0.5 text-xs">
                {card.lines.map((line) => (
                  <li key={line.key}>{line.text}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

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

export default function App() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const canUseOregon = isAdmin || (user?.betas ?? []).includes("oregon");
  const [units, setUnits] = useState<Unit[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [counties, setCounties] = useState<Record<string, CountyHunting>>({});
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [satellite, setSatellite] = useState(false);
  const [view, setView] = useState<"map" | "report" | "saved" | "users">("map");
  const [oregonOpen, setOregonOpen] = useState(false);

  useEffect(() => {
    if (!canUseOregon) setOregonOpen(false);
    if (!isAdmin && view === "users") setView("map");
  }, [canUseOregon, isAdmin, view]);
  const [error, setError] = useState<string | null>(null);

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

  const matchIds = useMemo(
    () => matchingUnitIds(units, opportunities, filters),
    [units, opportunities, filters],
  );
  const regionCounts = useMemo(() => regionMatchCounts(units, matchIds), [units, matchIds]);
  const selected = units.find((u) => u.id === selectedId) ?? null;
  const selectedCountyPages = useMemo(() => {
    if (!selected?.countySlugs) return [];
    return selected.countySlugs.map((slug) => counties[slug]).filter(Boolean);
  }, [selected, counties]);
  const selectedOpps = selected ? unitOpportunities(selected.id, opportunities, filters) : [];
  const isCorps = selected?.source === "usace";
  const speciesLabels = useMemo(
    () => Object.fromEntries((meta?.species ?? []).map((s) => [s.id, s.label])),
    [meta],
  );
  const headline = filterHeadline(filters, speciesLabels);

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
    setSelectedId(id);
    setView("map");
  };

  return (
    <div className="flex h-full min-h-0 flex-col bg-sand text-ink">
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-black/10 bg-pine px-4 py-3 text-sand">
        <div>
          <h1 className="font-serif text-xl font-semibold tracking-tight md:text-2xl">
            Texas Public Land Hunting
          </h1>
          <p className="text-sm text-sand/80">
            {meta ? `${meta.seasonYear} APH, walk-in & Corps of Engineers areas` : "Loading…"} · map and hunt report · unofficial planning aid
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm">
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
          </div>
          <span className="rounded-full bg-gold/20 px-3 py-1 text-gold">
            {matchIds.size} of {units.length} areas
          </span>
          <ExternalLink
            className="rounded-full border border-sand/30 px-3 py-1 hover:bg-white/10"
            href="https://tpwd.texas.gov/huntwild/hunt/public/annual_public_hunting/"
          >
            TPWD APH
          </ExternalLink>
          {canUseOregon && (
            <button
              type="button"
              className={`rounded-full px-3 py-1 ${oregonOpen ? "bg-gold text-pine" : "border border-gold/60 text-gold"}`}
              onClick={() => {
                setView("map");
                setOregonOpen(true);
              }}
            >
              Oregon beta
            </button>
          )}
          {isAdmin && (
            <button
              type="button"
              className={`rounded-full px-3 py-1 ${view === "users" ? "bg-gold text-pine" : "border border-sand/30 hover:bg-white/10"}`}
              onClick={() => {
                setOregonOpen(false);
                setView("users");
              }}
            >
              Users
            </button>
          )}
          <AccountBar savedActive={view === "saved"} onOpenSaved={() => setView("saved")} />
        </div>
      </header>

      {canUseOregon && oregonOpen && <OregonExplorer onClose={() => setOregonOpen(false)} />}
      <div className={`flex min-h-0 flex-1 flex-col md:flex-row ${oregonOpen ? "hidden" : ""}`}>
        <aside className="scrollbar-thin order-2 max-h-[42vh] shrink-0 overflow-y-auto border-t border-black/10 bg-sand p-4 md:order-1 md:max-h-none md:w-80 md:border-r md:border-t-0">
          <FilterPanel
            filters={filters}
            meta={meta}
            onChange={(next) => {
              setFilters(next);
              setSelectedId(null);
            }}
          />
          <p className="mt-4 text-xs leading-relaxed text-muted">{meta?.disclaimer}</p>
        </aside>

        <main className="relative order-1 min-h-[46vh] min-w-0 flex-1 md:order-2">
          {error ? (
            <p className="p-6 text-red-800">{error}</p>
          ) : (
            <>
              <div className={`absolute inset-0 ${view === "map" ? "z-10" : "invisible pointer-events-none"}`}>
                <HuntMap
                  matchingIds={matchIds}
                  selectedId={selectedId}
                  regionFilter={filters.region}
                  satellite={satellite}
                  active={view === "map"}
                  onSelectUnit={setSelectedId}
                  onSelectRegion={(region) => {
                    setSelectedId(null);
                    setFilters((f) => ({ ...f, region: f.region === region ? "" : region }));
                  }}
                />
                <div className="pointer-events-none absolute inset-x-0 top-0 z-10 flex flex-wrap items-start justify-between gap-2 p-3">
                  <div className="pointer-events-auto max-w-xl rounded-md bg-white/90 px-3 py-2 text-sm shadow">
                    <div className="font-semibold">{headline}</div>
                    <div className="text-xs text-muted">
                      {matchIds.size === 0
                        ? "No public hunt units match these filters"
                        : matchIds.size === units.length
                          ? "Click a colored region or a hunt unit"
                          : `Showing ${matchIds.size} matching unit${matchIds.size === 1 ? "" : "s"}`}
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-xs text-muted">
                      <span className="inline-flex items-center gap-1">
                        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "#2f6b4f" }} />
                        TPWD / APH
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "#a0522d" }} />
                        Corps of Engineers
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "#c4a35a" }} />
                        Entry
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "#1c3b2c" }} />
                        Parking
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ backgroundColor: "#1d4e89" }} />
                        Boat ramp
                      </span>
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
                <div className="pointer-events-none absolute inset-x-0 bottom-8 z-10 flex flex-wrap justify-center gap-1 px-3">
                  {regionCounts.map((row) => (
                    <button
                      key={row.region}
                      type="button"
                      className={`pointer-events-auto rounded-full px-2 py-1 text-xs shadow ${
                        filters.region === row.region ? "bg-moss text-white" : "bg-white/90"
                      }`}
                      onClick={() => {
                        setSelectedId(null);
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
              {view === "users" && user && (
                <div className="absolute inset-0 z-10">
                  <UsersView key={user.id} currentUserId={user.id} />
                </div>
              )}
              <div className={`absolute inset-0 ${view === "report" ? "z-10" : "hidden"}`}>
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
              </div>
            </>
          )}
        </main>

        {view === "map" && selected && (
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

            {isCorps ? (
              <>
                <div className="mb-3 rounded border border-gold/40 bg-gold/10 px-3 py-2 text-sm">
                  <p className="font-semibold text-pine">
                    {selected.managingAgency || "U.S. Army Corps of Engineers"}
                  </p>
                  <p className="mt-0.5 text-xs text-muted">
                    Corps of Engineers hunting area — separate from the TPWD e-postcard draw.{" "}
                    {selected.permitRequired
                      ? "A Corps hunting permit is required."
                      : "No Corps hunting permit required."}
                  </p>
                </div>

                {selected.permitInfo && (
                  <div className="mb-3">
                    <h3 className="text-sm font-semibold">Permit &amp; access</h3>
                    <p className="mt-1 text-sm leading-relaxed text-muted">{selected.permitInfo}</p>
                    {selected.permitCost && (
                      <p className="mt-1 text-sm">
                        <span className="font-medium">Cost:</span> {selected.permitCost}
                      </p>
                    )}
                  </div>
                )}

                {selected.means && (
                  <div className="mb-3">
                    <h3 className="text-sm font-semibold">Means &amp; methods</h3>
                    <p className="mt-1 text-sm leading-relaxed text-muted">{selected.means}</p>
                  </div>
                )}

                <div className="mb-3 flex flex-wrap gap-2 text-sm">
                  {selected.mapPdfUrl && (
                    <ExternalLink className="text-moss underline" href={selected.mapPdfUrl}>
                      Detailed hunt map (PDF)
                    </ExternalLink>
                  )}
                  {(selected.links ?? []).map((link) => (
                    <ExternalLink key={link.url} className="text-moss underline" href={link.url}>
                      {link.label}
                    </ExternalLink>
                  ))}
                  <ExternalLink
                    className="text-moss underline"
                    href={
                      selectedCountyPages[0]?.url ||
                      "https://tpwd.texas.gov/regulations/outdoor-annual/hunting/seasons-by-county"
                    }
                  >
                    Outdoor Annual county
                  </ExternalLink>
                </div>
                {(selected.accessPoints ?? []).length > 0 && (
                  <div className="mb-3">
                    <h3 className="text-sm font-semibold">Entry and parking</h3>
                    <ul className="mt-1 space-y-0.5 text-sm text-muted">
                      {(selected.accessPoints ?? []).map((point) => (
                        <li key={`${point.kind}-${point.name}`}>
                          {point.name}
                          <span className="text-xs"> · {ACCESS_KIND_LABEL[point.kind] ?? point.kind}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                <CorpsLegalGame
                  unit={selected}
                  pages={selectedCountyPages}
                  opportunities={opportunities.filter((opp) => opp.unitId === selected.id)}
                  speciesLabels={speciesLabels}
                  speciesOrder={(meta?.species ?? []).map((item) => item.id)}
                />
                {selected.boundaryNote && <p className="mb-3 text-xs text-muted">{selected.boundaryNote}</p>}
              </>
            ) : (
              <>
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
              </>
            )}

            {!isCorps && selectedCountyPages.length > 0 && (
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
