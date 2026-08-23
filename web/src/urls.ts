const ALLOWED_HOSTS = new Set(["tpwd.texas.gov", "www.tpwd.texas.gov"]);

/** Allow only HTTPS TPWD URLs for hrefs built from compiled data. */
export function safeExternalUrl(url: string | undefined | null): string | undefined {
  if (!url) return undefined;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:") return undefined;
    if (parsed.username || parsed.password) return undefined;
    if (!ALLOWED_HOSTS.has(parsed.hostname.toLowerCase())) return undefined;
    return parsed.href;
  } catch {
    return undefined;
  }
}
