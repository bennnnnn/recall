"""Execute one dedicated My Job search without a hidden chat or prompt row."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import SessionLocal
from app.core.redis_lock import acquire_lock, release_lock
from app.gateways import litellm_gateway, web_search_gateway
from app.models.orm import User
from app.modules.job_search import notifications as job_search_notifications
from app.modules.job_search.models import JobMatch, JobSearchProfile
from app.modules.job_search.posting import (
    _POSTING_EXTRACT_CHARS,
    _canonical_url_hash,
    _clean_posting_title,
    _dedupe_accepted,
    _explicit_place_mode,
    _extract_company_logo_url,
    _extract_experience,
    _extract_location,
    _extract_role_summary,
    _extract_salary,
    _extract_work_mode,
    _fallback_required_skills,
    _grounded_title,
    _is_board_name,
    _is_generic_employer,
    _is_listing_page,
    _is_listing_title,
    _named_salary,
    _source_for_url,
    _title_and_company,
    _title_company_key,
    _verified_fallback_identity,
    canonicalize_job_url,
)
from app.modules.job_search.ranking import (
    _fallback_rank,
    _keyword_scores,
    _obvious_mismatch,
    _passes_verified_constraints,
    _profile_from_rows,
    _ranking_messages,
    _search_queries,
    _snapshot_with_overrides,
    _specific_model_reasons,
    _strategic_match_assessment,
)
from app.modules.job_search.records import (
    JobSearchRunResult,
    PostingVerificationError,
    _AcceptedJob,
    _Candidate,
    _ProfileSnapshot,
    _RankedPayload,
)
from app.modules.todos import next_recurring_due

logger = logging.getLogger(__name__)

_RUN_LOCK_SECONDS = 10 * 60
_RETRY_DELAY = timedelta(minutes=15)
_MAX_CANDIDATES = 36


async def _find_candidates(
    settings: Settings,
    profile: _ProfileSnapshot,
) -> list[_Candidate]:
    results = await asyncio.gather(
        *(
            web_search_gateway.search_web(
                settings,
                query,
                max_results=10,
            )
            for query in _search_queries(profile)
        )
    )
    candidates: list[_Candidate] = []
    seen: set[str] = set()
    for hits in results:
        for hit in hits:
            canonical = canonicalize_job_url(hit.url)
            if not canonical or canonical in seen:
                continue
            if _is_listing_page(hit.url, hit.title):
                continue
            seen.add(canonical)
            candidates.append(
                _Candidate(
                    candidate_id=len(candidates),
                    title=" ".join(hit.title.strip().split())[:240],
                    url=hit.url.strip()[:2000],
                    canonical_url=canonical[:2000],
                    snippet=" ".join(hit.snippet.strip().split())[:800],
                    source=_source_for_url(hit.url),
                )
            )
            if len(candidates) >= _MAX_CANDIDATES:
                return candidates
    return candidates


async def _fetch_posting_pages(
    settings: Settings,
    profile: _ProfileSnapshot,
    eligible: list[_Candidate],
) -> list[_Candidate]:
    """Narrow to a keyword shortlist and attach full posting text when possible.

    Snippets rarely disclose salary or experience, so ranking over page text is
    much sharper. If no posting can be fetched, fail visibly instead of turning
    unverifiable snippets into confident job cards.
    """
    if not settings.job_search_page_fetch_enabled:
        return eligible
    limit = max(1, settings.job_search_page_fetch_max)
    shortlist = [candidate for _, candidate in _keyword_scores(profile, eligible)[:limit]]
    if shortlist and all(item.page_text for item in shortlist):
        return shortlist
    missing = [item.url for item in shortlist if not item.page_text]
    pages = await web_search_gateway.extract_pages(
        settings,
        missing,
        max_chars=_POSTING_EXTRACT_CHARS,
    )
    verified = [
        replace(item, page_text=item.page_text or pages.get(item.url))
        for item in shortlist
        if item.page_text or pages.get(item.url)
    ]
    if not verified:
        raise PostingVerificationError("No candidate posting page could be verified")
    return verified


async def _rank_candidates(
    settings: Settings,
    profile: _ProfileSnapshot,
    candidates: list[_Candidate],
) -> list[_AcceptedJob]:
    eligible = [item for item in candidates if not _obvious_mismatch(profile, item)]
    if not eligible:
        return []

    eligible = await _fetch_posting_pages(settings, profile, eligible)

    ranked = await litellm_gateway.complete_structured(
        settings=settings,
        # This is a foreground search. The fast function-capable route returns
        # the ranking schema in seconds; the background memory route can take
        # tens of seconds and sometimes emits prose instead of valid JSON.
        model_alias="gemini-flash",
        messages=_ranking_messages(profile, eligible),
        schema=_RankedPayload,
        max_tokens=2500,
        timeout_seconds=20.0,
    )
    if ranked is None or not ranked.jobs:
        return _fallback_rank(profile, eligible)

    by_id = {item.candidate_id: item for item in eligible}
    accepted: list[_AcceptedJob] = []
    seen: set[int] = set()
    for item in ranked.jobs:
        candidate = by_id.get(item.candidate_id)
        if candidate is None or item.candidate_id in seen:
            continue
        seen.add(item.candidate_id)
        page_title: str | None = None
        page_company: str | None = None
        if candidate.page_text:
            page_title, page_company = _verified_fallback_identity(candidate)
        title, company = _title_and_company(candidate.title, candidate.source)
        if page_title:
            title = page_title
        if page_company and page_company != "Unknown employer":
            company = page_company
        # The LLM title wins only when it is grounded in the actual posting —
        # a composed label like "Registered Nurse (ICU) — Berlin" is worse than
        # the page's real headline. A fetched heading already is that headline.
        if (
            page_title is None
            and item.title is not None
            and "##" not in item.title
            and not _is_listing_title(item.title)
            and _grounded_title(item.title, candidate)
        ):
            title = item.title
        title = _clean_posting_title(title)
        if _is_listing_title(title):
            # A list/category page that slipped past intake never becomes a card.
            continue
        if (
            item.company is not None
            and not _is_board_name(item.company)
            and not _is_generic_employer(item.company)
            and (page_company in (None, "Unknown employer") or _is_generic_employer(company))
        ):
            company = item.company
        if company == "Unknown employer":
            continue
        place_mode = _explicit_place_mode(candidate.page_text or "")
        work_mode = place_mode or item.work_mode or _extract_work_mode(candidate)
        location = _extract_location(candidate) or item.location
        if _named_salary(candidate.page_text or ""):
            salary = _extract_salary(candidate)
        else:
            salary = item.salary or _extract_salary(candidate)
        experience = item.experience or _extract_experience(candidate)
        required_skills = item.required_skills or _fallback_required_skills(profile, candidate)
        if not _passes_verified_constraints(
            profile,
            candidate,
            work_mode=work_mode,
            salary=salary,
            location=location,
        ):
            continue
        strategic_reasons, strategic_gap = _strategic_match_assessment(
            profile,
            required_skills=required_skills,
            experience=experience,
            work_mode=work_mode,
            location=location,
            salary=salary,
        )
        match_reasons = list(
            dict.fromkeys([*strategic_reasons, *_specific_model_reasons(item.match_reasons)])
        )[:5]
        accepted.append(
            _AcceptedJob(
                candidate=candidate,
                title=title,
                company=company,
                company_logo_url=_extract_company_logo_url(candidate, company),
                location=location,
                work_mode=work_mode,
                salary=salary,
                experience=experience,
                match_score=item.match_score,
                posted_at=item.posted_at,
                summary=(
                    _extract_role_summary(candidate) or item.summary or candidate.snippet or None
                ),
                required_skills=required_skills,
                match_reasons=match_reasons,
                gap=strategic_gap or item.gap,
            )
        )
        if len(accepted) >= profile.result_count:
            break
    return accepted or _fallback_rank(profile, eligible)


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
        hidden_matches = list(
            (
                await session.scalars(
                    select(JobMatch)
                    .where(
                        JobMatch.profile_id == profile.id,
                        JobMatch.status == "hidden",
                    )
                    .limit(200)
                )
            ).all()
        )
        snapshot = _profile_from_rows(profile, user, hidden_matches=hidden_matches)
        if not snapshot.is_pro and not (
            snapshot.result_count == 5 and snapshot.frequency == "weekly"
        ):
            profile.status = "paused"
            profile.last_run_at = datetime.now(UTC)
            profile.last_run_status = "error"
            await session.commit()
            return None
        return snapshot


async def analyze_job_url(
    settings: Settings,
    *,
    profile_id: UUID,
    url: str,
) -> _AcceptedJob | None:
    """Verify and compare one specific posting without changing the saved search."""
    canonical = canonicalize_job_url(url)
    if not canonical or _is_listing_page(url, ""):
        return None
    profile = await _load_snapshot(profile_id, require_active=False)
    if profile is None:
        return None
    pages = await web_search_gateway.extract_pages(
        settings,
        [url],
        max_chars=_POSTING_EXTRACT_CHARS,
    )
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
    accepted = await _rank_candidates(settings, profile, [candidate])
    return accepted[0] if accepted else None


async def _finish_run(
    settings: Settings,
    profile: _ProfileSnapshot,
    accepted: list[_AcceptedJob],
    *,
    manual: bool,
    run_status: Literal["ok", "error", "skipped_quota"],
) -> None:
    now = datetime.now(UTC)
    new_count = 0
    async with SessionLocal() as session:
        current = await session.get(JobSearchProfile, profile.id)
        if current is None:
            return

        existing = {
            match.canonical_url: match
            for match in (
                await session.scalars(select(JobMatch).where(JobMatch.profile_id == profile.id))
            ).all()
        }
        # Cross-source identity: the same opening on another board must update
        # the existing card, not insert a duplicate under a second URL.
        existing_keys = {
            _title_company_key(match.title, match.company): match for match in existing.values()
        }
        for item in _dedupe_accepted(accepted):
            match = existing.get(item.candidate.canonical_url)
            if match is None:
                match = existing_keys.get(_title_company_key(item.title, item.company))
            if match is None:
                match = JobMatch(
                    profile_id=profile.id,
                    canonical_url=item.candidate.canonical_url,
                    canonical_url_hash=_canonical_url_hash(item.candidate.canonical_url),
                    url=item.candidate.url,
                    title=item.title,
                    company=item.company,
                    company_logo_url=item.company_logo_url,
                    location=item.location,
                    work_mode=item.work_mode,
                    salary=item.salary,
                    experience=item.experience,
                    match_score=item.match_score,
                    source=item.candidate.source,
                    posted_at=item.posted_at,
                    summary=item.summary,
                    required_skills=item.required_skills,
                    match_reasons=item.match_reasons,
                    gap=item.gap,
                    status="new",
                    found_at=now,
                )
                session.add(match)
                existing[item.candidate.canonical_url] = match
                new_count += 1
            else:
                match.url = item.candidate.url
                match.title = item.title
                match.company = item.company
                match.company_logo_url = item.company_logo_url or match.company_logo_url
                match.location = item.location
                match.work_mode = item.work_mode
                match.salary = item.salary
                match.experience = item.experience
                match.match_score = item.match_score
                match.source = item.candidate.source
                match.posted_at = item.posted_at
                match.summary = item.summary
                match.required_skills = item.required_skills or match.required_skills
                match.match_reasons = item.match_reasons
                match.gap = item.gap

        current.last_run_at = now
        current.last_run_status = run_status
        if not manual and current.status == "active" and run_status == "ok":
            current.next_run_at = next_recurring_due(
                current.next_run_at,
                current.frequency,  # type: ignore[arg-type]
                now=now,
                timezone=profile.timezone,
            )
        elif not manual and current.status == "active" and run_status == "error":
            # Keep failures retryable soon instead of silently skipping a full
            # daily/weekly cadence. The durable worker also retries immediately.
            current.next_run_at = now + _RETRY_DELAY
        await session.commit()

        if run_status == "ok" and new_count > 0:
            try:
                await job_search_notifications.notify_job_matches_ready(
                    session,
                    settings,
                    user_id=profile.user_id,
                    profile_id=profile.id,
                    new_match_count=new_count,
                )
            except Exception:
                # A push outage must never turn a successfully persisted search
                # into a failed run or advance its schedule twice.
                logger.exception(
                    "My Job notification failed profile_id=%s",
                    profile.id,
                )


async def run_job_search(
    settings: Settings,
    redis: Redis,
    *,
    profile_id: UUID,
    manual: bool = False,
    overrides: dict[str, Any] | None = None,
    result_limit: int | None = None,
) -> JobSearchRunResult:
    """Search, rank, persist, and notify for one profile occurrence."""
    token = await acquire_lock(
        redis,
        f"recall:job-search:run:{profile_id}",
        _RUN_LOCK_SECONDS,
    )
    if token is None:
        return JobSearchRunResult(status="busy")

    profile: _ProfileSnapshot | None = None
    try:
        profile = await _load_snapshot(profile_id)
        if profile is None:
            return JobSearchRunResult(status="unavailable")
        profile = _snapshot_with_overrides(profile, overrides)
        if result_limit is not None:
            max_results = 15 if profile.is_pro else 5
            if not 1 <= result_limit <= max_results:
                raise ValueError(f"result_limit must be between 1 and {max_results}")
            profile = replace(profile, result_count=result_limit)
        candidates = await _find_candidates(settings, profile)
        accepted = _dedupe_accepted(await _rank_candidates(settings, profile, candidates))
        await _finish_run(
            settings,
            profile,
            accepted,
            manual=manual,
            run_status="ok",
        )
        return JobSearchRunResult(
            status="completed",
            canonical_urls=tuple(item.candidate.canonical_url for item in accepted),
        )
    except Exception:
        logger.exception("My Job search failed profile_id=%s", profile_id)
        if profile is not None:
            await _finish_run(
                settings,
                profile,
                [],
                manual=manual,
                run_status="error",
            )
        raise
    finally:
        await release_lock(
            redis,
            f"recall:job-search:run:{profile_id}",
            token,
        )
