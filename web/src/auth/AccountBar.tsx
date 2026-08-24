import { useAuth } from "./AuthContext";

type Props = {
  savedActive: boolean;
  onOpenSaved: () => void;
  usersActive?: boolean;
  onOpenUsers?: () => void;
};

export default function AccountBar({ savedActive, onOpenSaved, usersActive, onOpenUsers }: Props) {
  const { loading, user, profile, openAuth, signOut, favoriteIds, isAdmin } = useAuth();

  if (loading) {
    return <span className="text-sm text-sand/70">Account…</span>;
  }

  if (!user) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          className="rounded-full border border-sand/30 px-3 py-1 hover:bg-white/10"
          onClick={() => openAuth("signin")}
        >
          Sign in
        </button>
        <button
          type="button"
          className="rounded-full bg-gold px-3 py-1 text-pine hover:bg-gold/90"
          onClick={() => openAuth("signup")}
        >
          Create account
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        className={`rounded-full px-3 py-1 ${savedActive ? "bg-gold text-pine" : "border border-sand/30 hover:bg-white/10"}`}
        onClick={onOpenSaved}
      >
        Saved{favoriteIds.size ? ` · ${favoriteIds.size}` : ""}
      </button>
      {isAdmin && onOpenUsers ? (
        <button
          type="button"
          className={`rounded-full px-3 py-1 ${usersActive ? "bg-gold text-pine" : "border border-sand/30 hover:bg-white/10"}`}
          onClick={onOpenUsers}
        >
          Users
        </button>
      ) : null}
      <span className="max-w-[10rem] truncate text-sm text-sand/90" title={profile?.username ?? user.email ?? ""}>
        {profile?.username ?? user.email}
      </span>
      <button
        type="button"
        className="rounded-full border border-sand/30 px-3 py-1 hover:bg-white/10"
        onClick={() => void signOut()}
      >
        Sign out
      </button>
    </div>
  );
}
