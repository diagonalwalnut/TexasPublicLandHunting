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
