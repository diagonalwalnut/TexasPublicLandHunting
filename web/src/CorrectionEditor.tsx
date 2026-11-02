import { useEffect, useState } from "react";
import { clearCorrection, saveCorrection, type UnitCorrection } from "./auth/api";
import { METHOD_LABEL } from "./filters";
import type { MethodId, Opportunity, Unit } from "./types";

const CHOICES: MethodId[] = ["archery", "firearm", "muzzleloader", "shotgun"];

type Props = {
  unit: Unit;
  opportunities: Opportunity[];
  speciesLabels: Record<string, string>;
  onChange: (corrections: UnitCorrection[]) => void;
};

export default function CorrectionEditor({ unit, opportunities, speciesLabels, onChange }: Props) {
  const speciesIds = [...new Set([...unit.species, ...opportunities.map((opp) => opp.species)])]
    .filter((id) => id && id !== "fishing")
    .sort((a, b) => (speciesLabels[a] ?? a).localeCompare(speciesLabels[b] ?? b));
  const saved = unit.methodCorrection;
  const [riflesProhibited, setRiflesProhibited] = useState(saved?.forbidMethods?.includes("firearm") ?? false);
  const [note, setNote] = useState(saved?.note || unit.correctionNote || "");
  const [methods, setMethods] = useState<Record<string, MethodId[]>>(() => {
    const next: Record<string, MethodId[]> = {};
    for (const species of speciesIds) {
      const fromCorrection = saved?.speciesMethods?.[species];
      if (fromCorrection) {
        next[species] = fromCorrection.filter((method) => method !== "firearm" || !saved?.forbidMethods?.includes("firearm"));
        continue;
      }
      const found = new Set(opportunities.filter((opp) => opp.species === species).flatMap((opp) => opp.methods));
      next[species] = CHOICES.filter((method) => found.has(method) && method !== "any_legal");
    }
    return next;
  });
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const correctionKey = `${unit.correctionNote ?? ""}\n${JSON.stringify(unit.methodCorrection ?? null)}`;

  useEffect(() => {
    const current = unit.methodCorrection;
    setRiflesProhibited(current?.forbidMethods?.includes("firearm") ?? false);
    setNote(current?.note || unit.correctionNote || "");
    const next: Record<string, MethodId[]> = {};
    for (const species of speciesIds) {
      const fromCorrection = current?.speciesMethods?.[species];
      if (fromCorrection) {
        next[species] = fromCorrection.filter(
          (method) => method !== "firearm" || !current?.forbidMethods?.includes("firearm"),
        );
        continue;
      }
      const found = new Set(opportunities.filter((opp) => opp.species === species).flatMap((opp) => opp.methods));
      next[species] = CHOICES.filter((method) => found.has(method));
    }
    setMethods(next);
    // Reload the form when a save or reset changes the stored correction.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [correctionKey]);

  function toggle(species: string, method: MethodId) {
    setMethods((current) => {
      const list = current[species] ?? [];
      const next = list.includes(method) ? list.filter((item) => item !== method) : [...list, method];
      return { ...current, [species]: next };
    });
  }

  async function save() {
    setSaving(true);
    setError(null);
    const speciesMethods: Record<string, MethodId[]> = {};
    for (const species of speciesIds) {
      const selectedMethods = (methods[species] ?? []).filter((method) => method !== "firearm" || !riflesProhibited);
      // Leave unspecified any-legal species alone unless this correction already names them.
      if (!selectedMethods.length && !saved?.speciesMethods?.[species]) continue;
      speciesMethods[species] = selectedMethods;
    }
    try {
      const corrections = await saveCorrection({
        unitId: unit.id,
        speciesMethods,
        forbidMethods: riflesProhibited ? ["firearm"] : [],
        note: note.trim(),
      });
      onChange(corrections);
      setStatus("Saved. The map and report now use this correction.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save this correction.");
    } finally {
      setSaving(false);
    }
  }

  async function reset() {
    setSaving(true);
    setError(null);
    try {
      const corrections = await clearCorrection(unit.id);
      onChange(corrections);
      setStatus("Removed. Showing the hunt data again.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not remove this correction.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="mb-4 rounded-md border border-black/10 bg-white p-3">
      <h3 className="text-sm font-semibold">Correct legal methods</h3>
      <p className="mb-2 text-xs text-muted">
        Saved changes apply to the map and report for every visitor. Rifles prohibited also removes “any legal means,”
        because that tag is treated as a rifle.
      </p>
      <label className="mb-3 flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={riflesProhibited}
          onChange={(event) => setRiflesProhibited(event.target.checked)}
        />
        Rifles prohibited
      </label>
      <ul className="mb-3 space-y-2">
        {speciesIds.map((species) => (
          <li key={species}>
            <p className="text-xs font-medium">{speciesLabels[species] ?? species}</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {CHOICES.map((method) => {
                const on = (methods[species] ?? []).includes(method);
                const disabled = saving || (method === "firearm" && riflesProhibited);
                return (
                  <button
                    key={method}
                    type="button"
                    aria-pressed={on && !disabled}
                    disabled={disabled}
                    onClick={() => toggle(species, method)}
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      on && !disabled ? "bg-moss text-white" : "bg-sand text-muted ring-1 ring-black/10"
                    } disabled:opacity-40`}
                  >
                    {METHOD_LABEL[method] ?? method}
                  </button>
                );
              })}
            </div>
          </li>
        ))}
      </ul>
      <label className="mb-3 block text-sm">
        Note
        <textarea
          className="mt-1 w-full rounded-md border border-black/15 bg-white px-2 py-1.5 text-sm"
          rows={3}
          maxLength={500}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </label>
      {error && <p className="mb-2 text-sm text-red-800">{error}</p>}
      {status && !error && <p className="mb-2 text-sm text-moss">{status}</p>}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="rounded-full bg-moss px-3 py-1 text-sm text-white disabled:opacity-50"
          disabled={saving}
          onClick={() => void save()}
        >
          Save correction
        </button>
        <button
          type="button"
          className="rounded-full px-3 py-1 text-sm text-muted ring-1 ring-black/15 disabled:opacity-50"
          disabled={saving}
          onClick={() => void reset()}
        >
          Remove saved correction
        </button>
      </div>
    </section>
  );
}
