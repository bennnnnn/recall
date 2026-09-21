"""Dynamic My Job controls exposed to ordinary chat turns."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.jobs import enqueue
from app.gateways.mcp.base import ToolResult
from app.models.orm import JobMatch, JobSearchProfile, User
from app.models.schemas.job_search import JobSearchPreferencesPatch
from app.models.schemas.tools import JobSearchToolInput
from app.services import job_search as job_search_service
from app.services.job_search import runner as job_search_runner
from app.services.prompt_safety import wrap_untrusted

# Request-scoped identity, same pattern as the web search adapter.
_job_user: ContextVar[User | None] = ContextVar("mcp_job_search_user", default=None)
_job_redis: ContextVar[Redis | None] = ContextVar("mcp_job_search_redis", default=None)
_job_settings: ContextVar[Settings | None] = ContextVar("mcp_job_search_settings", default=None)

_MANUAL_RUN_COOLDOWN = timedelta(minutes=10)
_LIST_LIMIT = 10


@contextmanager
def bind_job_search_context(
    *,
    user: User | None = None,
    redis: Redis | None = None,
    settings: Settings | None = None,
) -> Iterator[None]:
    """Bind the calling turn's identity and runtime dependencies."""
    token_user = _job_user.set(user)
    token_redis = _job_redis.set(redis)
    token_settings = _job_settings.set(settings)
    try:
        yield
    finally:
        _job_user.reset(token_user)
        _job_redis.reset(token_redis)
        _job_settings.reset(token_settings)


def _match_line(match: JobMatch) -> str:
    fit = f", {match.match_score}% fit" if match.match_score is not None else ""
    return (
        f"- {match.title} at {match.company}{fit}; status={match.status}; "
        f"match_id={match.id} — {match.url}"
    )


def _profile_summary(profile: JobSearchProfile | Any) -> str:
    salary = f"{profile.salary_min}+ yearly" if profile.salary_min is not None else "not set"
    sponsorship = (
        "required"
        if profile.requires_sponsorship is True
        else "not required"
        if profile.requires_sponsorship is False
        else "not specified"
    )
    return (
        f"roles={', '.join(profile.target_roles)}; "
        f"location={profile.location or 'any'}; "
        f"work_modes={', '.join(profile.work_modes)}; "
        f"experience={', '.join(profile.experience_levels)}; "
        f"skills={', '.join(profile.skills) or 'not set'}; "
        f"minimum_salary={salary}; sponsorship={sponsorship}; "
        f"delivery=up to {profile.result_count} matches on a {profile.frequency} schedule; "
        f"status={profile.status}"
    )


def _preferences(args: dict[str, Any]) -> JobSearchPreferencesPatch | None:
    raw = args.get("preferences")
    if not isinstance(raw, dict):
        return None
    return JobSearchPreferencesPatch.model_validate(raw)


