import FavoriteButton from "./auth/FavoriteButton";
import { useAuth } from "./auth/AuthContext";
import { AUTH_AND_SAVES_ENABLED } from "./auth/features";
import { TYPE_LABEL } from "./filters";
import type { Unit } from "./types";

type Props = {
  units: Unit[];
  onSelectUnit: (id: string) => void;
};

export default function FavoritesView({ units, onSelectUnit }: Props) {
  const { user, favoriteIds, openAuth } = useAuth();
  if (!AUTH_AND_SAVES_ENABLED) return null;
  const byId = new Map(units.map((u) => [u.id, u]));
  const rows = [...favoriteIds].map((id) => ({ id, unit: byId.get(id) ?? null }));

  if (!user) {
    return (
      <div className="h-full overflow-auto bg-sand p-6">
        <h2 className="font-serif text-2xl font-semibold">Saved units</h2>
        <p className="mt-2 text-sm text-muted">
          Sign in to save hunt units and open them later on any device.
        </p>
        <button
          type="button"
          className="mt-4 rounded-md bg-pine px-3 py-2 text-sm text-sand"
          onClick={() => openAuth("signin")}
        >
          Sign in
        </button>
      </div>
    );
  }

  return (
    <div className="scrollbar-thin h-full overflow-auto bg-sand p-4 md:p-6">
      <header className="mb-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">Account</p>
        <h2 className="font-serif text-2xl font-semibold">Saved units</h2>
        <p className="text-sm text-muted">
          {rows.length === 0
            ? "No saved units yet. Open a unit on the map or report and tap the star."
            : `${rows.length} saved unit${rows.length === 1 ? "" : "s"} — click a name to open it on the map.`}
        </p>
      </header>
      {rows.length === 0 ? null : (
        <ul className="space-y-2">
          {rows.map(({ id, unit }) => (
            <li key={id} className="flex items-start justify-between gap-2 rounded-lg bg-white p-3 shadow-sm">
              <div className="min-w-0">
                {unit ? (
                  <>
                    <button
                      type="button"
                      className="text-left font-medium text-moss underline"
                      onClick={() => onSelectUnit(unit.id)}
                    >
                      {unit.name}
                    </button>
                    <p className="text-xs text-muted">
                      Unit {unit.unitIds.join(", ") || unit.id} · {unit.region}
                      {unit.bookletPage ? ` · booklet p. ${unit.bookletPage}` : ""}
                      {unit.type ? ` · ${TYPE_LABEL[unit.type] ?? unit.type}` : ""}
                    </p>
                    {unit.counties.length ? (
                      <p className="text-xs text-muted">{unit.counties.join(", ")} County</p>
                    ) : null}
                  </>
                ) : (
                  <button
                    type="button"
                    className="text-left font-medium text-moss underline"
                    onClick={() => onSelectUnit(id)}
                  >
                    Unit {id}
                  </button>
                )}
              </div>
              <FavoriteButton unitId={id} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
