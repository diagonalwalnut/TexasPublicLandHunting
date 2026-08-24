const API_BASE = "/api/index.php?action=";

export type Account = {
  id: string;
  username: string;
  email: string;
  role: "user" | "admin";
  betaEnabled: boolean;
};

export type AuthPayload = {
  user: Account | null;
  favorites: string[];
  csrf: string | null;
};

export type ManagedUser = {
  id: string;
  username: string;
  email: string;
  role: "user" | "admin";
  betaEnabled: boolean;
  createdAt: number;
};

function asAccount(user: Account | null): Account | null {
  if (!user) return null;
  return {
    id: user.id,
    username: user.username,
    email: user.email,
    role: user.role === "admin" ? "admin" : "user",
    betaEnabled: user.role === "admin" && Boolean(user.betaEnabled),
  };
}

let csrfToken = "";

export function currentCsrf(): string {
  return csrfToken;
}

function rememberCsrf(csrf: string | null | undefined) {
  if (typeof csrf === "string" && csrf.length > 0) csrfToken = csrf;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function readError(res: Response): Promise<string> {
  try {
    const data = (await res.json()) as { error?: string };
    if (data.error) return data.error;
  } catch {
    /* not JSON */
  }
  if (res.status === 404 || res.status === 405) {
    return "Accounts are not available on this host yet.";
  }
  if (res.status === 429) return "Too many attempts. Try again later.";
  return "Something went wrong. Try again.";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const action = path.replace(/^\//, "");
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (init.method && init.method !== "GET" && action !== "signup" && action !== "signin" && action !== "signout") {
    if (csrfToken) headers.set("X-CSRF-Token", csrfToken);
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${encodeURIComponent(action)}`, {
      ...init,
      headers,
      credentials: "include",
    });
  } catch {
    throw new ApiError(0, "Could not reach the accounts service.");
  }
  if (!res.ok) {
    throw new ApiError(res.status, await readError(res));
  }
  const data = (await res.json()) as T;
  if (data && typeof data === "object" && "csrf" in data) {
    rememberCsrf((data as { csrf?: string | null }).csrf);
  }
  return data;
}

export async function fetchMe(): Promise<AuthPayload> {
  const data = await request<AuthPayload>("/me");
  return {
    user: asAccount(data.user ?? null),
    favorites: Array.isArray(data.favorites) ? data.favorites : [],
    csrf: data.csrf ?? null,
  };
}

export async function signUpAccount(input: {
  username: string;
  email: string;
  password: string;
}): Promise<AuthPayload> {
  const data = await request<AuthPayload>("/signup", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return { ...data, user: asAccount(data.user) };
}

export async function signInAccount(input: { login: string; password: string }): Promise<AuthPayload> {
  const data = await request<AuthPayload>("/signin", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return { ...data, user: asAccount(data.user) };
}

export async function signOutAccount(): Promise<void> {
  await request<{ ok: boolean }>("/signout", { method: "POST" });
  csrfToken = "";
}

export async function updateAccountUsername(username: string): Promise<Account> {
  const data = await request<{ user: Account }>("/username", {
    method: "POST",
    body: JSON.stringify({ username }),
  });
  const next = asAccount(data.user);
  if (!next) throw new ApiError(500, "Could not save username. Try another.");
  return next;
}

export async function addFavorite(unitId: string): Promise<string[]> {
  const data = await request<{ favorites: string[] }>("/favorites", {
    method: "POST",
    body: JSON.stringify({ unit_id: unitId }),
  });
  return data.favorites;
}

export async function removeFavorite(unitId: string): Promise<string[]> {
  const data = await request<{ favorites: string[] }>("/favorites/delete", {
    method: "POST",
    body: JSON.stringify({ unit_id: unitId }),
  });
  return data.favorites;
}

export async function setBetaEnabled(enabled: boolean): Promise<Account> {
  const data = await request<{ user: Account }>("/beta", {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
  const user = asAccount(data.user);
  if (!user) throw new ApiError(500, "Could not update beta mode.");
  return user;
}

export async function listUsers(): Promise<ManagedUser[]> {
  const data = await request<{ users: ManagedUser[] }>("/users");
  return Array.isArray(data.users) ? data.users : [];
}

export async function setUserRole(userId: string, role: "user" | "admin"): Promise<ManagedUser[]> {
  const data = await request<{ users: ManagedUser[] }>("/users/role", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, role }),
  });
  return Array.isArray(data.users) ? data.users : [];
}

export async function probeApi(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}health`, { credentials: "include" });
    if (!res.ok) return false;
    const data = (await res.json()) as { ok?: boolean };
    return data.ok === true;
  } catch {
    return false;
  }
}
