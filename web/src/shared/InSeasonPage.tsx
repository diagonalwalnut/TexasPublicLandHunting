import { useMemo, useState } from "react";
import {
  buildInSeason,
  methodLabel,
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

export default function InSeasonPage({
  rows,
  timezone,
  stateName,
  methodLabels,
  placeFilterLabel = "Region / county / zone",
}: {
  rows: InSeasonSourceRow[];
  timezone: string;
  stateName: string;
  methodLabels?: Record<string, string>;
  placeFilterLabel?: string;
}) {
  const [date, setDate] = useState(() => todayInTimezone(timezone));
  const [speciesFilter, setSpeciesFilter] = useState("");
  const [methodFilter, setMethodFilter] = useState("");
  const [placeFilter, setPlaceFilter] = useState("");

  const cards = useMemo(() => buildInSeason(rows, date), [rows, date]);
  const speciesOptions = useMemo(
    () => [...new Set(rows.map((row) => row.speciesLabel || row.species))].sort(),
    [rows],
  );
  const methodOptions = useMemo(
    () => [...new Set(rows.flatMap((row) => row.methods))].sort(),
    [rows],
  );
  const placeOptions = useMemo(
    () => [...new Set(rows.map((row) => row.placeLabel))].sort(),
    [rows],
  );

  const filtered = cards.filter((card) => {
    if (speciesFilter && card.label !== speciesFilter && card.species !== speciesFilter) return false;
    if (methodFilter && !card.methods.includes(methodFilter)) {
      if (!card.places.some((place) => place.methods.includes(methodFilter))) return false;
    }
    if (placeFilter) {
      if (card.statewide) return true;
      if (!card.places.some((place) => place.label === placeFilter)) return false;
    }
    return true;
  });

  const statewideCount = filtered.filter((card) => card.statewide).length;
  const partialCount = filtered.length - statewideCount;

  return (
    <div className="scrollbar-thin absolute inset-0 overflow-y-auto bg-sand p-4 md:p-6">
      <div className="mx-auto max-w-4xl">
        <h2 className="font-serif text-2xl font-semibold text-pine">In season · {stateName}</h2>
        <p className="mt-1 text-sm text-muted">
          Animals open on the selected date, with legal methods. Region, county, and zone differences are listed under
          each species when they do not match statewide.
        </p>

        <div className="mt-4 flex flex-wrap gap-3 rounded-lg border border-black/10 bg-white/60 p-3 text-sm">
          <label className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-wide text-muted">Date</span>
            <input
              type="date"
              className="rounded border border-black/15 bg-white px-2 py-1"
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-wide text-muted">Animal</span>
            <select
              className="rounded border border-black/15 bg-white px-2 py-1"
              value={speciesFilter}
              onChange={(event) => setSpeciesFilter(event.target.value)}
            >
              <option value="">All</option>
              {speciesOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs uppercase tracking-wide text-muted">Method</span>
            <select
              className="rounded border border-black/15 bg-white px-2 py-1"
              value={methodFilter}
              onChange={(event) => setMethodFilter(event.target.value)}
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
            <span className="text-xs uppercase tracking-wide text-muted">{placeFilterLabel}</span>
            <select
              className="rounded border border-black/15 bg-white px-2 py-1"
              value={placeFilter}
              onChange={(event) => setPlaceFilter(event.target.value)}
            >
              <option value="">All</option>
              {placeOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <p className="mt-3 text-sm text-pine">
          {statewideCount} animal{statewideCount === 1 ? "" : "s"} open statewide
          {partialCount > 0
            ? `; ${partialCount} open only in some regions, counties, or zones`
            : filtered.length === 0
              ? ""
              : ""}
          .
        </p>

        {filtered.length === 0 ? (
          <p className="mt-6 text-sm text-muted">No published seasons cover this date for the current filters.</p>
        ) : (
          <ul className="mt-4 space-y-3">
            {filtered.map((card) => (
              <SpeciesCard key={card.species} card={card} methodLabels={methodLabels} />
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
}: {
  card: InSeasonSpecies;
  methodLabels?: Record<string, string>;
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
          {card.statewide ? "Statewide" : "Regional differences"}
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
        </div>
      ) : (
        <div className="mt-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-gold">Differences</p>
          <ul className="mt-1 space-y-2">
            {card.places.map((place) => (
              <li key={place.id} className="rounded bg-sand px-2 py-1.5 text-sm">
                <div className="font-medium">{place.label}</div>
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
