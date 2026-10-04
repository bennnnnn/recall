"""Chat surface over the same My Job preferences, durable runs and history service."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from redis.asyncio import Redis
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import SessionLocal
from app.gateways.mcp.base import ToolResult
from app.models.orm import User
from app.models.schemas.tools import JobSearchToolInput
from app.modules.job_search import runner as job_search_runner
from app.modules.job_search import service as job_search_service
from app.modules.job_search.chat_commands import parse_command
from app.modules.job_search.locations import location_label
from app.modules.job_search.models import JobMatch
from app.modules.job_search.runs import submit_run
from app.modules.job_search.schemas import JobSearchPreferencesPatch, JobSearchUpsert

_job_user: ContextVar[User | None] = ContextVar("mcp_job_search_user", default=None)
_job_redis: ContextVar[Redis | None] = ContextVar("mcp_job_search_redis", default=None)
_job_settings: ContextVar[Settings | None] = ContextVar("mcp_job_search_settings", default=None)
JOB_DIRECT_REPLY_PREFIX = "<!-- recall:job-direct-reply -->\n"


@contextmanager
def bind_job_search_context(
    *, user: User | None = None, redis: Redis | None = None, settings: Settings | None = None
) -> Iterator[None]:
    tokens = (_job_user.set(user), _job_redis.set(redis), _job_settings.set(settings))
    try:
        yield
    finally:
        _job_user.reset(tokens[0])
        _job_redis.reset(tokens[1])
        _job_settings.reset(tokens[2])


def _direct_reply(content: str, data: dict | None = None) -> ToolResult:
    clean = content.strip()
    return ToolResult(
        name="job_search",
        content=f"{JOB_DIRECT_REPLY_PREFIX}{clean}",
        data={"direct_reply": clean, **(data or {})},
    )


def _match_line(match: JobMatch) -> str:
    return f"- [{match.title} at {match.company}]({match.url})\n  <!-- job-match:{match.id} -->"


def _profile_summary(profile: Any) -> str:
    places = profile.included_locations or []
    scope = "; ".join(
        location_label(item.model_dump() if hasattr(item, "model_dump") else item)
        for item in places
    )
    exclusions = "; ".join(
        location_label(item.model_dump() if hasattr(item, "model_dump") else item)
        for item in (profile.excluded_locations or [])
    )
    salary = (
        f"{profile.salary_currency or 'Currency needs review'} "
        f"{profile.salary_min:,}/{profile.salary_period}"
        if profile.salary_min is not None
        else "Not set"
    )
    years = (
        f"{profile.years_experience:g} years" if profile.years_experience is not None else "Not set"
    )
    last = profile.last_run_at.isoformat() if profile.last_run_at else "Not checked yet"
    next_delivery = profile.next_run_at.isoformat() if profile.status == "active" else "Paused"
    return "\n".join(
        (
            f"- **Roles:** {', '.join(profile.target_roles)}",
            f"- **Scope:** {scope or profile.location or 'Worldwide'}",
            f"- **Excluded:** {exclusions or 'None'}",
            f"- **Work arrangement:** {', '.join(profile.work_modes)}",
            f"- **Job seniority:** {', '.join(profile.experience_levels)}",
            f"- **Your experience:** {years}",
            f"- **Minimum pay:** {salary}",
            f"- **Status:** {profile.status}",
            f"- **Last check:** {last}",
            f"- **Next delivery:** {next_delivery}",
        )
    )


def _saved_changes(values: dict[str, Any], profile: Any) -> str:
    labels = {
        "included_locations": "Search locations",
        "excluded_locations": "Excluded locations",
        "years_experience": "Your experience",
        "target_roles": "Target roles",
        "experience_levels": "Job seniority",
        "work_modes": "Work arrangement",
        "result_count": "Results per delivery",
        "frequency": "Delivery frequency",
    }
    lines = []
    for key, value in values.items():
        if key in {"salary_min", "salary_currency", "salary_period"}:
            continue
        if key in {"location", "country"} and "included_locations" in values:
            continue
        if key in {"included_locations", "excluded_locations"}:
            text = "; ".join(location_label(place) for place in value) or "None"
        elif key == "years_experience" and value is not None:
            text = f"{value:g} years"
        elif isinstance(value, list):
            text = ", ".join(str(item) for item in value) or "None"
        else:
            text = (
                "Not set"
                if value is None
                else "Yes"
                if value is True
                else "No"
                if value is False
                else str(value)
            )
        lines.append(f"- {labels.get(key, key.replace('_', ' ').capitalize())}: {text}")
    if {"salary_min", "salary_currency", "salary_period"}.intersection(values):
        pay = (
            f"{profile.salary_currency} {profile.salary_min:,} per {profile.salary_period}"
            if profile.salary_min is not None
            else "Not set"
        )
        lines.append(f"- Minimum pay: {pay}")
    return "Saved:\n" + "\n".join(lines)


def _preferences(args: dict[str, Any]) -> JobSearchPreferencesPatch | None:
    raw = args.get("preferences")
    return JobSearchPreferencesPatch.model_validate(raw) if isinstance(raw, dict) else None


class JobSearchAdapter:
    name = "job_search"
    input_schema = JobSearchToolInput

    def describe(self) -> str:
        return (
            "Set up or manage My Job using current saved records. Save ongoing edits by default. "
            "Use update_profile for atomic compound edits; only explicit 'just this time' uses "
            "preferences on search_now. Structured locations include country, region and city. "
            "Add DC includes Washington DC alongside existing locations. Excluding DC removes "
            "its inclusion. Countrywide uses the established country and retains exclusions. "
            "Numeric years_experience is actual experience, separate from desired seniority. "
            "Ask one clarification for ambiguous country or currency. Edits alone never run "
            "or resume searches; run_after_save is only for an explicitly requested search. "
            "Read get_profile for live status and list for verified persisted match IDs. "
            "Ask which job when ambiguous. Setup needs roles and country; pay and resume "
            "are optional. Support saved jobs, stages, notes and cover letters. Pro required."
        )

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.describe(),
                "parameters": JobSearchToolInput.model_json_schema(),
            },
        }

    async def invoke(self, args: dict[str, Any]) -> ToolResult:
        user, redis, settings = _job_user.get(), _job_redis.get(), _job_settings.get()
        if user is None or settings is None:
            return _direct_reply("My Job is unavailable right now. Please retry.")
        action = str(args.get("action") or "list")
        try:
            async with SessionLocal() as session:
                # Entitlement objects bound to chat may be stale after a webhook.
                fresh_user = await session.get(User, user.id)
                if fresh_user is not None:
                    user = fresh_user
                profile = await job_search_service.get_profile_for_user(session, user.id)
                if profile is None:
                    if action not in {"setup", "update_profile"}:
                        return _direct_reply(
                            "Let's set up My Job. What roles and country should I search in?"
                        )
                    patch = _preferences(args)
                    if patch is None or not patch.target_roles:
                        return _direct_reply("Which job roles should I search for?")
                    places = patch.included_locations or []
                    if not places and not patch.country and not patch.location:
                        return _direct_reply("Which country should I search in?")
                    from app.modules.job_search.locations import legacy_location

                    if (
                        patch.location
                        and not places
                        and not patch.country
                        and not legacy_location(patch.location)
                    ):
                        return _direct_reply("Which country is that location in?")
                    try:
                        zone = ZoneInfo(user.timezone or "UTC")
                    except ZoneInfoNotFoundError:
                        zone = ZoneInfo("UTC")
                    now = datetime.now(zone)
                    first = now.replace(hour=8, minute=0, second=0, microsecond=0)
                    if first <= now:
                        first += timedelta(days=1)
                    values = patch.model_dump(exclude_unset=True)
                    for key in list(values):
                        if key.endswith("_mode") or key == "expected_revision":
                            values.pop(key)
                    if patch.country and not places:
                        values["included_locations"] = [{"country": patch.country}]
                    await job_search_service.upsert_profile(
                        session,
                        user,
                        settings,
                        JobSearchUpsert.model_validate({"next_run_at": first} | values),
                    )
                    profile = await job_search_service.get_profile_for_user(session, user.id)
                    if profile is None:
                        return _direct_reply("My Job setup could not be confirmed. Please retry.")
                    return _direct_reply("My Job is set up. I saved:\n" + _profile_summary(profile))
                if action == "command":
                    args, clarification = parse_command(str(args.get("command") or ""), profile)
                    if clarification:
                        return _direct_reply(clarification)
                    action = args["action"]
                if action == "get_profile":
                    dashboard = await job_search_service.get_dashboard(session, user, settings)
                    latest = dashboard.latest_run
                    outcome = (
                        f"Last outcome: {latest.state}; "
                        f"{latest.qualifying_count + latest.possible_count} matches found; "
                        f"{latest.new_match_count} new verified matches."
                        if latest
                        else "No searches have run yet."
                    )
                    if latest and latest.partial:
                        outcome += " Coverage was partial."
                    if latest and latest.failure_reason:
                        outcome += " " + latest.failure_reason
                    restriction = (
                        (
                            "Recall Pro expired. History is readable; renew and expl"
                            "icitly Resume to search again."
                        )
                        if dashboard.pro_required
                        else f"{dashboard.manual_remaining} manual searches remaining today."
                    )
                    if not dashboard.premium_enabled:
                        restriction += " My Job search rollout is not enabled yet."
                    if dashboard.cooldown_until:
                        restriction += (
                            f" Next manual search after {dashboard.cooldown_until.isoformat()}."
                        )
                    return _direct_reply(
                        _profile_summary(dashboard.profile) + "\n\n" + outcome + "\n" + restriction,
                        {"dashboard": dashboard.model_dump(mode="json")},
                    )
                if action == "update_profile":
                    patch = _preferences(args)
                    if patch is None:
                        return _direct_reply("What would you like to change in My Job?")
                    values = job_search_service.preference_values(profile, patch)
                    dashboard = await job_search_service.patch_profile(
                        session, user, settings, patch
                    )
                    confirmation = _saved_changes(values, dashboard.profile)
                    if dashboard.profile and dashboard.profile.status == "paused":
                        confirmation += " My Job remains paused."
                    if args.get("run_after_save") and redis is not None:
                        run = await submit_run(session, user, settings, redis)
                        confirmation += " A new search is queued."
                        return _direct_reply(confirmation, {"run_id": str(run.id), "saved": values})
                    return _direct_reply(
                        confirmation,
                        {
                            "saved": values,
                            "profile": dashboard.profile.model_dump(mode="json")
                            if dashboard.profile
                            else None,
                        },
                    )
                if action == "update_status":
                    status = args.get("search_status")
                    if status not in {"active", "paused"}:
                        return _direct_reply("Should I pause or resume My Job?")
                    dashboard = await job_search_service.set_search_status(
                        session, user, settings, status
                    )
                    return _direct_reply(
                        f"My Job is now {status}.",
                        {
                            "profile": dashboard.profile.model_dump(mode="json")
                            if dashboard.profile
                            else None
                        },
                    )
                if action == "update_match":
                    if not args.get("match_id"):
                        return _direct_reply("Which job should I update?")
                    await job_search_service.set_match_status(
                        session,
                        user,
                        settings,
                        UUID(str(args["match_id"])),
                        args.get("match_status"),
                        args.get("notes"),
                        is_saved=args.get("is_saved"),
                        notes_provided="notes" in args,
                    )
                    return _direct_reply(
                        "Saved that job update.", {"match_id": str(args["match_id"])}
                    )
                if action == "cover_letter":
                    if not args.get("match_id") or redis is None:
                        return _direct_reply("Which job should I write the cover letter for?")
                    letter = await job_search_service.generate_cover_letter(
                        session, user, settings, redis, UUID(str(args["match_id"]))
                    )
                    return _direct_reply(letter.cover_letter, {"match_id": str(args["match_id"])})
                if action == "search_now":
                    if redis is None:
                        return _direct_reply("Search is unavailable right now. Please retry.")
                    patch = _preferences(args)
                    overrides = (
                        job_search_service.preference_values(profile, patch) if patch else None
                    )
                    run = await submit_run(
                        session,
                        user,
                        settings,
                        redis,
                        overrides=overrides,
                        result_limit=args.get("result_limit"),
                    )
                    note = (
                        "Search queued. You can close chat; check My Job or ask "
                        "for status while it runs."
                    )
                    if overrides:
                        note += " This one-time search leaves your saved preferences unchanged."
                    return _direct_reply(note, {"run_id": str(run.id), "state": run.state})
                if action == "analyze_job":
                    job_search_service.require_pro(user)
                    if redis is None:
                        return _direct_reply("Job comparison is unavailable right now.")
                    from app.services.quota import global_spend_exceeded

                    if await global_spend_exceeded(redis, settings):
                        return _direct_reply("Search spending limit reached. Please try later.")
                    result = await job_search_runner.analyze_job_url(
                        settings,
                        profile_id=profile.id,
                        url=str(args.get("job_url") or ""),
                        redis=redis,
                    )
                    if result is None:
                        return _direct_reply(
                            "That page could not be verified as a specific, available job posting."
                        )
                    return _direct_reply(
                        f"{result.title} at {result.company}\n"
                        + "\n".join(result.match_reasons)
                        + ("\nNeeds review: " + result.gap if result.gap else ""),
                        {"assessment": result.assessment},
                    )
                query = select(JobMatch).where(
                    JobMatch.profile_id == profile.id, JobMatch.status != "hidden"
                )
                filter_name = args.get("list_filter", "matches")
                if filter_name == "saved":
                    query = query.where(JobMatch.is_saved.is_(True))
                elif filter_name in {"applied", "interviewing", "offer", "rejected"}:
                    query = query.where(JobMatch.status == filter_name)
                rows = list(
                    (
                        await session.scalars(
                            query.order_by(JobMatch.found_at.desc())
                            .offset(int(args.get("offset", 0)))
                            .limit(15)
                        )
                    ).all()
                )
                snapshot = job_search_service._profile_from_rows(profile, user)
                matches = [
                    job_search_service.match_out(match, profile_snapshot=snapshot).model_dump(
                        mode="json"
                    )
                    for match in rows
                ]
                if not matches:
                    return _direct_reply(
                        "No jobs in that view yet. Ask me to search or change your preferences."
                    )
                # Persisted IDs let the native cards hydrate verified facts.
                return _direct_reply(
                    "Here are your saved My Job results.\n\n```job-results\n"
                    + json.dumps({"matches": matches})
                    + "\n```",
                    {"matches": matches},
                )
        except (ValueError, job_search_service.JobSearchError) as exc:
            return _direct_reply(str(getattr(exc, "detail", str(exc))))
