"""Posting analysis and compatibility entry point over durable My Job runs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.db import SessionLocal
from app.models.orm import User
from app.modules.job_search.models import JobSearchProfile
from app.modules.job_search.posting import (
    _is_listing_page,
    _source_for_url,
    canonicalize_job_url,
)
from app.modules.job_search.ranking import _profile_from_rows
from app.modules.job_search.records import (
    JobSearchRunResult,
    _AcceptedJob,
    _Candidate,
    _ProfileSnapshot,
)


async def _load_snapshot(
    profile_id: UUID,
    *,
    require_active: bool = True,
) -> _ProfileSnapshot | None:
    async with SessionLocal() as session:
        profile = await session.get(JobSearchProfile, profile_id)
        if profile is None or (require_active and profile.status != "active"):
            return None
        user = await session.get(User, profile.user_id)
        if user is None:
            return None
        snapshot = _profile_from_rows(profile, user)
        if not snapshot.is_pro:
            profile.status = "paused"
            profile.suspension_reason = "pro_expired"
            await session.commit()
            return None
        return snapshot


async def analyze_job_url(
    settings: Settings,
    *,
    profile_id: UUID,
    url: str,
    redis: Redis,
) -> _AcceptedJob | None:
    """Verify and compare one specific posting without changing the saved search."""
    from app.modules.job_search.service import JobSearchError

    if not settings.job_search_premium_enabled or not settings.web_search_enabled:
        raise JobSearchError("Job comparison is unavailable right now", status_code=503)
    canonical = canonicalize_job_url(url)
    if not canonical or _is_listing_page(url, ""):
        return None
    profile = await _load_snapshot(profile_id, require_active=False)
    if profile is None:
        return None
    from app.modules.job_search.providers import TavilyExtraction
    from app.modules.job_search.spending import check_spending, record_tokens
    from app.services.quota import record_global_spend

    async with SessionLocal() as session:
        user = await session.get(User, profile.user_id)
        if user is None:
            return None
        await check_spending(session, user, redis, settings)
    await record_global_spend(redis, settings.job_search_tavily_credit_usd)
    pages, _usage = await TavilyExtraction(settings).extract([url])
    posting = (pages.get(url) or "").strip()
    if not posting:
        return None
    first_line = next(
        (line.strip() for line in posting.splitlines() if line.strip()),
        "Job posting",
    )
    candidate = _Candidate(
        candidate_id=0,
        title=first_line[:240],
        url=url,
        canonical_url=canonical[:2000],
        snippet=" ".join(posting.split())[:800],
        source=_source_for_url(url),
        page_text=posting,
    )
    from app.modules.job_search.providers import EvidenceRanker

    async with SessionLocal() as session:
        user = await session.get(User, profile.user_id)
        if user is None:
            return None
        await check_spending(session, user, redis, settings)
    usage: dict[str, int] = {}
    try:
        accepted = await EvidenceRanker(settings).rank(profile, [candidate], usage)
    finally:
        await record_tokens(redis, "gemini-flash", usage)
    return accepted[0] if accepted else None


async def run_job_search(
    settings: Settings,
    redis: Redis,
    *,
    profile_id: UUID,
    manual: bool = False,
    overrides: dict[str, Any] | None = None,
    result_limit: int | None = None,
) -> JobSearchRunResult:
    """Compatibility callers submit to the same durable queue as chat and screens."""
    from app.modules.job_search.runs import submit_run

    async with SessionLocal() as session:
        profile = await session.get(JobSearchProfile, profile_id)
        user = await session.get(User, profile.user_id) if profile else None
        if profile is None or user is None:
            return JobSearchRunResult(status="unavailable")
        run = await submit_run(
            session,
            user,
            settings,
            redis,
            manual=manual,
            overrides=overrides,
            result_limit=result_limit,
        )
        return JobSearchRunResult(status="queued", run_id=run.id)
