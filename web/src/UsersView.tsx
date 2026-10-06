import { useEffect, useState } from "react";
import {
  fetchAdminUsers,
  updateAdminUser,
  type BetaFeature,
  type ManagedUser,
} from "./auth/api";

type Props = {
  currentUserId: string;
};

export default function UsersView({ currentUserId }: Props) {
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [betas, setBetas] = useState<BetaFeature[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);

  useEffect(() => {
    let cancel = false;
    fetchAdminUsers()
      .then((data) => {
        if (cancel) return;
        setUsers(data.users);
        setBetas(data.betas);
      })
      .catch((err: unknown) => {
        if (!cancel) setError(err instanceof Error ? err.message : "Could not load users.");
      })
      .finally(() => {
        if (!cancel) setLoading(false);
      });
    return () => {
      cancel = true;
    };
  }, []);

  async function save(user: ManagedUser, patch: { role?: "admin" | "user"; betas?: string[] }) {
    setSavingId(user.id);
    setError(null);
    try {
      const updated = await updateAdminUser({ user_id: user.id, ...patch });
      setUsers((rows) => rows.map((row) => (row.id === updated.id ? updated : row)));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Could not update that user.");
    } finally {
      setSavingId(null);
    }
  }

  return (
    <div className="scrollbar-thin h-full overflow-auto bg-sand p-4 md:p-6">
      <header className="mb-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">Account</p>
        <h2 className="font-serif text-2xl font-semibold">Users</h2>
        <p className="text-sm text-muted">
          Promote an account to admin, or grant a beta to a regular account. Admins can open every beta.
        </p>
      </header>
      {error && <p className="mb-3 text-sm text-red-800">{error}</p>}
      {loading ? (
        <p className="text-sm text-muted">Loading users…</p>
      ) : users.length === 0 ? (
        <p className="text-sm text-muted">No accounts yet.</p>
      ) : (
        <ul className="space-y-3">
          {users.map((user) => {
            const saving = savingId === user.id;
            const isSelfAdmin = user.id === currentUserId && user.role === "admin";
            return (
              <li key={user.id} className="rounded-md border border-black/10 bg-white p-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate font-semibold">{user.username}</div>
                    <div className="truncate text-sm text-muted">{user.email}</div>
                  </div>
                  <label className="text-sm">
                    <span className="mr-2 text-muted">Role</span>
                    <select
                      className="rounded border border-black/15 bg-sand px-2 py-1"
                      value={user.role}
                      disabled={saving || isSelfAdmin}
                      onChange={(event) => {
                        const role = event.target.value === "admin" ? "admin" : "user";
                        void save(user, { role });
                      }}
                    >
                      <option value="user">User</option>
                      <option value="admin">Admin</option>
                    </select>
                  </label>
                </div>
                {betas.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-3">
                    {betas.map((beta) => {
                      const granted = user.role === "admin" || user.betas.includes(beta.id);
                      return (
                        <label key={beta.id} className="inline-flex items-center gap-2 text-sm">
                          <input
                            type="checkbox"
                            checked={granted}
                            disabled={saving || user.role === "admin"}
                            onChange={(event) => {
                              const next = event.target.checked
                                ? [...user.betas, beta.id]
                                : user.betas.filter((id) => id !== beta.id);
                              void save(user, { betas: next });
                            }}
                          />
                          {beta.label}
                        </label>
                      );
                    })}
                  </div>
                )}
                {isSelfAdmin && (
                  <p className="mt-2 text-xs text-muted">You cannot remove your own admin role.</p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
