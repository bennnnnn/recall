"""Structured geography shared by saved preferences and posting verification."""

from __future__ import annotations

import re
from typing import Any

from app.modules.job_search.schemas import JobLocation

_COUNTRIES = {
    "us": "United States",
    "usa": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "gb": "United Kingdom",
    "ca": "Canada",
    "au": "Australia",
    "de": "Germany",
    "fr": "France",
    "in": "India",
    "et": "Ethiopia",
    "jp": "Japan",
}
_US_REGIONS = {
    "california": "California",
    "dc": "District of Columbia",
    "washington dc": "District of Columbia",
    "washington, dc": "District of Columbia",
    "district of columbia": "District of Columbia",
}


def canonical_country(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    aliases = _COUNTRIES | {country.casefold(): country for country in _COUNTRIES.values()}
    return aliases.get(cleaned.casefold().replace(".", ""), cleaned)


def normalize_location(value: JobLocation | dict[str, Any]) -> dict[str, str | None]:
    item = value if isinstance(value, JobLocation) else JobLocation.model_validate(value)
    return {"country": canonical_country(item.country), "region": item.region, "city": item.city}


def legacy_location(value: str | None) -> list[dict[str, str | None]]:
    """Backfill only known country names/codes or unambiguous US state examples."""
    if not value:
        return []
    key = value.strip().casefold()
    if key in _US_REGIONS:
        return [{"country": "United States", "region": _US_REGIONS[key], "city": None}]
    parts = [part.strip() for part in value.split(",")]
    country = canonical_country(parts[-1])
    known = {
        *_COUNTRIES.values(),
        "Canada",
        "Australia",
        "United States",
        "United Kingdom",
        "Germany",
        "France",
        "India",
        "Ethiopia",
        "Japan",
    }
    if country not in known:
        return []
    return [
        {
            "country": country,
            "region": parts[-2] if len(parts) > 1 else None,
            "city": parts[0] if len(parts) > 2 else None,
        }
    ]


def location_label(item: dict[str, Any]) -> str:
    return ", ".join(str(item[key]) for key in ("city", "region", "country") if item.get(key))


def merge_locations(current: list[dict], incoming: list[dict], mode: str) -> list[dict]:
    def key(item: dict) -> str:
        return location_label(item).casefold()

    additions = {key(item): item for item in incoming}
    if mode == "replace":
        return list(additions.values())[:20]
    if mode == "remove":
        return [item for item in current if key(item) not in additions]
    return list({**{key(item): item for item in current}, **additions}.values())[:20]


def contains_place(place: dict, text: str) -> bool:
    """Match every disclosed part, with word boundaries to avoid CA/Canada collisions."""
    parts = [str(place[k]) for k in ("country", "region", "city") if place.get(k)]
    folded = text.casefold()
    for part in parts:
        aliases = [part]
        if part == "United States":
            aliases += ["USA", "U.S.", "US", "United States of America"]
        if part == "District of Columbia":
            aliases += ["Washington, DC", "Washington DC", "D.C."]
        if part == "California":
            aliases += ["CA"]
        if not any(
            re.search(r"(?<!\w)" + re.escape(alias.casefold()) + r"(?!\w)", folded)
            for alias in aliases
        ):
            return False
    return bool(parts)
