const ALLOWED_HOSTS = new Set([
  "tpwd.texas.gov",
  "www.tpwd.texas.gov",
  "myodfw.com",
  "www.myodfw.com",
  "dfw.state.or.us",
  "www.dfw.state.or.us",
  "nrimp.dfw.state.or.us",
  "eregulations.com",
  "www.eregulations.com",
]);

/** Allow only HTTPS links to the agencies this planner cites. */
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
