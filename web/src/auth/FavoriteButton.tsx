import { useAuth } from "./AuthContext";
import { AUTH_AND_SAVES_ENABLED } from "./features";

type Props = {
  unitId: string;
  className?: string;
};

export default function FavoriteButton({ unitId, className = "" }: Props) {
  const { user, isFavorite, toggleFavorite, openAuth } = useAuth();
  if (!AUTH_AND_SAVES_ENABLED) return null;
  const saved = isFavorite(unitId);

  return (
    <button
      type="button"
      className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-sm ${
        saved ? "bg-gold/20 text-pine" : "text-muted hover:bg-sand"
      } ${className}`}
      aria-pressed={saved}
      aria-label={saved ? "Remove from saved units" : "Save unit for later"}
      title={user ? (saved ? "Remove from saved" : "Save for later") : "Sign in to save units"}
      onClick={() => {
        if (!user) {
          openAuth("signin");
          return;
        }
        void toggleFavorite(unitId);
      }}
    >
      <span aria-hidden="true">{saved ? "★" : "☆"}</span>
      <span className="hidden sm:inline">{saved ? "Saved" : "Save"}</span>
    </button>
  );
}
