"""Deterministic handling for common conversational edits and short follow-ups."""

from __future__ import annotations

import re
from typing import Any

from app.modules.job_search.locations import canonical_country, legacy_location
from app.modules.job_search.models import JobSearchProfile

_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "fifteen": 15,
    "twenty": 20,
}
_TEMPORARY = re.compile(
    r"\b(just this (?:time|once)|one[ -]?time|without changing|don't change|do not change)\b", re.I
)
_COMMAND = re.compile(
    r"\b(add dc|(?:don't|dont|do not|don\u2019t) want "
    r"(?:(?:jobs? )?(?:from|in) )?dc|all over (?:the|my) country|nationwide|"
    r"minimum salary|my experience to .{1,20}years?|my job status|status of my job)\b",
    re.I,
)


def direct_command(text: str) -> dict[str, Any] | None:
    if _COMMAND.search(text) and not re.search(
        r"\b(?:roles?|skills?|remote|hybrid|onsite|frequency|sponsorship|companies)\b", text, re.I
    ):
        return {"action": "command", "command": text[:1500]}
    return None


def parse_command(text: str, profile: JobSearchProfile) -> tuple[dict[str, Any], str | None]:
    lower = text.casefold()
    patch: dict[str, Any] = {}
    if re.search(r"my job status|status of my job", lower):
        return {"action": "get_profile"}, None
    # Recognize every requested fragment before applying one atomic update.
    if re.search(r"\badd dc\b", lower):
        patch.update(
            included_locations=[{"country": "United States", "region": "District of Columbia"}],
            included_locations_mode="add",
        )
    if re.search(r"(?:don't|dont|do not|don\u2019t) want (?:(?:jobs? )?(?:from|in) )?dc", lower):
        patch.update(
            excluded_locations=[{"country": "United States", "region": "District of Columbia"}],
            excluded_locations_mode="add",
        )
        patch.pop("included_locations", None)
        patch.pop("included_locations_mode", None)
    if re.search(r"all over (?:the|my) country|nationwide", lower):
        countries = {
            place["country"]
            for place in (profile.included_locations or legacy_location(profile.location))
        }
        country = profile.country or (next(iter(countries)) if len(countries) == 1 else None)
        if not country:
            return {}, "Which country should I search across?"
        patch.update(
            included_locations=[{"country": canonical_country(country)}],
            included_locations_mode="replace",
        )
    experience = re.search(
        r"(?:my )?experience (?:to|is|=)\s*(\d+(?:\.\d+)?|" + "|".join(_NUMBERS) + r")\s*years?",
        lower,
    )
    if experience:
        number = experience.group(1)
        patch["years_experience"] = float(number) if number[0].isdigit() else _NUMBERS[number]
    salary = re.search(
        r"minimum salary\s*(?:to|is|of|=)?\s*(?:[A-Z]{3}\s*)?\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(k)?",
        text,
        re.I,
    )
    if salary:
        patch["salary_min"] = int(
            float(salary.group(1).replace(",", "")) * (1000 if salary.group(2) else 1)
        )
        currency = re.search(r"minimum salary\s*(?:to|is|of|=)?\s*([A-Z]{3})\b", text, re.I)
        if currency:
            patch["salary_currency"] = currency.group(1).upper()
        elif not profile.salary_currency:
            return {}, "Which currency should I use for your minimum salary?"
        for period, expression in (
            ("hour", "hour|hourly"),
            ("month", "month|monthly"),
            ("week", "week|weekly"),
            ("year", "year|yearly|annual"),
        ):
            if re.search(r"\b(?:" + expression + r")\b", lower):
                patch["salary_period"] = period
    # Mixed unsupported preference edits belong to the structured selector;
    # never confirm just the easiest part of a compound request.
    if re.search(
        r"\b(?:roles?|skills?|remote|hybrid|onsite|frequency|sponsorship|companies)\b", lower
    ):
        return (
            {},
            ("What roles, skills or work arrangement should I save with this change?"),
        )
    if not patch:
        return {}, "What would you like to change in My Job?"
    return {
        "action": "search_now" if _TEMPORARY.search(text) else "update_profile",
        "preferences": patch,
        "run_after_save": bool(
            re.search(r"\b(search now|search again|run a search|check all over)\b", lower)
        )
        and not _TEMPORARY.search(text),
    }, None
