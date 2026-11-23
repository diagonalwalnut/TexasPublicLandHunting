import { useEffect, useMemo, useState } from "react";
import {
  buildInSeason,
  countyOptionsFromRows,
  methodLabel,
  rollupRowsByCounty,
  scopeRowsToCounty,
  type InSeasonSourceRow,
  type InSeasonSpecies,
} from "./inSeason";
import { todayInTimezone } from "../states/catalog";

function formatRange(start: string, end: string): string {
  const fmt = (value: string) => {
    const [y, m, d] = value.split("-").map(Number);
    return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone: "UTC",
    });
  };
  return start === end ? fmt(start) : `${fmt(start)} – ${fmt(end)}`;
}

/** Shared filters carried between Map/Report/Hunts and In Season. */
export type InSeasonSharedFilters = {
  date?: string;
  species?: string[];
  methods?: string[];
  access?: string[];
  /** Free-text search (unit/hunt/county names). */
  query?: string;
  /** County, parish, region, zone, or unit label. */
  place?: string;
  start?: string;
  end?: string;
};

function speciesMatches(
  card: InSeasonSpecies,
  selected: string[],
  speciesLabels?: Record<string, string>,
): boolean {
  if (!selected.length) return true;
  const labelById = speciesLabels ?? {};
  return selected.some((id) => {
    if (card.species === id) return true;
    if (card.label === id) return true;
    const label = labelById[id];
    return Boolean(label && card.label === label);
  });
}

function placeMatches(card: InSeasonSpecies, place: string, query: string): boolean {
  const placeNeedle = place.trim().toLowerCase();
  const queryNeedle = query.trim().toLowerCase();
  if (!placeNeedle && !queryNeedle) return true;
  if (card.statewide) {
    if (queryNeedle && !placeNeedle) {
      const hay = `${card.label} ${card.species}`.toLowerCase();
      return hay.includes(queryNeedle);
    }
    return true;
  }
  return card.places.some((row) => {
    const hay = `${row.label} ${row.id}`.toLowerCase();
    if (placeNeedle && !hay.includes(placeNeedle)) return false;
    if (queryNeedle && !hay.includes(queryNeedle) && !`${card.label}`.toLowerCase().includes(queryNeedle)) {
      return false;
    }
    return true;
  });
}

