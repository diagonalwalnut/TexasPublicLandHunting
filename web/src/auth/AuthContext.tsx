import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  addFavorite,
  fetchMe,
  listUsers,
  probeApi,
  removeFavorite,
  setBetaEnabled,
  setUserRole,
  signInAccount,
  signOutAccount,
  signUpAccount,
  updateAccountUsername,
  type Account,
  type ManagedUser,
} from "./api";
import {
  GENERIC_LOGIN_ERROR,
  isValidUnitId,
  normalizeEmail,
  normalizeUsername,
  validateEmail,
  validateSignUp,
  validateUsername,
} from "./rules";

export type Profile = {
  user_id: string;
  username: string;
};

type AuthMode = "signin" | "signup";

type AuthContextValue = {
  configured: boolean;
  loading: boolean;
  user: Account | null;
  isAdmin: boolean;
  betaEnabled: boolean;
  profile: Profile | null;
  favoriteIds: ReadonlySet<string>;
  authOpen: boolean;
  authMode: AuthMode;
  cooldownSeconds: number;
  notice: string | null;
  openAuth: (mode?: AuthMode) => void;
  closeAuth: () => void;
  signIn: (login: string, password: string) => Promise<string | null>;
  signUp: (email: string, password: string, username: string) => Promise<string | null>;
  signOut: () => Promise<void>;
  toggleFavorite: (unitId: string) => Promise<string | null>;
  isFavorite: (unitId: string) => boolean;
  updateUsername: (username: string) => Promise<string | null>;
  setBeta: (enabled: boolean) => Promise<string | null>;
  loadUsers: () => Promise<ManagedUser[] | string>;
  changeUserRole: (userId: string, role: "user" | "admin") => Promise<ManagedUser[] | string>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const FAIL_KEY = "tplh_auth_failures";

type FailState = { n: number; until: number };

function readFail(): FailState {
  try {
    const raw = sessionStorage.getItem(FAIL_KEY);
    if (!raw) return { n: 0, until: 0 };
    const parsed = JSON.parse(raw) as FailState;
    return { n: Number(parsed.n) || 0, until: Number(parsed.until) || 0 };
  } catch {
    return { n: 0, until: 0 };
  }
}

function writeFail(state: FailState) {
  sessionStorage.setItem(FAIL_KEY, JSON.stringify(state));
}

function cooldownSecondsFrom(until: number): number {
  return Math.max(0, Math.ceil((until - Date.now()) / 1000));
}

function recordFailure(): FailState {
  const prev = readFail();
  const n = prev.n + 1;
  const extra = n >= 3 ? Math.min(60, 8 * 2 ** Math.min(n - 3, 3)) : 0;
  const next = { n, until: extra ? Date.now() + extra * 1000 : 0 };
  writeFail(next);
  return next;
}

function clearFailures() {
  sessionStorage.removeItem(FAIL_KEY);
}

function profileFrom(user: Account | null): Profile | null {
  if (!user) return null;
  return { user_id: user.id, username: user.username };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [configured, setConfigured] = useState(true);
  const [user, setUser] = useState<Account | null>(null);
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(() => new Set());
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>("signin");
  const [cooldownSeconds, setCooldownSeconds] = useState(() => cooldownSecondsFrom(readFail().until));
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const ok = await probeApi();
      if (cancelled) return;
      setConfigured(ok);
      if (!ok) {
        setLoading(false);
        return;
      }
      try {
        const me = await fetchMe();
        if (cancelled) return;
        setUser(me.user);
        setFavoriteIds(new Set(me.favorites.filter(isValidUnitId)));
      } catch {
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (cooldownSeconds <= 0) return;
    const id = window.setInterval(() => {
      setCooldownSeconds(cooldownSecondsFrom(readFail().until));
    }, 500);
    return () => window.clearInterval(id);
  }, [cooldownSeconds]);

  const openAuth = useCallback((mode: AuthMode = "signin") => {
    setNotice(null);
    setAuthMode(mode);
    setAuthOpen(true);
  }, []);

  const closeAuth = useCallback(() => {
    setAuthOpen(false);
    setNotice(null);
  }, []);

  const applyPayload = useCallback((payload: { user: Account | null; favorites: string[] }) => {
    setUser(payload.user);
    setFavoriteIds(new Set(payload.favorites.filter(isValidUnitId)));
  }, []);

  const signIn = useCallback(
    async (login: string, password: string) => {
      if (!configured) return "Accounts are not available on this host yet. The map still works.";
      const wait = cooldownSecondsFrom(readFail().until);
      if (wait > 0) {
        setCooldownSeconds(wait);
        return `Too many attempts. Try again in ${wait}s.`;
      }
      const identifier = login.includes("@") ? normalizeEmail(login) : normalizeUsername(login);
      if (!identifier || (identifier.includes("@") && validateEmail(identifier))) {
        recordFailure();
        setCooldownSeconds(cooldownSecondsFrom(readFail().until));
        return GENERIC_LOGIN_ERROR;
      }
      try {
        const payload = await signInAccount({ login: identifier, password });
        clearFailures();
        setCooldownSeconds(0);
        applyPayload(payload);
        setAuthOpen(false);
        setNotice(null);
        return null;
      } catch (err) {
        recordFailure();
        setCooldownSeconds(cooldownSecondsFrom(readFail().until));
        return err instanceof Error ? err.message : GENERIC_LOGIN_ERROR;
      }
    },
    [applyPayload, configured],
  );

  const signUp = useCallback(
    async (email: string, password: string, username: string) => {
      if (!configured) return "Accounts are not available on this host yet. The map still works.";
      const emailNorm = normalizeEmail(email);
      const userNorm = normalizeUsername(username);
      const localError = validateSignUp({ email: emailNorm, password, username: userNorm });
      if (localError) return localError;
      try {
        const payload = await signUpAccount({ username: userNorm, email: emailNorm, password });
        applyPayload(payload);
        setAuthOpen(false);
        setNotice(null);
        return null;
      } catch (err) {
        return err instanceof Error ? err.message : "Could not create that account. Try again.";
      }
    },
    [applyPayload, configured],
  );

  const signOut = useCallback(async () => {
    try {
      await signOutAccount();
    } catch {
      /* still clear local state */
    }
    setUser(null);
    setFavoriteIds(new Set());
    setNotice(null);
  }, []);

  const toggleFavorite = useCallback(
    async (unitId: string) => {
      if (!configured) return "Accounts are not available on this host yet.";
      if (!user) {
        openAuth("signin");
        return "Sign in to save units.";
      }
      if (!isValidUnitId(unitId)) return "That unit cannot be saved.";
      const was = favoriteIds.has(unitId);
      setFavoriteIds((prev) => {
        const next = new Set(prev);
        if (was) next.delete(unitId);
        else next.add(unitId);
        return next;
      });
      try {
        const next = was ? await removeFavorite(unitId) : await addFavorite(unitId);
        setFavoriteIds(new Set(next.filter(isValidUnitId)));
        return null;
      } catch {
        setFavoriteIds((prev) => {
          const next = new Set(prev);
          if (was) next.add(unitId);
          else next.delete(unitId);
          return next;
        });
        return "Could not update saved units.";
      }
    },
    [configured, favoriteIds, openAuth, user],
  );

  const isFavorite = useCallback((unitId: string) => favoriteIds.has(unitId), [favoriteIds]);

  const updateUsername = useCallback(
    async (username: string) => {
      if (!configured || !user) return "Sign in to continue.";
      const userNorm = normalizeUsername(username);
      const localError = validateUsername(userNorm);
      if (localError) return localError;
      try {
        const next = await updateAccountUsername(userNorm);
        setUser(next);
        return null;
      } catch (err) {
        return err instanceof Error ? err.message : "Could not save username. Try another.";
      }
    },
    [configured, user],
  );

  const setBeta = useCallback(
    async (enabled: boolean) => {
      if (!configured || !user || user.role !== "admin") return "Only administrators can use beta features.";
      const previous = user;
      setUser({ ...user, betaEnabled: enabled });
      try {
        const next = await setBetaEnabled(enabled);
        setUser(next);
        return null;
      } catch (err) {
        setUser(previous);
        return err instanceof Error ? err.message : "Could not update beta mode.";
      }
    },
    [configured, user],
  );

  const loadUsers = useCallback(async () => {
    if (!configured || !user || user.role !== "admin") return "Only administrators can manage users.";
    try {
      return await listUsers();
    } catch (err) {
      return err instanceof Error ? err.message : "Could not load users.";
    }
  }, [configured, user]);

  const changeUserRole = useCallback(
    async (userId: string, role: "user" | "admin") => {
      if (!configured || !user || user.role !== "admin") return "Only administrators can manage users.";
      try {
        const users = await setUserRole(userId, role);
        if (userId === user.id) {
          const self = users.find((row) => row.id === user.id);
          if (self) {
            setUser({
              ...user,
              role: self.role,
              betaEnabled: self.role === "admin" && user.betaEnabled,
            });
          }
        }
        return users;
      } catch (err) {
        return err instanceof Error ? err.message : "Could not update that role.";
      }
    },
    [configured, user],
  );

  const profile = profileFrom(user);
  const isAdmin = user?.role === "admin";
  const betaEnabled = Boolean(isAdmin && user?.betaEnabled);

  const value = useMemo<AuthContextValue>(
    () => ({
      configured,
      loading,
      user,
      isAdmin,
      betaEnabled,
      profile,
      favoriteIds,
      authOpen,
      authMode,
      cooldownSeconds,
      notice,
      openAuth,
      closeAuth,
      signIn,
      signUp,
      signOut,
      toggleFavorite,
      isFavorite,
      updateUsername,
      setBeta,
      loadUsers,
      changeUserRole,
    }),
    [
      configured,
      loading,
      user,
      isAdmin,
      betaEnabled,
      profile,
      favoriteIds,
      authOpen,
      authMode,
      cooldownSeconds,
      notice,
      openAuth,
      closeAuth,
      signIn,
      signUp,
      signOut,
      toggleFavorite,
      isFavorite,
      updateUsername,
      setBeta,
      loadUsers,
      changeUserRole,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
