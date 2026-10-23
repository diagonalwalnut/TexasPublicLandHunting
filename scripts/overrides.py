"""Apply hand-checked legal-means corrections on top of compiled hunt data.

`data/unit_overrides.json` is the seed. The accounts API stores later edits in
the same shape, and `web/src/corrections.ts` applies them again in the browser.
Keep the two rewrite rules in step.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OVERRIDES_PATH = ROOT / "data" / "unit_overrides.json"

METHOD_ORDER = ("archery", "firearm", "muzzleloader", "shotgun", "any_legal")


def load_unit_overrides(path: Path | None = None) -> list[dict[str, Any]]:
    src = path or OVERRIDES_PATH
    if not src.exists():
        return []
    data = json.loads(src.read_text())
    if not isinstance(data, list):
        raise ValueError(f"{src} must be a list of unit corrections")
    return [row for row in data if isinstance(row, dict) and row.get("unitId")]


def _ordered(methods: list[str]) -> list[str]:
    rank = {method: index for index, method in enumerate(METHOD_ORDER)}
    seen: list[str] = []
    for method in methods:
        if method not in seen:
            seen.append(method)
    return sorted(seen, key=lambda method: rank.get(method, 99))


def forbid_set(override: dict[str, Any]) -> set[str]:
    forbid = {method for method in (override.get("forbidMethods") or []) if isinstance(method, str)}
    # The rifle filter treats any_legal as a rifle, so a rifle ban has to clear it.
    if "firearm" in forbid:
        forbid.add("any_legal")
    return forbid


def rewrite_methods(methods: list[str], species: str, override: dict[str, Any]) -> list[str]:
    """Return the corrected methods, or an empty list when the row should be dropped.

    speciesMethods replaces that species. A row whose only explicit methods are
    outside the replacement (a firearm row when deer is archery only) is dropped
    so its dates are not relabeled. An unspecified any_legal row is refined to
    the replacement list. forbidMethods then strips those means everywhere;
    forbidding firearm also strips any_legal.
    """
    forbid = forbid_set(override)
    species_methods = override.get("speciesMethods") or {}
    allowed = species_methods.get(species) if isinstance(species_methods, dict) else None
    if isinstance(allowed, list):
        allowed_list = _ordered(
            [method for method in allowed if isinstance(method, str) and method not in forbid and method != "any_legal"]
        )
        explicit = [method for method in methods if method != "any_legal"]
        if explicit and not any(method in allowed_list for method in explicit):
            return []
        return allowed_list
    return _ordered([method for method in methods if method not in forbid])


def apply_unit_overrides(
    units: list[dict[str, Any]],
    opportunities: list[dict[str, Any]],
    overrides: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Rewrite units and opportunities in place. Rows left with no methods are removed."""
    by_id = {str(row["unitId"]): row for row in overrides if row.get("unitId")}
    if not by_id:
        return units, opportunities

    kept: list[dict[str, Any]] = []
    for opp in opportunities:
        override = by_id.get(str(opp.get("unitId") or ""))
        if not override:
            kept.append(opp)
            continue
        methods = rewrite_methods(list(opp.get("methods") or []), str(opp.get("species") or ""), override)
        if not methods:
            continue
        nxt = dict(opp)
        nxt["methods"] = methods
        kept.append(nxt)
    opportunities[:] = kept

    by_unit: dict[str, list[dict[str, Any]]] = {}
    for opp in opportunities:
        by_unit.setdefault(str(opp["unitId"]), []).append(opp)

    for unit in units:
        override = by_id.get(str(unit.get("id") or ""))
        if not override:
            continue
        rows = by_unit.get(str(unit["id"]), [])
        unit["methods"] = _ordered([method for row in rows for method in row["methods"]])
        unit["species"] = sorted({row["species"] for row in rows if row.get("species") and row["species"] != "fishing"})
        note = str(override.get("note") or "").strip()
        if note:
            unit["correctionNote"] = note
        else:
            unit.pop("correctionNote", None)
        unit["methodCorrection"] = {
            "speciesMethods": {
                species: _ordered(
                    [
                        method
                        for method in methods
                        if isinstance(method, str) and method not in forbid_set(override) and method != "any_legal"
                    ]
                )
                for species, methods in (override.get("speciesMethods") or {}).items()
                if isinstance(species, str) and isinstance(methods, list)
            },
            "forbidMethods": _ordered(
                [method for method in (override.get("forbidMethods") or []) if isinstance(method, str)]
            ),
            "note": note,
        }
    return units, opportunities


def sync_feature_corrections(features: list[dict[str, Any]], units: list[dict[str, Any]]) -> None:
    """Copy corrected method fields onto GeoJSON properties already snapped from units."""
    by_id = {str(unit["id"]): unit for unit in units}
    for feature in features:
        props = feature.get("properties") or {}
        unit_id = str(feature.get("id") or props.get("id") or "")
        unit = by_id.get(unit_id)
        if not unit:
            continue
        props["methods"] = unit.get("methods") or []
        props["species"] = unit.get("species") or []
        if unit.get("correctionNote"):
            props["correctionNote"] = unit["correctionNote"]
        else:
            props.pop("correctionNote", None)
        if unit.get("methodCorrection"):
            props["methodCorrection"] = unit["methodCorrection"]
        else:
            props.pop("methodCorrection", None)
        feature["properties"] = props
