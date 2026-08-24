import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL?.trim() ?? "";
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY?.trim() ?? "";

export const isAuthConfigured = url.startsWith("https://") && anonKey.length > 20;

export function authRedirectTo(): string {
  return new URL(import.meta.env.BASE_URL || "/", window.location.origin).toString();
}

export const supabase: SupabaseClient | null = isAuthConfigured
  ? createClient(url, anonKey, {
      auth: {
        flowType: "pkce",
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
      },
    })
  : null;

export type OAuthProviders = {
  google: boolean;
  microsoft: boolean;
};

export async function fetchOAuthProviders(): Promise<OAuthProviders> {
  if (!isAuthConfigured) return { google: false, microsoft: false };
  try {
    const res = await fetch(`${url}/auth/v1/settings`, {
      headers: { apikey: anonKey, Authorization: `Bearer ${anonKey}` },
    });
    if (!res.ok) return { google: isAuthConfigured, microsoft: false };
    const data = (await res.json()) as { external?: Record<string, { enabled?: boolean } | boolean> };
    const ext = data.external ?? {};
    const on = (key: string) => {
      const value = ext[key];
      if (typeof value === "boolean") return value;
      return Boolean(value && value.enabled);
    };
    return { google: on("google"), microsoft: on("azure") };
  } catch {
    return { google: isAuthConfigured, microsoft: false };
  }
}
