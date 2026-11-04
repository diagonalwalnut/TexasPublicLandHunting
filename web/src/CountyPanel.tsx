import ExternalLink from "./ExternalLink";
import { formatRange } from "./filters";
import type { CountyAnimal, CountyHunting } from "./types";

type Side = "north" | "south";

const ROAD_PATTERNS: { re: RegExp; label: string }[] = [
  { re: /spur\s*239/i, label: "Spur 239" },
  { re: /loop\s*1604/i, label: "Loop 1604" },
  { re: /u\.?\s*s\.?\s*(highway|hwy\.?)?\s*90\b/i, label: "U.S. Highway 90" },
  { re: /\b(ih|i-)\s*10\b/i, label: "IH 10" },
];

const ROAD_ORDER = ["U.S. Highway 90", "Spur 239", "Loop 1604", "IH 10"];

// Counties the Outdoor Annual South Zone boundary cuts. IH 20 dove splits and
// sandhill-crane zones mention the same highways but stay in the season text.
const SPLIT_COUNTIES = new Set([
  "austin",
  "bexar",
  "caldwell",
  "chambers",
  "colorado",
  "fayette",
  "gonzales",
  "guadalupe",
  "harris",
  "jefferson",
  "kinney",
  "medina",
  "orange",
  "uvalde",
  "val-verde",
  "waller",
]);

function nsSide(portion: string): Side | null {
  if (!portion || !ROAD_PATTERNS.some((road) => road.re.test(portion))) return null;
  const text = portion.trim().toLowerCase();
  if (text.includes("southeastern portion")) return "south";
  if (/^(north|northeast|northwest) of\b/.test(text)) return "north";
  if (/^(south|southeast|southwest) of\b/.test(text)) return "south";
  const south = /\bsouth of\b/.test(text);
  const north = /\bnorth of\b/.test(text);
  if (south && !north) return "south";
  if (north && !south) return "north";
  return null;
}

function roadsIn(portion: string): string[] {
  return ROAD_PATTERNS.filter((road) => road.re.test(portion)).map((road) => road.label);
}

function sidesFor(animals: CountyAnimal[], slug: string | undefined): Map<CountyAnimal, Side | null> {
  const assigned = new Map<CountyAnimal, Side | null>();
  for (const animal of animals) assigned.set(animal, null);
  if (!slug || !SPLIT_COUNTIES.has(slug)) return assigned;
  for (const animal of animals) assigned.set(animal, nsSide(animal.portion || ""));
  const countyIsSplit = animals.some((animal) => assigned.get(animal));
  if (!countyIsSplit) return assigned;
  const bySpecies = new Map<string, CountyAnimal[]>();
  for (const animal of animals) {
    const list = bySpecies.get(animal.species) ?? [];
    list.push(animal);
    bySpecies.set(animal.species, list);
  }
  for (const rows of bySpecies.values()) {
    if (rows.some((animal) => assigned.get(animal))) continue;
    const zones = new Set(rows.map((animal) => animal.zone));
    if (!zones.has("North Zone") || !zones.has("South Zone")) continue;
    for (const animal of rows) {
      if (animal.zone === "North Zone") assigned.set(animal, "north");
      if (animal.zone === "South Zone") assigned.set(animal, "south");
    }
  }
  return assigned;
}

function zonePhrase(animals: CountyAnimal[], species: string, empty: string): string {
  const zones = [
    ...new Set(animals.filter((animal) => animal.species === species).map((animal) => animal.zone).filter(Boolean)),
  ];
  if (zones.length === 0) return empty;
  if (zones.length === 1) return zones[0];
  return zones.join(" and ");
}

function AnimalCard({ animal, showPortion }: { animal: CountyAnimal; showPortion: boolean }) {
  return (
    <li className="rounded bg-sand px-2 py-1.5 text-sm">
      <div className="font-medium">
        {animal.label}
        {animal.zone ? <span className="font-normal text-muted"> · {animal.zone}</span> : null}
        {showPortion && animal.portion ? (
          <span className="font-normal text-muted"> · {animal.portion}</span>
        ) : null}
      </div>
      {animal.bagLimit ? <p className="text-xs text-muted">{animal.bagLimit}</p> : null}
      {animal.antlerRestrictions ? (
        <p className="text-xs text-muted">Antler restrictions: {animal.antlerRestrictions}</p>
      ) : null}
      <ul className="mt-1 space-y-0.5 text-xs">
        {animal.seasons.length === 0 ? (
          <li>No open season</li>
        ) : (
          animal.seasons.map((season, index) => (
            <li key={`${season.title}-${index}`}>
              {season.title}: {season.windows.map((window) => formatRange(window.start, window.end)).join("; ")}
              {season.notes && season.notes !== animal.bagLimit ? (
                <span className="text-muted"> — {season.notes}</span>
              ) : null}
            </li>
          ))
        )}
      </ul>
    </li>
  );
}

