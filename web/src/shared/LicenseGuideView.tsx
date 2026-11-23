import ExternalLink from "../ExternalLink";
import type { LicenseGuide } from "./licenseTypes";

function formatDay(value: string | null): string {
  if (!value) return "";
  const [y, m, d] = value.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

export default function LicenseGuideView({ guide }: { guide: LicenseGuide }) {
  return (
    <div className="scrollbar-thin absolute inset-0 overflow-y-auto bg-sand p-4 md:p-6">
      <div className="mx-auto max-w-4xl space-y-6">
        <div>
          <h2 className="font-serif text-2xl font-semibold text-pine">{guide.title}</h2>
          <p className="mt-1 text-sm text-muted">{guide.intro}</p>
          <p className="mt-1 text-xs text-muted">Season year {guide.seasonYear}</p>
        </div>

        <section>
          <h3 className="font-semibold text-pine">How to get a license</h3>
          <ul className="mt-2 space-y-2">
            {guide.whereToBuy.map((channel) => (
              <li key={channel.id} className="rounded-lg border border-black/10 bg-white/70 p-3 text-sm">
                <div className="font-medium">{channel.title}</div>
                <p className="mt-1 text-muted">{channel.body}</p>
              </li>
            ))}
          </ul>
        </section>

        <section>
          <h3 className="font-semibold text-pine">Resident and nonresident fees</h3>
          <div className="mt-2 overflow-x-auto rounded-lg border border-black/10 bg-white/70">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-pine/10 text-xs uppercase tracking-wide text-muted">
                <tr>
                  <th className="px-3 py-2">Item</th>
                  <th className="px-3 py-2">Resident</th>
                  <th className="px-3 py-2">Nonresident</th>
                </tr>
              </thead>
              <tbody>
                {guide.fees.map((row) => (
                  <tr key={row.item} className="border-t border-black/5">
                    <td className="px-3 py-2">{row.item}</td>
                    <td className="px-3 py-2">{row.resident || "—"}</td>
                    <td className="px-3 py-2">{row.nonresident || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {guide.residencyRules && guide.residencyRules.length > 0 && (
          <section>
            <h3 className="font-semibold text-pine">Resident vs nonresident (beyond fees)</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">
              {guide.residencyRules.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
        )}

        {guide.deadlines.length > 0 && (
          <section>
            <h3 className="font-semibold text-pine">Deadlines</h3>
            <ul className="mt-2 space-y-2 text-sm">
              {guide.deadlines.map((row) => (
                <li key={row.name} className="rounded bg-white/70 px-3 py-2">
                  <div className="font-medium">
                    {row.name}
                    {row.date ? ` · ${formatDay(row.date)}` : ""}
                  </div>
                  <p className="text-muted">{row.detail}</p>
                </li>
              ))}
            </ul>
          </section>
        )}

        {guide.huntSeries && guide.huntSeries.length > 0 && (
          <section>
            <h3 className="font-semibold text-pine">Hunt series</h3>
            <ul className="mt-2 grid gap-2 sm:grid-cols-2">
              {guide.huntSeries.map((series) => (
                <li key={series.id} className="rounded bg-white/70 px-3 py-2 text-sm">
                  <span className="font-medium">{series.label}</span>
                  <span className="text-muted"> · {series.points ? "preference points" : "no points"}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {guide.preferencePoints && guide.preferencePoints.length > 0 && (
          <section>
            <h3 className="font-semibold text-pine">Preference points</h3>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-muted">
              {guide.preferencePoints.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
        )}

        <section>
          <h3 className="font-semibold text-pine">Sources</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {guide.sources.map((source) => (
              <li key={source.url}>
                <ExternalLink className="text-moss underline" href={source.url}>
                  {source.name}
                </ExternalLink>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
