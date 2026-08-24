import ExternalLink from "./ExternalLink";
import { safeExternalUrl } from "./urls";
import type { DrawnHunt, Filters } from "./types";
import {
  ACCESS_LABEL,
  METHOD_LABEL,
  buildDrawnHuntReport,
  drawnRegionMatchCounts,
  filterHeadline,
  formatRange,
  matchingDrawnHuntIds,
} from "./filters";

type Props = {
  hunts: DrawnHunt[];
  filters: Filters;
  speciesLabels: Record<string, string>;
  onSelectHunt: (id: string) => void;
  onSelectRegion: (region: string) => void;
};

function feeLabel(hunt: DrawnHunt): string {
  const parts: string[] = [];
  if (hunt.feeAdult != null) parts.push(`$${hunt.feeAdult.toFixed(0)} adult`);
  if (hunt.feeYouth != null) parts.push(`$${hunt.feeYouth.toFixed(0)} youth`);
  return parts.join(" · ") || "—";
}

export default function DrawnReport({ hunts, filters, speciesLabels, onSelectHunt, onSelectRegion }: Props) {
  const focused = filters.species.length > 0 || filters.methods.length > 0 || filters.access.length > 0;
  const report = focused ? buildDrawnHuntReport(hunts, filters) : [];
  const matchIds = matchingDrawnHuntIds(hunts, filters);
  const huntTotal = focused ? report.reduce((n, r) => n + r.huntCount, 0) : matchIds.size;
  const headline = filterHeadline(filters, speciesLabels, "All drawn hunts");
  const regionSummary = drawnRegionMatchCounts(hunts, matchIds);

  return (
    <div className="scrollbar-thin h-full overflow-auto bg-sand p-4 md:p-6">
      <header className="mb-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">Drawn hunt report</p>
        <h2 className="font-serif text-2xl font-semibold">{headline}</h2>
        <p className="text-sm text-muted">
          {focused
            ? `${report.length} region${report.length === 1 ? "" : "s"} · ${huntTotal} hunt${huntTotal === 1 ? "" : "s"}`
            : `${regionSummary.length} regions · ${huntTotal} drawn hunts — pick an animal and method, or a quick report above`}
        </p>
      </header>

      {!focused ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {regionSummary.map((row) => (
            <button
              key={row.region}
              type="button"
              className="rounded-lg bg-white p-4 text-left shadow-sm hover:ring-2 hover:ring-moss"
              onClick={() => onSelectRegion(row.region === "Other areas" ? "" : row.region)}
            >
              <h3 className="font-serif text-lg font-semibold">{row.region}</h3>
              <p className="text-sm text-muted">
                {row.count} hunt{row.count === 1 ? "" : "s"}
              </p>
            </button>
          ))}
        </div>
      ) : report.length === 0 ? (
        <p className="rounded-md bg-white p-4 text-sm text-muted">
          No drawn hunts match these filters. Try another animal, method, or date range.
        </p>
      ) : (
        <div className="space-y-6">
          {report.map((block) => (
            <section key={block.region} className="overflow-hidden rounded-lg bg-white shadow-sm">
              <button
                type="button"
                className="flex w-full items-baseline justify-between gap-2 bg-pine px-4 py-2 text-left text-sand"
                onClick={() => onSelectRegion(block.region === "Other areas" ? "" : block.region)}
              >
                <h3 className="font-serif text-lg font-semibold">{block.region}</h3>
                <span className="text-sm text-sand/80">
                  {block.huntCount} hunt{block.huntCount === 1 ? "" : "s"}
                </span>
              </button>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[44rem] text-left text-sm">
                  <thead className="bg-sand/80 text-xs uppercase tracking-wide text-muted">
                    <tr>
                      <th className="px-3 py-2 font-medium">Area</th>
                      <th className="px-3 py-2 font-medium">Hunt</th>
                      <th className="px-3 py-2 font-medium">Deadline</th>
                      <th className="px-3 py-2 font-medium">Dates</th>
                      <th className="px-3 py-2 font-medium">Weapons</th>
                      <th className="px-3 py-2 font-medium">Fee</th>
                    </tr>
                  </thead>
                  <tbody>
                    {block.hunts.map((hunt) => (
                      <tr key={hunt.id} className="border-t border-black/5 align-top">
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            className="text-left font-medium text-moss underline"
                            onClick={() => onSelectHunt(hunt.id)}
                          >
                            {hunt.areaName}
                          </button>
                          <div className="text-xs text-muted">
                            {hunt.counties.join(", ") || hunt.areaCode}
                            {hunt.access ? ` · ${ACCESS_LABEL[hunt.access] ?? hunt.access}` : ""}
                          </div>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex items-center gap-2">
                            <span
                              className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
                              style={{ background: hunt.color }}
                            />
                            {hunt.speciesLabel || hunt.categoryName}
                          </div>
                          <div className="text-xs text-muted">{hunt.categoryName}</div>
                        </td>
                        <td className="px-3 py-2">
                          {hunt.applicationDeadline ? formatRange(hunt.applicationDeadline, hunt.applicationDeadline) : "—"}
                        </td>
                        <td className="px-3 py-2">
                          {hunt.huntDates.length
                            ? hunt.huntDates.map((d) => (
                                <div key={`${hunt.id}-${d.start}-${d.end}`}>{formatRange(d.start, d.end)}</div>
                              ))
                            : "—"}
                        </td>
                        <td className="px-3 py-2">
                          {hunt.meansAllowed.length
                            ? hunt.meansAllowed.join(", ")
                            : hunt.methods.map((m) => METHOD_LABEL[m] ?? m).join(", ")}
                        </td>
                        <td className="px-3 py-2">
                          {feeLabel(hunt)}
                          {safeExternalUrl(hunt.applyUrl) ? (
                            <div>
                              <ExternalLink className="text-xs text-moss underline" href={hunt.applyUrl}>
                                Apply
                              </ExternalLink>
                            </div>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ))}
          <p className="text-xs leading-relaxed text-muted">
            Drawn hunt details come from the TPWD public hunt drawing catalog. Deadlines, means, and dates
            change. Confirm every hunt on the official catalog before you apply.
          </p>
        </div>
      )}
    </div>
  );
}