export function CountyRegulations({
  page,
  hasPublicLand = true,
}: {
  page: CountyHunting;
  hasPublicLand?: boolean;
}) {
  const sides = sidesFor(page.animals, page.slug);
  const north = page.animals.filter((animal) => sides.get(animal) === "north");
  const south = page.animals.filter((animal) => sides.get(animal) === "south");
  const rest = page.animals.filter((animal) => !sides.get(animal));
  const split = north.length > 0 && south.length > 0;
  const roadLabels = [
    ...new Set(
      page.animals.flatMap((animal) => (sides.get(animal) ? roadsIn(animal.portion || "") : [])),
    ),
  ].sort((a, b) => ROAD_ORDER.indexOf(a) - ROAD_ORDER.indexOf(b));
  const roadText =
    roadLabels.length === 0
      ? ""
      : roadLabels.length === 1
        ? roadLabels[0]
        : `${roadLabels.slice(0, -1).join(", ")} and ${roadLabels[roadLabels.length - 1]}`;
  const deer = zonePhrase(page.animals, "white_tailed_deer", "No open season");
  const dove = zonePhrase(page.animals, "dove", "not listed");
  const ducks = zonePhrase(page.animals, "waterfowl", "not listed");

  const groups: { title: string; detail: string; animals: CountyAnimal[] }[] = [];
  if (split) {
    const northDetail = [...new Set(north.map((animal) => animal.portion).filter(Boolean))].join("; ");
    const southDetail = [...new Set(south.map((animal) => animal.portion).filter(Boolean))].join("; ");
    groups.push({ title: "North side", detail: northDetail, animals: north });
    groups.push({ title: "South side", detail: southDetail, animals: south });
    if (rest.length) groups.push({ title: "Entire county", detail: "", animals: rest });
  } else {
    groups.push({ title: "", detail: "", animals: page.animals });
  }

  return (
    <>
      {split ? (
        <p className="mb-2 text-sm font-medium text-pine">
          Split by {roadText}. North Zone and South Zone.
        </p>
      ) : null}
      <p className="mb-3 text-sm text-muted">
        White-tailed deer: {deer}
        {" · "}
        Dove: {dove}
        {" · "}
        Ducks: {ducks}
      </p>
      <ExternalLink className="mb-3 block text-sm font-semibold text-moss underline" href={page.url}>
        Outdoor Annual — {page.county} County
      </ExternalLink>
      {!hasPublicLand ? (
        <p className="mb-3 text-sm text-pine">
          No public hunting area is mapped in this county. The zone, dates, bag limits, and restrictions below
          are the county Outdoor Annual rules.
        </p>
      ) : null}
      <p className="mb-3 text-xs text-muted">
        Dates, bag limits, and zone lines are from the TPWD Outdoor Annual. Confirm them before you hunt.
      </p>
      {groups.map((group) => (
        <section key={group.title || "all"} className="mb-4">
          {group.title ? <h3 className="text-sm font-semibold">{group.title}</h3> : null}
          {group.detail ? <p className="mb-1 text-xs text-muted">{group.detail}</p> : null}
          <ul className="mt-1 space-y-2">
            {group.animals.map((animal, index) => {
              const portions = new Set(group.animals.map((item) => item.portion).filter(Boolean));
              const showPortion = !split || portions.size > 1 || group.title === "Entire county";
              return (
                <AnimalCard
                  key={`${animal.species}-${animal.zone}-${animal.portion || ""}-${index}`}
                  animal={animal}
                  showPortion={showPortion && Boolean(animal.portion)}
                />
              );
            })}
          </ul>
        </section>
      ))}
    </>
  );
}

export default function CountyPanel({
  page,
  hasPublicLand = true,
  onClose,
}: {
  page: CountyHunting;
  hasPublicLand?: boolean;
  onClose: () => void;
}) {
  return (
    <aside className="scrollbar-thin order-3 max-h-[40vh] w-full shrink-0 overflow-y-auto border-t border-black/10 bg-white p-4 md:max-h-none md:w-96 md:border-l md:border-t-0">
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted">County regulations</p>
          <h2 className="font-serif text-xl font-semibold">{page.county} County</h2>
        </div>
        <button type="button" className="text-muted" onClick={onClose} aria-label="Close">
          ✕
        </button>
      </div>
      <CountyRegulations page={page} hasPublicLand={hasPublicLand} />
    </aside>
  );
}
