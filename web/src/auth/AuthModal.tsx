import { useEffect, useId, useState, type FormEvent } from "react";
import { useAuth } from "./AuthContext";
import { AUTH_AND_SAVES_ENABLED } from "./features";
import { PASSWORD_MIN, USERNAME_MAX, USERNAME_MIN } from "./rules";

export default function AuthModal() {
  const {
    configured,
    authOpen,
    authMode,
    closeAuth,
    openAuth,
    signIn,
    signUp,
    signInWithGoogle,
    signInWithMicrosoft,
    cooldownSeconds,
    notice,
    needsUsername,
    user,
    updateUsername,
    profile,
  } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pickedName, setPickedName] = useState("");
  const emailId = useId();
  const passwordId = useId();
  const usernameId = useId();

  const showPickUsername = Boolean(user && needsUsername && authOpen);

  useEffect(() => {
    if (!authOpen) {
      setEmail("");
      setPassword("");
      setUsername("");
      setError(null);
      setBusy(false);
      setPickedName("");
    }
  }, [authOpen, authMode]);

  useEffect(() => {
    if (!authOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeAuth();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [authOpen, closeAuth]);

  if (!AUTH_AND_SAVES_ENABLED || !authOpen) return null;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const result =
      authMode === "signup" ? await signUp(email, password, username) : await signIn(email, password);
    setBusy(false);
    if (result) setError(result);
  };

  const onOAuth = async (which: "google" | "microsoft") => {
    setError(null);
    setBusy(true);
    const result = which === "google" ? await signInWithGoogle() : await signInWithMicrosoft();
    setBusy(false);
    if (result) setError(result);
  };

  const onPickUsername = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const result = await updateUsername(pickedName);
    setBusy(false);
    if (result) setError(result);
    else closeAuth();
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-4 sm:items-center"
      role="presentation"
      onClick={closeAuth}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-title"
        className="w-full max-w-md rounded-lg bg-white p-5 text-ink shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {!configured ? (
          <>
            <h2 id="auth-title" className="font-serif text-xl font-semibold">
              Accounts not configured
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-muted">
              Email, Google, and Microsoft sign-in need a Supabase project. Set{" "}
              <code className="text-ink">VITE_SUPABASE_URL</code> and{" "}
              <code className="text-ink">VITE_SUPABASE_ANON_KEY</code> (see the README), then rebuild.
              The map and hunt report still work without an account.
            </p>
            <button
              type="button"
              className="mt-4 rounded-md bg-pine px-3 py-2 text-sm text-sand"
              onClick={closeAuth}
            >
              Close
            </button>
          </>
        ) : showPickUsername ? (
          <>
            <h2 id="auth-title" className="font-serif text-xl font-semibold">
              Choose a username
            </h2>
            <p className="mt-1 text-sm text-muted">
              This is a public handle, not your login. Your current handle is{" "}
              <span className="text-ink">{profile?.username}</span>.
            </p>
            <form className="mt-4 space-y-3" onSubmit={onPickUsername}>
              <label className="block text-sm" htmlFor={`${usernameId}-pick`}>
                Username
                <input
                  id={`${usernameId}-pick`}
                  className="mt-1 w-full rounded-md border border-black/15 px-2 py-1.5"
                  autoComplete="nickname"
                  spellCheck={false}
                  maxLength={USERNAME_MAX}
                  value={pickedName}
                  onChange={(e) => setPickedName(e.target.value)}
                  placeholder={`${USERNAME_MIN}–${USERNAME_MAX} letters, numbers, _`}
                />
              </label>
              {error ? <p className="text-sm text-red-800">{error}</p> : null}
              <div className="flex justify-end gap-2">
                <button type="button" className="rounded-md px-3 py-2 text-sm text-muted" onClick={closeAuth}>
                  Skip
                </button>
                <button
                  type="submit"
                  className="rounded-md bg-pine px-3 py-2 text-sm text-sand disabled:opacity-60"
                  disabled={busy}
                >
                  Save
                </button>
              </div>
            </form>
          </>
        ) : (
          <>
            <h2 id="auth-title" className="font-serif text-xl font-semibold">
              {authMode === "signup" ? "Create account" : "Sign in"}
            </h2>
            <p className="mt-1 text-sm text-muted">
              {authMode === "signup"
                ? "Email is your login. Username is a public handle for this site."
                : "Use the email and password you registered, or continue with Google or Microsoft."}
            </p>
            {notice ? <p className="mt-2 text-sm text-moss">{notice}</p> : null}

            <form className="mt-4 space-y-3" onSubmit={onSubmit}>
              {authMode === "signup" ? (
                <label className="block text-sm" htmlFor={usernameId}>
                  Username
                  <input
                    id={usernameId}
                    className="mt-1 w-full rounded-md border border-black/15 px-2 py-1.5"
                    autoComplete="nickname"
                    spellCheck={false}
                    maxLength={USERNAME_MAX}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                  />
                </label>
              ) : null}
              <label className="block text-sm" htmlFor={emailId}>
                Email
                <input
                  id={emailId}
                  type="email"
                  className="mt-1 w-full rounded-md border border-black/15 px-2 py-1.5"
                  autoComplete="email"
                  inputMode="email"
                  maxLength={254}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </label>
              <label className="block text-sm" htmlFor={passwordId}>
                Password
                <input
                  id={passwordId}
                  type="password"
                  className="mt-1 w-full rounded-md border border-black/15 px-2 py-1.5"
                  autoComplete={authMode === "signup" ? "new-password" : "current-password"}
                  spellCheck={false}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={authMode === "signup" ? PASSWORD_MIN : undefined}
                />
              </label>
              {authMode === "signup" ? (
                <p className="text-xs text-muted">
                  At least {PASSWORD_MIN} characters, at most 72 bytes. Paste is allowed.
                </p>
              ) : null}
              {error ? <p className="text-sm text-red-800">{error}</p> : null}
              {cooldownSeconds > 0 ? (
                <p className="text-sm text-muted">Try again in {cooldownSeconds}s.</p>
              ) : null}
              <button
                type="submit"
                className="w-full rounded-md bg-pine px-3 py-2 text-sm text-sand disabled:opacity-60"
                disabled={busy || cooldownSeconds > 0}
              >
                {authMode === "signup" ? "Create account" : "Sign in"}
              </button>
            </form>

            <div className="mt-4 space-y-2">
              <button
                type="button"
                className="w-full rounded-md border border-black/15 px-3 py-2 text-sm hover:bg-sand disabled:opacity-60"
                disabled={busy}
                onClick={() => void onOAuth("google")}
              >
                Continue with Google
              </button>
              <button
                type="button"
                className="w-full rounded-md border border-black/15 px-3 py-2 text-sm hover:bg-sand disabled:opacity-60"
                disabled={busy}
                onClick={() => void onOAuth("microsoft")}
              >
                Continue with Microsoft
              </button>
            </div>

            <p className="mt-4 text-sm text-muted">
              {authMode === "signup" ? (
                <>
                  Already have an account?{" "}
                  <button type="button" className="text-moss underline" onClick={() => openAuth("signin")}>
                    Sign in
                  </button>
                </>
              ) : (
                <>
                  Need an account?{" "}
                  <button type="button" className="text-moss underline" onClick={() => openAuth("signup")}>
                    Create one
                  </button>
                </>
              )}
            </p>
            <button type="button" className="mt-2 text-sm text-muted underline" onClick={closeAuth}>
              Cancel
            </button>
          </>
        )}
      </div>
    </div>
  );
}
