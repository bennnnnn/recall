"""Deterministic job routing and guards around model-selected chat edits."""

from __future__ import annotations

import json
import re
from typing import Any

_NUMBER_WORDS = {
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
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
}

_UNFILTERED_JOB_SEARCH_WORDS = {
    "a",
    "again",
    "current",
    "find",
    "for",
    "job",
    "jobs",
    "look",
    "match",
    "matches",
    "me",
    "more",
    "my",
    "new",
    "now",
    "opening",
    "openings",
    "please",
    "profile",
    "role",
    "roles",
    "saved",
    "search",
    "searching",
    "start",
    "the",
    "using",
}


def _requested_job_limit(text: str) -> int | None:
    match = re.search(
        r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen)\b",
        text.casefold(),
    )
    if match is None:
        return None
    raw = match.group(1)
    value = int(raw) if raw.isdigit() else _NUMBER_WORDS.get(raw)
    return value if value is not None and 1 <= value <= 15 else None


def _is_unfiltered_job_search(text: str) -> bool:
    """Only bypass the selector when the request adds no search filters."""
    normalized = "".join(character if character.isalnum() else " " for character in text.casefold())
    words = normalized.split()
    return all(
        word.isdigit() or word in _NUMBER_WORDS or word in _UNFILTERED_JOB_SEARCH_WORDS
        for word in words
    )


def _is_one_off_job_search(text: str) -> bool:
    lower = text.casefold()
    has_search = bool(re.search(r"\b(search|find|look\s+for|start\s+searching)\b", lower))
    temporary = bool(
        re.search(
            r"\b(just this (?:once|time)|one[ -]?time|do not change|don't change|"
            r"without changing|keep my saved)\b",
            lower,
        )
    )
    return has_search and temporary


def _is_saved_job_update(text: str) -> bool:
    lower = text.casefold()
    if _is_one_off_job_search(text):
        return False
    has_mutation = bool(re.search(r"\b(restore|change|update|set|switch|edit|replace)\b", lower))
    has_subject = "my job" in lower or "job search" in lower
    has_preference = any(
        cue in lower
        for cue in (
            "saved",
            "preference",
            "profile",
            "location",
            "experience",
            "work mode",
            "remote",
            "hybrid",
            "on-site",
            "onsite",
            "target role",
            "skill",
            "salary",
            "frequency",
        )
    )
    return has_mutation and has_subject and has_preference


def _protect_one_off_job_search(
    name: str,
    raw_args: str,
    user_text: str,
) -> str:
    """Prevent temporary searches from mutating the saved My Job profile."""
    if name != "job_search" or not _is_one_off_job_search(user_text):
        return raw_args
    try:
        args = json.loads(raw_args)
    except (TypeError, ValueError):
        return raw_args
    if not isinstance(args, dict) or args.get("action") not in {"update_profile", "search_now"}:
        return raw_args
    args["action"] = "search_now"
    requested_limit = _requested_job_limit(user_text)
    if requested_limit is not None:
        args["result_limit"] = requested_limit
    return json.dumps(args)


def _protect_saved_job_update(name: str, raw_args: str, user_text: str) -> str:
    """Keep explicit saved-search edits from becoming temporary searches."""
    if name != "job_search" or not _is_saved_job_update(user_text):
        return raw_args
    try:
        args = json.loads(raw_args)
    except (TypeError, ValueError):
        return raw_args
    if (
        not isinstance(args, dict)
        or args.get("action") != "search_now"
        or args.get("preferences") is None
    ):
        return raw_args
    args["action"] = "update_profile"
    args.pop("result_limit", None)
    return json.dumps(args)


