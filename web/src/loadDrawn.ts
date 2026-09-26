import type { DrawnHunt, DrawnMeta } from "./types";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(url);
  return (await res.json()) as T;
}

/** Load drawn hunts from /data, then from the JS bundle if HostGator never got those files. */
export async function loadDrawnCatalog(): Promise<{ hunts: DrawnHunt[]; meta: DrawnMeta }> {
  try {
    const [hunts, meta] = await Promise.all([
      fetchJson<DrawnHunt[]>("/data/drawn_hunts.json"),
      fetchJson<DrawnMeta>("/data/drawn_meta.json"),
    ]);
    if (!Array.isArray(hunts) || hunts.length < 1 || !meta?.seasonYear) {
      throw new Error("drawn shape");
    }
    return { hunts, meta };
  } catch {
    const [huntsMod, metaMod] = await Promise.all([
      import("../public/data/drawn_hunts.json"),
      import("../public/data/drawn_meta.json"),
    ]);
    return {
      hunts: huntsMod.default as DrawnHunt[],
      meta: metaMod.default as DrawnMeta,
    };
  }
}