class JobSearchAdapter:
    name = "job_search"
    input_schema = JobSearchToolInput

    def describe(self) -> str:
        return (
            "Control the user's My Job assistant. Read or update saved job-search "
            "preferences, pause/resume it, list matches, start a search, compare a "
            "specific job URL, or update a match stage and notes. For a temporary "
            "search, pass preferences to search_now without calling update_profile. "
            "For an ongoing change, call update_profile; use list modes add/remove "
            "unless the user explicitly asks to replace their roles or skills."
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
        user = _job_user.get()
        if user is None:
            return ToolResult(name=self.name, content="Job search is unavailable right now.")
        action = str(args.get("action") or "list")
        settings = _job_settings.get()

        async with SessionLocal() as session:
            profile = await job_search_service.get_profile_for_user(session, user.id)
            if profile is None:
                return ToolResult(
                    name=self.name,
                    content=(
                        "The user has not set up My Job yet. Suggest opening the "
                        "My Job screen to choose roles, location, and resume first."
                    ),
                )

            try:
                if action == "get_profile":
                    return ToolResult(name=self.name, content=_profile_summary(profile))

                if action == "update_profile":
                    patch = _preferences(args)
                    if patch is None:
                        return ToolResult(
                            name=self.name,
                            content="No job-search preferences were provided to update.",
                        )
                    if settings is None:
                        return ToolResult(
                            name=self.name,
                            content="My Job preferences cannot be changed right now.",
                        )
                    dashboard = await job_search_service.patch_profile(
                        session,
                        user,
                        settings,
                        patch,
                    )
                    saved_profile = dashboard.profile
                    if saved_profile is None:
                        return ToolResult(
                            name=self.name,
                            content="My Job could not confirm the saved preferences.",
                        )
                    return ToolResult(
                        name=self.name,
                        content=(
                            "Updated the saved My Job search. "
                            + _profile_summary(saved_profile)
                        ),
                    )

                if action == "update_status":
                    status = args.get("search_status")
                    if status not in {"active", "paused"} or settings is None:
                        return ToolResult(
                            name=self.name,
                            content="Choose active or paused for the My Job search.",
                        )
                    dashboard = await job_search_service.set_search_status(
                        session,
                        user,
                        settings,
                        status,
                    )
                    saved_profile = dashboard.profile
                    if saved_profile is None:
                        return ToolResult(
                            name=self.name,
                            content="My Job could not confirm the new status.",
                        )
                    return ToolResult(
                        name=self.name,
                        content=f"My Job is now {saved_profile.status}.",
                    )

                if action == "update_match":
                    match_id = args.get("match_id")
                    match_status = args.get("match_status")
                    if match_id is None or match_status is None or settings is None:
                        return ToolResult(
                            name=self.name,
                            content="A match ID and target stage are required.",
                        )
                    dashboard = await job_search_service.set_match_status(
                        session,
                        user,
                        settings,
                        UUID(str(match_id)),
                        match_status,
                        args.get("notes"),
                    )
                    changed = next(
                        (item for item in dashboard.matches if str(item.id) == str(match_id)),
                        None,
                    )
                    title = changed.title if changed is not None else "The job"
                    return ToolResult(
                        name=self.name,
                        content=f"{title} is now marked {match_status}.",
                    )

                one_off_values: dict[str, Any] = {}
                patch = _preferences(args)
                if patch is not None:
                    one_off_values = job_search_service.preference_values(profile, patch)
            except (ValueError, job_search_service.JobSearchError) as exc:
                detail = getattr(exc, "detail", str(exc))
                return ToolResult(name=self.name, content=f"My Job could not update: {detail}")

            matches = list(
                (
                    await session.scalars(
                        select(JobMatch)
                        .where(
                            JobMatch.profile_id == profile.id,
                            JobMatch.status != "hidden",
                        )
                        .order_by(JobMatch.found_at.desc())
                        .limit(_LIST_LIMIT)
                    )
                ).all()
            )
            profile_id = profile.id
            last_run_at = profile.last_run_at
            updated_at = profile.updated_at

        listing = "\n".join(_match_line(match) for match in matches) or "No matches yet."
        listing = wrap_untrusted("job matches", listing)

        if action == "analyze_job":
            job_url = str(args.get("job_url") or "").strip()
            if not job_url:
                return ToolResult(name=self.name, content="A job posting URL is required.")
            if settings is None:
                return ToolResult(
                    name=self.name,
                    content="Job comparison is unavailable right now.",
                )
            try:
                result = await job_search_runner.analyze_job_url(
                    settings,
                    profile_id=profile_id,
                    url=job_url,
                )
            except Exception:
                return ToolResult(
                    name=self.name,
                    content="That job posting could not be verified or analyzed right now.",
                )
            if result is None:
                return ToolResult(
                    name=self.name,
                    content="That URL is not a readable, specific job posting.",
                )
            reasons = "; ".join(result.match_reasons) or "No strong evidence found"
            gap = result.gap or "No clear gap was identified"
            score = f"{result.match_score}%" if result.match_score is not None else "unscored"
            return ToolResult(
                name=self.name,
                content=(
                    f"Verified job comparison: {result.title} at {result.company}; "
                    f"fit={score}; reasons={reasons}; gap={gap}; url={result.candidate.url}"
                ),
            )

        if action != "search_now":
            return ToolResult(name=self.name, content=listing)

        redis = _job_redis.get()
        now = datetime.now(UTC)
        if not job_search_service.can_request_manual_run(user, profile):
            note = (
                "On-demand searches need Recall Pro; the matches below are from "
                "the scheduled weekly search."
            )
        elif redis is None:
            note = "A fresh search cannot start right now; the matches below are the latest."
        elif (
            not one_off_values
            and last_run_at is not None
            and now - last_run_at < _MANUAL_RUN_COOLDOWN
            and not (updated_at is not None and updated_at > last_run_at)
        ):
            note = "A search ran a few minutes ago; the matches below are the latest."
        else:
            payload: dict[str, Any] = {"profile_id": str(profile_id), "manual": True}
            if one_off_values:
                payload["overrides"] = one_off_values
            override_key = hashlib.sha256(
                json.dumps(one_off_values, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()[:12]
            await enqueue(
                redis,
                "job_search_run",
                payload,
                dedupe_key=(
                    f"job_search_manual:{profile_id}:"
                    f"{last_run_at.isoformat() if last_run_at else 'never'}:{override_key}"
                ),
            )
            note = (
                "A temporary job search with the requested preferences just started; "
                "the saved My Job profile was not changed. New matches will appear shortly."
                if one_off_values
                else "A fresh job search just started; new matches will appear shortly."
            )
        return ToolResult(name=self.name, content=f"{note}\n\n{listing}")
