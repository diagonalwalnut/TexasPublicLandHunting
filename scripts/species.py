"""Normalize TPWD APH legal-game tags into species, methods, and access types."""

from __future__ import annotations

import re
from typing import Any

SPECIES: dict[str, str] = {
    "white_tailed_deer": "White-tailed deer",
    "mule_deer": "Mule deer",
    "javelina": "Javelina",
    "turkey": "Turkey",
    "dove": "Dove",
    "quail": "Quail",
    "pheasant": "Pheasant",
    "chachalaca": "Chachalaca",
    "squirrel": "Squirrel",
    "rabbit": "Rabbit",
    "feral_hog": "Feral hog",
    "waterfowl": "Waterfowl",
    "teal": "Teal",
    "sandhill_crane": "Sandhill crane",
    "other_migratory": "Other migratory birds",
    "furbearers": "Furbearers / predators",
    "coyote": "Coyote",
    "exotic_mammals": "Exotic mammals",
    "alligator": "Alligator",
    "pronghorn": "Pronghorn",
    "bighorn_sheep": "Bighorn sheep",
    "fishing": "Fishing",
}

SKIP_TAGS = {"", "none", "trapping"}

DEER_METHOD_RE = re.compile(r"archery|muzzle|general|gun|rifle|firearm", re.I)


def _clean(tag: str) -> str:
    return re.sub(r"\s+", " ", tag).strip()


def legal_game_tags(row: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for i in range(1, 23):
        raw = row.get(f"legalGame{i}") or ""
        text = _clean(str(raw))
        if text.lower() in SKIP_TAGS:
            continue
        tags.append(text)
    return tags


def access_from_tag(tag: str) -> str:
    t = tag.lower()
    if "e-postcard" in t or "epostcard" in t:
        return "e_postcard"
    if "regular permit" in t:
        return "regular_permit"
    if "youth/adult" in t or "youth / adult" in t:
        return "youth_adult"
    if "youth" in t:
        return "youth"
    if "drawn" in t or "special permit" in t:
        return "drawn"
    return "aph_walk_in"


def methods_from_tag(tag: str, species: str) -> list[str]:
    t = tag.lower()
    methods: list[str] = []
    if "archery" in t:
        methods.append("archery")
    if "muzzle" in t:
        methods.append("muzzleloader")
    # "gun" must not match shotgun. "general" is the gun season, not a means —
    # it defaults to firearm/rifle unless the unit Legal Game box restricts it.
    if re.search(r"\brifle\b|\bfirearm\b|centerfire", t):
        methods.append("firearm")
    elif re.search(r"\bgeneral\b", t) and "muzzle" not in t:
        methods.append("firearm")
    if re.search(r"shotguns?", t) and "shotgun" not in methods:
        methods.append("shotgun")
    if species in {"dove", "waterfowl", "teal", "sandhill_crane", "other_migratory", "chachalaca"}:
        if "shotgun" not in methods:
            methods.append("shotgun")
    if not methods:
        methods.append("any_legal")
    return methods


def species_from_tag(tag: str) -> str | None:
    t = tag.lower().replace("squirel", "squirrel")
    t = t.replace("feral hop", "feral hog").replace("exotics mammals", "exotic mammals")
    t = t.replace("mulit-species", "multi-species").replace("mult-species", "multi-species")
    if "alligator" in t:
        return "alligator"
    if "pronghorn" in t or "antelope" in t:
        return "pronghorn"
    if "bighorn" in t:
        return "bighorn_sheep"
    if "fishing" in t:
        return "fishing"
    if "chachalaca" in t:
        return "chachalaca"
    if "pheasant" in t and "waterfowl" in t:
        return "waterfowl"
    if "pheasant" in t:
        return "pheasant"
    if "quail" in t:
        return "quail"
    if "turkey" in t:
        return "turkey"
    if "javelina" in t:
        return "javelina"
    if "mule" in t:
        return "mule_deer"
    if "deer" in t:
        return "white_tailed_deer"
    if "dove" in t:
        return "dove"
    if "teal" in t:
        return "teal"
    if "crane" in t:
        return "sandhill_crane"
    if "waterfowl" in t or "duck" in t or "goose" in t:
        return "waterfowl"
    if "migratory" in t:
        return "other_migratory"
    if "squirrel" in t:
        return "squirrel"
    if "rabbit" in t:
        return "rabbit"
    if "hog" in t:
        return "feral_hog"
    if "coyote" in t:
        return "coyote"
    if "furbear" in t or "predator" in t:
        return "furbearers"
    if "exotic" in t:
        return "exotic_mammals"
    if "multi-species" in t:
        return None
    return None


def extra_species_from_tag(tag: str) -> list[str]:
    """Tags that name more than one species."""
    t = tag.lower()
    extras: list[str] = []
    if "pheasant" in t and "waterfowl" in t:
        extras.append("pheasant")
    if "hog" in t and "predator" in t:
        extras.append("furbearers")
    if "multi-species" in t:
        extras.extend(["dove", "quail", "rabbit", "squirrel", "feral_hog"])
    return extras


def classify_tag(tag: str) -> list[dict[str, Any]]:
    species = species_from_tag(tag)
    extras = extra_species_from_tag(tag)
    keys = []
    if species:
        keys.append(species)
    for extra in extras:
        if extra not in keys:
            keys.append(extra)
    if not keys:
        return []
    access = access_from_tag(tag)
    rows = []
    for key in keys:
        rows.append(
            {
                "species": key,
                "speciesLabel": SPECIES.get(key, key),
                "methods": methods_from_tag(tag, key),
                "access": access,
                "sourceTag": tag,
            }
        )
    return rows
