import { useEffect, useState } from "react";
import { useAuth } from "./auth/AuthContext";
import type { ManagedUser } from "./auth/api";

export default function UsersView() {
  const { user, loadUsers, changeUserRole } = useAuth();
  const [rows, setRows] = useState<ManagedUser[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const result = await loadUsers();
      if (cancelled) return;
      if (typeof result === "string") {
        setError(result);
        return;
      }
      setRows(result);
    })();
    return () => {
      cancelled = true;
    };
  }, [loadUsers]);

  const adminCount = rows.filter((row) => row.role === "admin").length;

  const onRole = async (row: ManagedUser, role: "user" | "admin") => {
    setError(null);
    setBusyId(row.id);
    const result = await changeUserRole(row.id, role);
    setBusyId(null);
    if (typeof result === "string") {
      setError(result);
      return;
    }
    setRows(result);
  };

  return (
    <div className="scrollbar-thin h-full overflow-auto bg-sand p-4 md:p-6">
      <header className="mb-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">Account</p>
        <h2 className="font-serif text-2xl font-semibold">Users</h2>
        <p className="text-sm text-muted">
          Administrators can sign in, manage roles, and turn beta features on for themselves.
          Standard users can save hunt units. Passwords are stored as Argon2id hashes, never plain
          text.
        </p>
      </header>
      {error ? <p className="mb-3 text-sm text-red-800">{error}</p> : null}
      <div className="overflow-x-auto rounded-lg bg-white shadow-sm">
        <table className="w-full min-w-[36rem] text-left text-sm">
          <thead className="bg-sand/80 text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">Username</th>
              <th className="px-3 py-2 font-medium">Email</th>
              <th className="px-3 py-2 font-medium">Role</th>
              <th className="px-3 py-2 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const lastAdmin = row.role === "admin" && adminCount <= 1;
              return (
                <tr key={row.id} className="border-t border-black/5">
                  <td className="px-3 py-2 font-medium">
                    {row.username}
                    {row.id === user?.id ? <span className="ml-1 text-xs text-muted">(you)</span> : null}
                  </td>
                  <td className="px-3 py-2">{row.email}</td>
                  <td className="px-3 py-2">{row.role === "admin" ? "Administrator" : "Standard user"}</td>
                  <td className="px-3 py-2">
                    {row.role === "admin" ? (
                      <button
                        type="button"
                        className="text-moss underline disabled:text-muted disabled:no-underline"
                        disabled={lastAdmin || busyId === row.id}
                        onClick={() => void onRole(row, "user")}
                      >
                        Remove administrator
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="text-moss underline disabled:text-muted"
                        disabled={busyId === row.id}
                        onClick={() => void onRole(row, "admin")}
                      >
                        Make administrator
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
