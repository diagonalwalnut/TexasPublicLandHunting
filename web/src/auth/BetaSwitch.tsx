import { useAuth } from "./AuthContext";

export default function BetaSwitch() {
  const { isAdmin, betaEnabled, setBeta } = useAuth();
  if (!isAdmin) return null;

  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-sand">
      <span className="text-xs font-semibold uppercase tracking-wide text-sand/80">Beta</span>
      <button
        type="button"
        role="switch"
        aria-checked={betaEnabled}
        aria-label="Beta features"
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
          betaEnabled ? "bg-gold" : "bg-black/40 ring-1 ring-sand/30"
        }`}
        onClick={() => void setBeta(!betaEnabled)}
      >
        <span
          className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
            betaEnabled ? "translate-x-5" : "translate-x-0"
          }`}
        />
      </button>
    </label>
  );
}
