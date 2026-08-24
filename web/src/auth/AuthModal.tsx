import { useEffect, useId, useState, type FormEvent } from "react";
import { useAuth } from "./AuthContext";
import { PASSWORD_MAX_BYTES, PASSWORD_MIN, USERNAME_MAX, USERNAME_MIN } from "./rules";

export default function AuthModal() {
  const {
    configured,
    authOpen,
    authMode,
    closeAuth,
    openAuth,
    signIn,
    signUp,
    cooldownSeconds,
    notice,
  } = useAuth();
  const [login, setLogin] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const emailId = useId();
  const loginId = useId();
  const passwordId = useId();
  const usernameId = useId();

  useEffect(() => {
    if (!authOpen) {
      setLogin("");
      setEmail("");
      setPassword("");
      setUsername("");
      setError(null);
      setBusy(false);
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

  if (!authOpen) return null;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    const result =
      authMode === "signup" ? await signUp(email, password, username) : await signIn(login, password);
    setBusy(false);
    if (result) setError(result);
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
              Accounts not available
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-muted">
              The map and hunt report still work. Sign-in needs the accounts service on this host.
            </p>
            <button
              type="button"
              className="mt-4 rounded-md bg-pine px-3 py-2 text-sm text-sand"
              onClick={closeAuth}
            >
              Close
            </button>
          </>
        ) : (
          <>
            <h2 id="auth-title" className="font-serif text-xl font-semibold">
              {authMode === "signup" ? "Create account" : "Sign in"}
            </h2>
            <p className="mt-1 text-sm text-muted">
              {authMode === "signup"
                ? "Pick a username, email, and password. Passwords are stored as a one-way hash, never as plain text."
                : "Use your username or email, and your password."}
            </p>
            {notice ? <p className="mt-2 text-sm text-moss">{notice}</p> : null}

            <form className="mt-4 space-y-3" onSubmit={onSubmit}>
              {authMode === "signup" ? (
                <label className="block text-sm" htmlFor={usernameId}>
                  Username
                  <input
                    id={usernameId}
                    className="mt-1 w-full rounded-md border border-black/15 px-2 py-1.5"
                    autoComplete="username"
                    spellCheck={false}
                    maxLength={USERNAME_MAX}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder={`${USERNAME_MIN}–${USERNAME_MAX} letters, numbers, _`}
                  />
                </label>
              ) : (
                <label className="block text-sm" htmlFor={loginId}>
                  Username or email
                  <input
                    id={loginId}
                    className="mt-1 w-full rounded-md border border-black/15 px-2 py-1.5"
                    autoComplete="username"
                    spellCheck={false}
                    maxLength={254}
                    value={login}
                    onChange={(e) => setLogin(e.target.value)}
                  />
                </label>
              )}
              {authMode === "signup" ? (
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
              ) : null}
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
                  At least {PASSWORD_MIN} characters, at most {PASSWORD_MAX_BYTES} bytes. Paste is
                  allowed.
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
