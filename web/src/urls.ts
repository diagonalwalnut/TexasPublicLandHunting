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
  "wildlife.dgf.nm.gov",
  "onlinesales.wildlife.dgf.nm.gov",
  "cpw.state.co.us",
  "www.cpw.state.co.us",
  "www.cpwshop.com",
  "cpwshop.com",
  "www.wlf.louisiana.gov",
  "wlf.louisiana.gov",
  "louisianaoutdoors.com",
  "www.louisianaoutdoors.com",
  "www.agfc.com",
  "agfc.com",
  "www.wildlifedepartment.com",
  "wildlifedepartment.com",
  "gooutdoorsoklahoma.com",
  "www.gooutdoorsoklahoma.com",
  "www.recreation.gov",
  "recreation.gov",
  "www.swf-wc.usace.army.mil",
  "www.swt-wc.usace.army.mil",
  "www.mvk.usace.army.mil",
  "www.mvr.usace.army.mil",
  "www.spa.usace.army.mil",
  "www.nwo.usace.army.mil",
  "www.nwp.usace.army.mil",
  "nwp.usace.army.mil",
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
