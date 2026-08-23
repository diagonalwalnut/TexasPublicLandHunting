import ExternalLink from "./ExternalLink";
import FavoriteButton from "./auth/FavoriteButton";
import { AUTH_AND_SAVES_ENABLED } from "./auth/features";
import { safeExternalUrl } from "./urls";
import type { Filters, Opportunity, Unit } from "./types";
import {
  ACCESS_LABEL,
  METHOD_LABEL,
  TYPE_LABEL,
  buildHuntReport,
  filterHeadline,
  formatRange,
  matchingUnitIds,
  regionMatchCounts,
  uniqueDateRanges,
} from "./filters";

type Props = {
  units: Unit[];
  opportunities: Opportunity[];
  filters: Filters;
  speciesLabels: Record<string, string>;
  onSelectUnit: (id: string) => void;
  onSelectRegion: (region: string) => void;
};

export default function HuntReport({
  units,
  opportunities,
  filters,
  speciesLabels,
  onSelectUnit,
  onSelectRegion,
}: Props) {
  const focused = filters.species.length > 0 || filters.methods.length > 0 || filters.access.length > 0;
  const report = focused ? buildHuntReport(units, opportunities, filters) : [];
  const matchIds = matchingUnitIds(units, opportunities, filters);
  const unitTotal = focused ? report.reduce((n, r) => n + r.unitCount, 0) : matchIds.size;
  const headline = filterHeadline(filters, speciesLabels);
  const regionSummary = regionMatchCounts(units, matchIds);

  return (
    <div className="scrollbar-thin h-full overflow-auto bg-sand p-4 md:p-6">
      <header className="mb-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">Hunt report</p>
        <h2 className="font-serif text-2xl font-semibold">{headline}</h2>
        <p className="text-sm text-muted">
          {focused
            ? `${report.length} region${report.length === 1 ? "" : "s"} · ${unitTotal} unit${unitTotal === 1 ? "" : "s"}`
            : `${regionSummary.length} regions · ${unitTotal} public hunt units — pick an animal and method (for example Whitetail + rifle), or a quick report above`}
        </p>
      </header>

      {!focused ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {regionSummary.map((row) => (
            <button
              key={row.region}
              type="button"
              className="rounded-lg bg-white p-4 text-left shadow-sm hover:ring-2 hover:ring-moss"
              onClick={() => onSelectRegion(row.region)}
            >
              <h3 className="font-serif text-lg font-semibold">{row.region}</h3>
              <p className="text-sm text-muted">
                {row.count} unit{row.count === 1 ? "" : "s"}
              </p>
            </button>
          ))}
        </div>
      ) : report.length === 0 ? (
        <p className="rounded-md bg-white p-4 text-sm text-muted">
          No public hunt units match these filters. Try another animal, method, or date range.
        </p>
      ) : (
        <div className="space-y-6">
          {report.map((block) => (
            <section key={block.region} className="overflow-hidden rounded-lg bg-white shadow-sm">
              <button
                type="button"
                className="flex w-full items-baseline justify-between gap-2 bg-pine px-4 py-2 text-left text-sand"
                onClick={() => onSelectRegion(block.region)}
              >
                <h3 className="font-serif text-lg font-semibold">{block.region}</h3>
                <span className="text-sm text-sand/80">
                  {block.unitCount} unit{block.unitCount === 1 ? "" : "s"}
                </span>
              </button>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[40rem] text-left text-sm">
                  <thead className="bg-sand/80 text-xs uppercase tracking-wide text-muted">
                    <tr>
                      {AUTH_AND_SAVES_ENABLED ? <th className="px-3 py-2 font-medium">Save</th> : null}
                      <th className="px-3 py-2 font-medium">Unit</th>
                      <th className="px-3 py-2 font-medium">County</th>
                      <th className="px-3 py-2 font-medium">Booklet</th>
                      <th className="px-3 py-2 font-medium">Access</th>
                      <th className="px-3 py-2 font-medium">Dates</th>
                    </tr>
                  </thead>
                  <tbody>
                    {block.rows.map((row) => {
                      const dates = uniqueDateRanges(row.opportunities);
                      const access = [...new Set(row.opportunities.map((o) => o.access))];
                      const species = [...new Set(row.opportunities.map((o) => o.speciesLabel))];
                      return (
                        <tr key={row.unit.id} className="border-t border-black/5 align-top">
                          {AUTH_AND_SAVES_ENABLED ? (
                            <td className="px-3 py-2">
                              <FavoriteButton unitId={row.unit.id} />
                            </td>
                          ) : null}
                          <td className="px-3 py-2">
                            <button
                              type="button"
                              className="text-left font-medium text-moss underline"
                              onClick={() => onSelectUnit(row.unit.id)}
                            >
                              {row.unit.name}
                            </button>
                            <div className="text-xs text-muted">
                              Unit {row.unit.unitIds.join(", ") || row.unit.id}
                              {row.unit.acres ? ` · ${Math.round(row.unit.acres).toLocaleString()} acres` : ""}
                              {row.unit.type ? ` · ${TYPE_LABEL[row.unit.type] ?? row.unit.type}` : ""}
                              {row.unit.pdfUrl ? " · official PDF" : ""}
                            </div>
                          </td>
                          <td className="px-3 py-2">{row.unit.counties.join(", ") || "—"}</td>
                          <td className="px-3 py-2">
                            {safeExternalUrl(row.unit.bookletUrl) ? (
                              <ExternalLink className="text-moss underline" href={row.unit.bookletUrl}>
                                {row.unit.bookletPage ? `p. ${row.unit.bookletPage}` : "PDF"}
                              </ExternalLink>
                            ) : (
                              "—"
                            )}
                          </td>
                          <td className="px-3 py-2">
                            {access.map((id) => ACCESS_LABEL[id] ?? id).join(", ")}
                          </td>
                          <td className="px-3 py-2">
                            {species.length > 1 ? (
                              <div className="mb-1 text-xs text-muted">{species.join(", ")}</div>
                            ) : null}
                            {dates.map((d) => (
                              <div key={`${d.start}-${d.end}`}>{formatRange(d.start, d.end)}</div>
                            ))}
                            <div className="text-xs text-muted">
                              {[...new Set(row.opportunities.flatMap((o) => o.methods))]
                                .map((m) => METHOD_LABEL[m] ?? m)
                                .join(", ")}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
          <p className="text-xs leading-relaxed text-muted">
            Dates come from the Outdoor Annual county calendar unless a unit PDF overrides them. Confirm
            legal game, means, and dates on the official unit PDF before hunting. Click a unit name to
            open it on the map, or a region header to zoom to that region.
          </p>
        </div>
      )}
    </div>
  );
}
