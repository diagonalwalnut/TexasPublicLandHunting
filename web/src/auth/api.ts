// REST-style base. The PHP router accepts both "/api/<action>" and the legacy
// "/api/index.php?action=<action>" form, so this works against the local PHP
// dev server and the Lambda Function URL behind CloudFront.
const API_BASE = "/api/";

export type Account = {
  id: string;
  username: string;
  email: string;
  role?: "admin" | "user";
  betas?: string[];
};

export type BetaFeature = {
  id: string;
  label: string;
};

export type ManagedUser = {
  id: string;
  username: string;
  email: string;
  role: "admin" | "user";
  betas: string[];
  created_at: number;
};

export type AuthPayload = {
  user: Account | null;
  favorites: string[];
  csrf: string | null;
};

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

// CloudFront signs POST bodies to the Lambda Function URL. Lambda rejects the
// call unless the browser sends the SHA-256 of those exact bytes.
async function sha256Hex(text: string): Promise<string | null> {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) return null;
  const digest = await subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const action = path.replace(/^\//, "");
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const method = (init.method ?? "GET").toUpperCase();
  if (method !== "GET" && method !== "HEAD") {
    const hash = await sha256Hex(typeof init.body === "string" ? init.body : "");
    if (hash) headers.set("x-amz-content-sha256", hash);
  }
  if (init.method && init.method !== "GET" && action !== "signup" && action !== "signin" && action !== "signout") {
    if (csrfToken) headers.set("X-CSRF-Token", csrfToken);
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${action}`, {
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
    user: data.user ?? null,
    favorites: Array.isArray(data.favorites) ? data.favorites : [],
    csrf: data.csrf ?? null,
  };
}

export async function signUpAccount(input: {
  username: string;
  email: string;
  password: string;
}): Promise<AuthPayload> {
  return request<AuthPayload>("/signup", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function signInAccount(input: { login: string; password: string }): Promise<AuthPayload> {
  return request<AuthPayload>("/signin", {
    method: "POST",
    body: JSON.stringify(input),
  });
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
  return data.user;
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

export async function fetchAdminUsers(): Promise<{ users: ManagedUser[]; betas: BetaFeature[] }> {
  const data = await request<{ users?: ManagedUser[]; betas?: BetaFeature[] }>("/admin/users");
  return {
    users: Array.isArray(data.users) ? data.users : [],
    betas: Array.isArray(data.betas) ? data.betas : [],
  };
}

export async function updateAdminUser(input: {
  user_id: string;
  role?: "admin" | "user";
  betas?: string[];
}): Promise<ManagedUser> {
  const data = await request<{ user: ManagedUser }>("/admin/users/update", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return data.user;
}

export async function deleteAdminUser(userId: string): Promise<void> {
  await request<{ ok: boolean }>("/admin/users/delete", {
    method: "POST",
    body: JSON.stringify({ user_id: userId }),
  });
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
