import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { User } from "@supabase/supabase-js";
import {
  GENERIC_LOGIN_ERROR,
  isGeneratedUsername,
  isValidUnitId,
  normalizeEmail,
  normalizeUsername,
  validateEmail,
  validateSignUp,
  validateUsername,
} from "./rules";
import { authRedirectTo, isAuthConfigured, supabase } from "./supabase";

export type Profile = {
  user_id: string;
  username: string;
};

type AuthMode = "signin" | "signup";

type AuthContextValue = {
  configured: boolean;
  loading: boolean;
  user: User | null;
  profile: Profile | null;
  favoriteIds: ReadonlySet<string>;
  authOpen: boolean;
  authMode: AuthMode;
  cooldownSeconds: number;
  needsUsername: boolean;
  notice: string | null;
  openAuth: (mode?: AuthMode) => void;
  closeAuth: () => void;
  signIn: (email: string, password: string) => Promise<string | null>;
  signUp: (email: string, password: string, username: string) => Promise<string | null>;
  signInWithGoogle: () => Promise<string | null>;
  signInWithMicrosoft: () => Promise<string | null>;
  signOut: () => Promise<void>;
  toggleFavorite: (unitId: string) => Promise<string | null>;
  isFavorite: (unitId: string) => boolean;
  updateUsername: (username: string) => Promise<string | null>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const FAIL_KEY = "tplh_auth_failures";
const NOT_CONFIGURED =
  "Accounts are not configured on this deployment yet. The map still works without signing in.";

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

async function usernameIsTaken(username: string): Promise<boolean> {
  if (!supabase) return false;
  const { data, error } = await supabase.rpc("username_taken", { p_username: username });
  if (error) throw error;
  return Boolean(data);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(isAuthConfigured);
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(() => new Set());
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<AuthMode>("signin");
  const [cooldownSeconds, setCooldownSeconds] = useState(() => cooldownSecondsFrom(readFail().until));
  const [notice, setNotice] = useState<string | null>(null);
  const promptedUsername = useRef(false);

  const loadAccount = useCallback(async (sessionUser: User | null) => {
    if (!supabase || !sessionUser) {
      setProfile(null);
      setFavoriteIds(new Set());
      return;
    }
    const [{ data: profileRow }, { data: favRows }] = await Promise.all([
      supabase.from("profiles").select("user_id, username").eq("user_id", sessionUser.id).maybeSingle(),
      supabase.from("favorites").select("unit_id"),
    ]);
    if (profileRow?.username) {
      setProfile({ user_id: profileRow.user_id as string, username: profileRow.username as string });
    } else {
      const metaName = normalizeUsername(String(sessionUser.user_metadata?.username ?? ""));
      const fallback =
        validateUsername(metaName) === null
          ? metaName
          : `user_${sessionUser.id.replaceAll("-", "").slice(0, 12)}`;
      const { data: inserted } = await supabase
        .from("profiles")
        .insert({ user_id: sessionUser.id, username: fallback })
        .select("user_id, username")
        .maybeSingle();
      if (inserted?.username) {
        setProfile({ user_id: inserted.user_id as string, username: inserted.username as string });
      } else {
        setProfile(null);
      }
    }
    const ids = new Set<string>();
    for (const row of favRows ?? []) {
      if (typeof row.unit_id === "string" && isValidUnitId(row.unit_id)) ids.add(row.unit_id);
    }
    setFavoriteIds(ids);
  }, []);

  useEffect(() => {
    if (!supabase) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    void supabase.auth.getSession().then(({ data }) => {
      if (cancelled) return;
      const nextUser = data.session?.user ?? null;
      setUser(nextUser);
      void loadAccount(nextUser).finally(() => {
        if (!cancelled) setLoading(false);
      });
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      setUser(session?.user ?? null);
      void loadAccount(session?.user ?? null);
    });
    return () => {
      cancelled = true;
      sub.subscription.unsubscribe();
    };
  }, [loadAccount]);

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

  const signIn = useCallback(async (email: string, password: string) => {
    if (!supabase) return NOT_CONFIGURED;
    const wait = cooldownSecondsFrom(readFail().until);
    if (wait > 0) {
      setCooldownSeconds(wait);
      return `Too many attempts. Try again in ${wait}s.`;
    }
    const emailNorm = normalizeEmail(email);
    if (validateEmail(emailNorm)) {
      recordFailure();
      setCooldownSeconds(cooldownSecondsFrom(readFail().until));
      return GENERIC_LOGIN_ERROR;
    }
    const { error } = await supabase.auth.signInWithPassword({ email: emailNorm, password });
    if (error) {
      recordFailure();
      setCooldownSeconds(cooldownSecondsFrom(readFail().until));
      return GENERIC_LOGIN_ERROR;
    }
    clearFailures();
    setCooldownSeconds(0);
    setAuthOpen(false);
    setNotice(null);
    return null;
  }, []);

  const signUp = useCallback(async (email: string, password: string, username: string) => {
    if (!supabase) return NOT_CONFIGURED;
    const emailNorm = normalizeEmail(email);
    const userNorm = normalizeUsername(username);
    const localError = validateSignUp({ email: emailNorm, password, username: userNorm });
    if (localError) return localError;
    try {
      if (await usernameIsTaken(userNorm)) return "That username is already taken.";
    } catch {
      return "Could not check username availability. Try again.";
    }
    const { data, error } = await supabase.auth.signUp({
      email: emailNorm,
      password,
      options: {
        data: { username: userNorm },
        emailRedirectTo: authRedirectTo(),
      },
    });
    if (error) {
      return "If this email can be used, you will get a confirmation message. Otherwise try signing in.";
    }
    if (!data.session) {
      setNotice("Check your email to confirm your account before signing in.");
      setAuthMode("signin");
      return null;
    }
    setAuthOpen(false);
    setNotice(null);
    return null;
  }, []);

  const startOAuth = useCallback(async (provider: "google" | "azure") => {
    if (!supabase) return NOT_CONFIGURED;
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: {
        redirectTo: authRedirectTo(),
        skipBrowserRedirect: false,
        scopes: provider === "azure" ? "email" : undefined,
      },
    });
    if (error) return "Could not start sign-in. Try email and password, or try again.";
    return null;
  }, []);

  const signInWithGoogle = useCallback(() => startOAuth("google"), [startOAuth]);
  const signInWithMicrosoft = useCallback(() => startOAuth("azure"), [startOAuth]);

  const signOut = useCallback(async () => {
    if (!supabase) return;
    await supabase.auth.signOut();
    setUser(null);
    setProfile(null);
    setFavoriteIds(new Set());
    setNotice(null);
    promptedUsername.current = false;
  }, []);

  const toggleFavorite = useCallback(
    async (unitId: string) => {
      if (!supabase) return NOT_CONFIGURED;
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
      if (was) {
        const { error } = await supabase.from("favorites").delete().eq("user_id", user.id).eq("unit_id", unitId);
        if (error) {
          setFavoriteIds((prev) => new Set(prev).add(unitId));
          return "Could not update saved units.";
        }
      } else {
        const { error } = await supabase.from("favorites").insert({ user_id: user.id, unit_id: unitId });
        if (error) {
          setFavoriteIds((prev) => {
            const next = new Set(prev);
            next.delete(unitId);
            return next;
          });
          return "Could not update saved units.";
        }
      }
      return null;
    },
    [favoriteIds, openAuth, user],
  );

  const isFavorite = useCallback((unitId: string) => favoriteIds.has(unitId), [favoriteIds]);

  const updateUsername = useCallback(
    async (username: string) => {
      if (!supabase || !user) return NOT_CONFIGURED;
      const userNorm = normalizeUsername(username);
      const localError = validateUsername(userNorm);
      if (localError) return localError;
      try {
        if (await usernameIsTaken(userNorm)) return "That username is already taken.";
      } catch {
        return "Could not check username availability. Try again.";
      }
      const { error } = await supabase.from("profiles").update({ username: userNorm }).eq("user_id", user.id);
      if (error) return "Could not save username. Try another.";
      setProfile({ user_id: user.id, username: userNorm });
      return null;
    },
    [user],
  );

  const needsUsername = Boolean(profile && isGeneratedUsername(profile.username));

  useEffect(() => {
    if (user && needsUsername && !promptedUsername.current) {
      promptedUsername.current = true;
      setAuthOpen(true);
    }
    if (!user) promptedUsername.current = false;
  }, [user, needsUsername]);

  const value = useMemo<AuthContextValue>(
    () => ({
      configured: isAuthConfigured,
      loading,
      user,
      profile,
      favoriteIds,
      authOpen,
      authMode,
      cooldownSeconds,
      needsUsername,
      notice,
      openAuth,
      closeAuth,
      signIn,
      signUp,
      signInWithGoogle,
      signInWithMicrosoft,
      signOut,
      toggleFavorite,
      isFavorite,
      updateUsername,
    }),
    [
      loading,
      user,
      profile,
      favoriteIds,
      authOpen,
      authMode,
      cooldownSeconds,
      needsUsername,
      notice,
      openAuth,
      closeAuth,
      signIn,
      signUp,
      signInWithGoogle,
      signInWithMicrosoft,
      signOut,
      toggleFavorite,
      isFavorite,
      updateUsername,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