def _direct_job_tool_args(text: str) -> dict[str, Any] | None:
    """Return safe My Job actions that need no model interpretation.

    This keeps common reads and unambiguous preference edits reliable during a
    model-provider outage. More complex edits still use the structured selector.
    """
    from app.modules.job_search.chat_commands import direct_command

    command = direct_command(text)
    if command:
        return command
    lower = text.casefold()
    if not lower.strip():
        return None
    if _is_one_off_job_search(text):
        # Let the structured selector extract temporary role/location filters;
        # the invoke path below guarantees they cannot become a profile edit.
        return None
    match_id = re.search(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
        lower,
    )
    match_status = next(
        (
            status
            for status in (
                "saved",
                "applied",
                "interviewing",
                "offer",
                "rejected",
                "hidden",
                "new",
            )
            if re.search(rf"\b{status}\b", lower)
        ),
        None,
    )
    if (
        match_id is not None
        and match_status is not None
        and any(cue in lower for cue in ("mark", "move", "set", "change", "update"))
    ):
        return {
            "action": "update_match",
            "match_id": match_id.group(0),
            "match_status": match_status,
        }
    if "http://" in lower or "https://" in lower:
        if any(cue in lower for cue in ("check", "analyze", "analyse", "compare", "fit")):
            starts = [
                index for index in (lower.find("https://"), lower.find("http://")) if index >= 0
            ]
            if starts:
                start = min(starts)
                url = text[start:].split()[0].rstrip('.,;:!?)"]}')
                return {"action": "analyze_job", "job_url": url}
    if "pause" in lower and ("my job" in lower or "job search" in lower):
        return {"action": "update_status", "search_status": "paused"}
    if "resume" in lower and ("my job" in lower or "job search" in lower):
        return {"action": "update_status", "search_status": "active"}
    mutation_cues = (
        "change",
        "restore",
        "update",
        "set ",
        "switch",
        "make it",
        "prefer",
        "only want",
    )
    if any(cue in lower for cue in mutation_cues):
        # Arbitrary role/location/skill/salary edits need the structured tool
        # selector. Handling only the easy fragment (for example, experience)
        # would silently ignore the requested role while claiming full success.
        complex_change = any(
            cue in lower
            for cue in (
                "target role",
                "job type",
                "skill",
                "salary",
                "location",
                "sponsorship",
                "excluded",
                "company",
            )
        ) or bool(re.search(r"\b(?:my job|job search)\s+to\b", lower))
        if complex_change:
            return None
        preferences: dict[str, Any] = {}
        work_modes = [
            mode
            for mode, patterns in (
                ("remote", ("remote",)),
                ("hybrid", ("hybrid",)),
                ("onsite", ("onsite", "on-site", "on site")),
            )
            if any(pattern in lower for pattern in patterns)
        ]
        if work_modes:
            preferences["work_modes"] = work_modes
        experience_levels = [
            level
            for level, patterns in (
                ("internship", ("internship", "intern level")),
                ("entry", ("entry level", "entry-level")),
                ("mid", ("mid level", "mid-level")),
                ("senior", ("senior",)),
            )
            if any(pattern in lower for pattern in patterns)
        ]
        if experience_levels:
            preferences["experience_levels"] = experience_levels
        frequency = next(
            (
                value
                for value, patterns in (
                    ("weekdays", ("weekdays", "every weekday")),
                    ("daily", ("daily", "every day")),
                    ("weekly", ("weekly", "every week")),
                    ("monthly", ("monthly", "every month")),
                )
                if any(pattern in lower for pattern in patterns)
            ),
            None,
        )
        if frequency is not None:
            preferences["frequency"] = frequency
        if preferences:
            return {"action": "update_profile", "preferences": preferences}
    if any(cue in lower for cue in ("preference", "setting", "profile")) and (
        "my job" in lower or "job search" in lower
    ):
        return {"action": "get_profile"}
    if any(cue in lower for cue in ("match", "listing", "saved job", "applied job")) and (
        "job" in lower or "role" in lower
    ):
        return {"action": "list"}
    if re.search(r"\b(search|find|look\s+for|start\s+searching)\b", lower):
        if not _is_unfiltered_job_search(text):
            # Role, location, level, work mode, and other filters belong to the
            # structured selector. A direct search here would silently use the
            # saved profile and ignore the user's requested filters.
            return None
        search_args: dict[str, Any] = {"action": "search_now"}
        requested_limit = _requested_job_limit(text)
        if requested_limit is not None:
            search_args["result_limit"] = requested_limit
        return search_args
    return None
