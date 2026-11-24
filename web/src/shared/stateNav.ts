import type { StateId, StateProfile } from "../states/catalog";

/** Shared view ids across Texas and multi-state explorers. */
export type StateViewId =
  | "map"
  | "report"
  | "hunts"
  | "in-season"
  | "licenses"
  | "rules"
  | "saved"
  | "users";

export type StateNavTab = { id: StateViewId; label: string };

/** Header tabs for the active state — same placement/style for every state. */
export function navTabsForState(stateId: StateId, profile: StateProfile): StateNavTab[] {
  if (stateId === "tx") {
    return [
      { id: "map", label: "Map" },
      { id: "report", label: "Report" },
      { id: "in-season", label: "In Season" },
      { id: "licenses", label: "Licenses" },
      { id: "saved", label: "Saved" },
    ];
  }
  if (profile === "unitGrid") {
    return [
      { id: "map", label: "Map" },
      { id: "hunts", label: "Hunts" },
      { id: "in-season", label: "In Season" },
      { id: "licenses", label: "Licenses" },
      { id: "rules", label: "Rules" },
    ];
  }
  return [
    { id: "map", label: "Map" },
    { id: "report", label: "Report" },
    { id: "in-season", label: "In Season" },
    { id: "licenses", label: "Licenses" },
    { id: "rules", label: "Rules" },
  ];
}

export function isNavTabForState(
  view: StateViewId,
  stateId: StateId,
  profile: StateProfile,
): boolean {
  return navTabsForState(stateId, profile).some((tab) => tab.id === view);
}