export default function InSeasonPage({
  rows,
  timezone,
  stateName,
  methodLabels,
  speciesLabels,
  placeFilterLabel = "Region / county / zone",
  shared,
  onSharedChange,
  /** When true, Place dropdown lists counties only and filtering scopes to one county. */
  countyMode = false,
}: {
  rows: InSeasonSourceRow[];
  timezone: string;
  stateName: string;
  methodLabels?: Record<string, string>;
  speciesLabels?: Record<string, string>;
  placeFilterLabel?: string;
  shared?: InSeasonSharedFilters;
  onSharedChange?: (next: InSeasonSharedFilters) => void;
  countyMode?: boolean;
}) {
  const defaultDate = todayInTimezone(timezone);
  const date = shared?.date || shared?.start || defaultDate;
  const speciesFilter = shared?.species?.[0] ?? "";
  const methodFilter = shared?.methods?.[0] ?? "";
  const placeFilter = shared?.place ?? "";
  const query = shared?.query ?? "";
  const selectedSpecies = shared?.species ?? [];
  const selectedMethods = shared?.methods ?? [];
  const selectedAccess = shared?.access ?? [];

  const [localDate, setLocalDate] = useState(defaultDate);
  const [localSpecies, setLocalSpecies] = useState("");
  const [localMethod, setLocalMethod] = useState("");
  const [localPlace, setLocalPlace] = useState("");
  const controlled = Boolean(onSharedChange);

  useEffect(() => {
    if (!controlled) setLocalDate(todayInTimezone(timezone));
  }, [timezone, controlled]);

  const activeDate = controlled ? date : localDate;
  const activeSpecies = controlled ? speciesFilter : localSpecies;
  const activeMethod = controlled ? methodFilter : localMethod;
  const activePlace = controlled ? placeFilter : localPlace;

  const counties = useMemo(
    () => (countyMode ? countyOptionsFromRows(rows) : []),
    [countyMode, rows],
  );

  const selectedCounty = useMemo(() => {
    if (!countyMode || !activePlace.trim()) return null;
    const needle = activePlace.trim().toLowerCase();
    return (
      counties.find(
        (c) =>
          c.label.toLowerCase() === needle ||
          c.id.toLowerCase() === needle ||
          c.label.toLowerCase().startsWith(needle) ||
          needle.startsWith(c.label.toLowerCase().replace(/ county$/, "")),
      ) ?? null
    );
  }, [countyMode, activePlace, counties]);

  const scopedRows = useMemo(() => {
    if (!countyMode) return rows;
    if (selectedCounty) return scopeRowsToCounty(rows, selectedCounty.id);
    return rollupRowsByCounty(rows);
  }, [countyMode, rows, selectedCounty]);

  const cards = useMemo(() => buildInSeason(scopedRows, activeDate), [scopedRows, activeDate]);

  const speciesOptions = useMemo(() => {
    const ids = [...new Set(rows.map((row) => row.species))].sort();
    return ids.map((id) => ({
      id,
      label: rows.find((row) => row.species === id)?.speciesLabel || speciesLabels?.[id] || id,
    }));
  }, [rows, speciesLabels]);
  const methodOptions = useMemo(
    () => [...new Set(rows.flatMap((row) => row.methods))].sort(),
    [rows],
  );
  const placeOptions = useMemo(() => {
    if (countyMode) return counties.map((c) => c.label);
    return [...new Set(rows.map((row) => row.placeLabel))].sort();
  }, [countyMode, counties, rows]);

  const filtered = cards.filter((card) => {
    const speciesSel = controlled ? selectedSpecies : activeSpecies ? [activeSpecies] : [];
    if (!speciesMatches(card, speciesSel, speciesLabels)) return false;

    const methodSel = controlled ? selectedMethods : activeMethod ? [activeMethod] : [];
    if (methodSel.length) {
      const ok =
        methodSel.some((id) => card.methods.includes(id)) ||
        card.places.some((place) => methodSel.some((id) => place.methods.includes(id)));
      if (!ok) return false;
    }

    if (selectedAccess.length) {
      const accessOk = scopedRows.some((row) => {
        if (row.species !== card.species) return false;
        const label = row.accessLabel.toLowerCase();
        return selectedAccess.some((id) => {
          const pretty = id.replaceAll("_", " ").toLowerCase();
          return label === id.toLowerCase() || label.includes(pretty) || pretty.includes(label);
        });
      });
      if (!accessOk) return false;
    }

    // County mode already scoped rows before build; skip place substring filtering.
    if (countyMode) {
      if (controlled && query.trim()) {
        const q = query.trim().toLowerCase();
        const hay = `${card.label} ${card.species}`.toLowerCase();
        if (!hay.includes(q) && !card.places.some((p) => `${p.label} ${p.id}`.toLowerCase().includes(q))) {
          return false;
        }
      }
      return true;
    }

    if (!placeMatches(card, activePlace, controlled ? query : "")) return false;
    return true;
  });

  const displayCards = filtered.map((card) => {
    if (countyMode || card.statewide || (!activePlace.trim() && !(controlled && query.trim()))) {
      return card;
    }
    const needles = [activePlace, controlled ? query : ""]
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean);
    if (!needles.length) return card;
    return {
      ...card,
      places: card.places.filter((place) => {
        const hay = `${place.label} ${place.id}`.toLowerCase();
        return needles.every((needle) => hay.includes(needle));
      }),
    };
  });

  const uniformCount = displayCards.filter((card) => card.statewide).length;
  const partialCount = displayCards.length - uniformCount;
  const scopeLabel = selectedCounty
    ? selectedCounty.label
    : countyMode
      ? "all counties"
      : "statewide";

  const patchShared = (patch: InSeasonSharedFilters) => {
    if (!onSharedChange) return;
    onSharedChange({
      date: activeDate,
      species: selectedSpecies,
      methods: selectedMethods,
      access: selectedAccess,
      query,
      place: placeFilter,
      start: shared?.start,
      end: shared?.end,
      ...patch,
    });
  };

  const uniformBadge = selectedCounty ? "Open in this county" : "Statewide";
  const partialBadge = selectedCounty ? "Differs by zone / portion" : "Regional differences";
  const placeHeading = selectedCounty ? "Zone / portion" : "Differences";

  return (
    <div className="scrollbar-thin absolute inset-0 overflow-y-auto bg-sand p-4 md:p-6">
      <div className="mx-auto max-w-4xl">
        <h2 className="font-serif text-2xl font-semibold text-pine">In season · {stateName}</h2>
        <p className="mt-1 text-sm text-muted">
          {countyMode
            ? "Animals open on the selected date for the chosen county. Zone seasons (North Zone, etc.) are shown as that county’s rules when the county is in the zone."
            : "Animals open on the selected date, with legal methods. Map and report filters carry over here when you switch views. Region, county, and zone differences are listed under each species when they do not match statewide."}
        </p>

        <div className="mt-4 flex flex-wrap gap-3 rounded-lg border border-black/10 bg-white/60 p-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-wide text-muted">Date</span>
            <input
              type="date"
              className="rounded border border-black/15 bg-white px-2 py-1"
              value={activeDate}
              onChange={(event) => {
                const next = event.target.value;
                if (controlled) {
                  patchShared({ date: next, start: next, end: next });
                } else {
                  setLocalDate(next);
                }
              }}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-wide text-muted">Animal</span>
            <select
              className="rounded border border-black/15 bg-white px-2 py-1"
              value={activeSpecies}
              onChange={(event) => {
                const next = event.target.value;
                if (controlled) {
                  patchShared({ species: next ? [next] : [] });
                } else {
                  setLocalSpecies(next);
                }
              }}
            >
              <option value="">All</option>
              {speciesOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-wide text-muted">Method</span>
            <select
              className="rounded border border-black/15 bg-white px-2 py-1"
              value={activeMethod}
              onChange={(event) => {
                const next = event.target.value;
                if (controlled) {
                  patchShared({ methods: next ? [next] : [] });
                } else {
                  setLocalMethod(next);
                }
              }}
            >
              <option value="">All</option>
              {methodOptions.map((id) => (
                <option key={id} value={id}>
                  {methodLabel(id, methodLabels)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-wide text-muted">
              {countyMode ? "County" : placeFilterLabel}
            </span>
            <select
              className="rounded border border-black/15 bg-white px-2 py-1"
              value={
                countyMode && selectedCounty
                  ? selectedCounty.label
                  : countyMode
                    ? ""
                    : activePlace
              }
              onChange={(event) => {
                const next = event.target.value;
                if (controlled) {
                  patchShared({ place: next });
                } else {
                  setLocalPlace(next);
                }
              }}
            >
              <option value="">All</option>
              {placeOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          {controlled && query.trim() ? (
            <p className="flex items-end text-xs text-muted">Search: “{query.trim()}”</p>
          ) : null}
        </div>

        <p className="mt-3 text-sm text-pine">
          {selectedCounty ? (
            <>
              {displayCards.length} animal{displayCards.length === 1 ? "" : "s"} open in{" "}
              {selectedCounty.label}
              {partialCount > 0 ? `; ${partialCount} differ by zone or portion` : ""}
              .
            </>
          ) : (
            <>
              {uniformCount} animal{uniformCount === 1 ? "" : "s"} open {scopeLabel === "statewide" ? "statewide" : `the same across ${scopeLabel}`}
              {partialCount > 0
                ? `; ${partialCount} open only in some ${countyMode ? "counties" : "regions, counties, or zones"}`
                : ""}
              .
            </>
          )}
        </p>

        {displayCards.length === 0 ? (
          <p className="mt-6 text-sm text-muted">No published seasons cover this date for the current filters.</p>
        ) : (
          <ul className="mt-4 space-y-3">
            {displayCards.map((card) => (
              <SpeciesCard
                key={`${card.species}::${card.label}`}
                card={card}
                methodLabels={methodLabels}
                uniformBadge={uniformBadge}
                partialBadge={partialBadge}
                placeHeading={placeHeading}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function SpeciesCard({
  card,
  methodLabels,
  uniformBadge,
  partialBadge,
  placeHeading,
}: {
  card: InSeasonSpecies;
  methodLabels?: Record<string, string>;
  uniformBadge: string;
  partialBadge: string;
  placeHeading: string;
}) {
  return (
    <li className="rounded-lg border border-black/10 bg-white/70 p-3 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-serif text-lg font-semibold text-pine">{card.label}</h3>
        <span
          className={`rounded-full px-2 py-0.5 text-xs ${
            card.statewide ? "bg-moss/15 text-moss" : "bg-gold/25 text-pine"
          }`}
        >
          {card.statewide ? uniformBadge : partialBadge}
        </span>
      </div>
      {card.statewide ? (
        <div className="mt-2 text-sm">
          <p>
            <span className="text-muted">Methods: </span>
            {card.methods.map((id) => methodLabel(id, methodLabels)).join(", ") || "See regulations"}
          </p>
          {card.accessLabels.length > 0 && (
            <p>
              <span className="text-muted">Access: </span>
              {card.accessLabels.join(" · ")}
            </p>
          )}
          <p>
            <span className="text-muted">Windows: </span>
            {card.windows.map((window) => formatRange(window.start, window.end)).join("; ")}
          </p>
          {card.notes.length > 0 && (
            <p>
              <span className="text-muted">Zone: </span>
              {card.notes.join(" · ")}
            </p>
          )}
        </div>
      ) : (
        <div className="mt-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-gold">{placeHeading}</p>
          <ul className="mt-1 space-y-2">
            {card.places.map((place) => (
              <li key={place.id} className="rounded bg-sand px-2 py-1.5 text-sm">
                <div className="font-medium">
                  {place.label}
                  {place.notes.length > 0 && place.notes.join(" · ") !== place.label ? (
                    <span className="font-normal text-muted"> · {place.notes.join(" · ")}</span>
                  ) : null}
                </div>
                <div className="text-xs text-muted">
                  Methods: {place.methods.map((id) => methodLabel(id, methodLabels)).join(", ") || "See regulations"}
                </div>
                {place.accessLabels.length > 0 && (
                  <div className="text-xs text-muted">Access: {place.accessLabels.join(" · ")}</div>
                )}
                <div className="text-xs text-muted">
                  Windows: {place.windows.map((window) => formatRange(window.start, window.end)).join("; ")}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </li>
  );
}
