"""Atomic structured preference composition, independent of chat or HTTP."""

from typing import Any

from app.modules.job_search.locations import (
    canonical_country,
    legacy_location,
    location_label,
    merge_locations,
    normalize_location,
)
from app.modules.job_search.models import JobSearchProfile
from app.modules.job_search.schemas import JobSearchPreferencesPatch


def structured_values(
    profile: JobSearchProfile, patch: JobSearchPreferencesPatch
) -> dict[str, Any]:
    fields = patch.model_fields_set
    values: dict[str, Any] = {}
    for field in ("country", "salary_currency", "salary_period", "years_experience"):
        if field in fields:
            values[field] = getattr(patch, field)
    if values.get("country"):
        values["country"] = canonical_country(values["country"])
    included = list(profile.included_locations or legacy_location(profile.location))
    excluded = list(profile.excluded_locations or [])
    for field, current in (("included_locations", included), ("excluded_locations", excluded)):
        if field in fields:
            incoming = [normalize_location(item) for item in (getattr(patch, field) or [])]
            values[field] = merge_locations(current, incoming, getattr(patch, field + "_mode"))
    # An explicit inclusion reverses the same saved exclusion. A broad country
    # inclusion leaves narrower region/city exclusions intact.
    if (
        "included_locations" in fields
        and patch.included_locations_mode != "remove"
        and "excluded_locations" not in fields
    ):
        added = {
            location_label(normalize_location(item)).casefold()
            for item in (patch.included_locations or [])
        }
        values["excluded_locations"] = [
            item for item in excluded if location_label(item).casefold() not in added
        ]
    if "excluded_locations" in values:
        removed = {location_label(item).casefold() for item in values["excluded_locations"]}
        values["included_locations"] = [
            item
            for item in values.get("included_locations", included)
            if location_label(item).casefold() not in removed
        ]
    if "location" in fields and "included_locations" not in fields:
        places = legacy_location(patch.location)
        if patch.location and not places:
            raise ValueError(
                "Which country is that location in? Use a structured country, region and city."
            )
        values["included_locations"] = places
    if "included_locations" in values:
        places = values["included_locations"]
        values["location"] = "; ".join(location_label(item) for item in places)[:160] or None
        countries = {item["country"] for item in places}
        values["country"] = next(iter(countries)) if len(countries) == 1 else None
    salary = values.get(
        "salary_min", patch.salary_min if "salary_min" in fields else profile.salary_min
    )
    currency = values.get("salary_currency", profile.salary_currency)
    if (
        salary is not None
        and not currency
        and {"salary_min", "salary_currency"}.intersection(fields)
    ):
        raise ValueError("Which currency should I use for your minimum salary?")
    for field in ("work_modes", "experience_levels", "result_count", "frequency", "salary_period"):
        if field in fields and getattr(patch, field) is None:
            raise ValueError(f"{field} cannot be null")
    return values
