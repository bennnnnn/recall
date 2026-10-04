"""Crash-recoverable run execution with bounded provider spending and durable checkpoints."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select

from app.core.config import Settings
from app.core.db import SessionLocal
from app.models.orm import User
from app.modules.billing import is_pro
from app.modules.job_search.discovery import collect_candidates
from app.modules.job_search.models import JobSearchProfile, JobSearchRun
from app.modules.job_search.providers import EvidenceRanker, TavilyExtraction, TavilySearch
from app.modules.job_search.publishing import publish
from app.modules.job_search.ranking import (
    _profile_from_rows,
    _search_queries,
    _snapshot_with_overrides,
)
from app.modules.job_search.records import (
    PostingVerificationError,
    _AcceptedJob,
    _Candidate,
    _ProfileSnapshot,
)
from app.modules.job_search.service import JobSearchError
from app.services import model_catalog, quota

LEASE = timedelta(minutes=10)
MAX_ATTEMPTS = 3
logger = logging.getLogger(__name__)


async def _claim(run_id: UUID) -> tuple[_ProfileSnapshot, dict, dict, int | None] | None:
    async with SessionLocal() as session:
        run = await session.scalar(
            select(JobSearchRun).where(JobSearchRun.id == run_id).with_for_update()
        )
        if run is None or run.state not in {"queued", "running"}:
            return None
        now = datetime.now(UTC)
        if run.state == "running" and run.lease_until and run.lease_until > now:
            return None
        profile = await session.get(JobSearchProfile, run.profile_id)
        user = await session.get(User, profile.user_id) if profile else None
        reason = None
        if (
            profile is None
            or profile.status != "active"
            or (profile.revision or 1) != run.profile_revision
        ):
            run.state, reason = "cancelled", "Preferences changed or search paused"
        elif user is None or not is_pro(user):
            run.state, reason = "limited", "Recall Pro is required"
            profile.status, profile.suspension_reason = "paused", "pro_expired"
        elif run.attempts >= MAX_ATTEMPTS:
            run.state, reason = "failed", "Search could not complete after retries"
        if reason:
            run.failure_reason, run.finished_at = reason, now
            await session.commit()
            return None
        if profile is None or user is None:
            return None
        try:
            snapshot = _snapshot_with_overrides(_profile_from_rows(profile, user), run.overrides)
        except (ValueError, JobSearchError):
            run.state, run.failure_reason, run.finished_at = (
                "failed",
                "Temporary preferences need review",
                now,
            )
            await session.commit()
            return None
        run.state, run.started_at, run.lease_until = "running", run.started_at or now, now + LEASE
        run.attempts += 1
        await session.commit()
        return snapshot, dict(run.usage or {}), dict(run.checkpoint or {}), run.result_limit


async def _checkpoint(run_id: UUID, usage: dict, checkpoint: dict) -> None:
    async with SessionLocal() as session:
        run = await session.get(JobSearchRun, run_id)
        if run and run.state == "running":
            run.usage, run.checkpoint = dict(usage), dict(checkpoint)
            await session.commit()


async def _spending_allowed(settings: Settings, redis: Redis, profile: _ProfileSnapshot) -> None:
    async with SessionLocal() as session:
        user = await session.get(User, profile.user_id)
        current = await session.get(JobSearchProfile, profile.id)
        if user is None or not is_pro(user):
            raise PermissionError("Recall Pro is required")
        if (
            current is None
            or current.status != "active"
            or (current.revision or 1) != profile.revision
        ):
            raise PermissionError("Preferences changed or search paused")
    if await quota.global_spend_exceeded(redis, settings):
        raise PermissionError("Search spending limit reached")


async def execute_run(settings: Settings, redis: Redis, run_id: UUID) -> None:
    claimed = await _claim(run_id)
    if claimed is None:
        return
    profile, usage, checkpoint, result_limit = claimed
    if result_limit:
        profile = replace(profile, result_count=result_limit)
    try:
        if not settings.job_search_premium_enabled or not settings.web_search_enabled:
            raise PermissionError("My Job searches are temporarily unavailable")
        if "candidates" not in checkpoint:
            await _spending_allowed(settings, redis, profile)
            queries = _search_queries(profile)[:6]
            if usage.get("search_requests", 0) + len(queries) > 6:
                raise PostingVerificationError(
                    "Search interrupted before its checkpoint; retry with a new run"
                )
            for _query in queries:
                if not await quota.reserve_tavily_search(
                    redis, profile.user_id, limit=settings.daily_tavily_searches_pro
                ):
                    raise PermissionError(
                        "Daily search provider allowance reached. Try again tomorrow."
                    )
            usage["search_requests"] = usage.get("search_requests", 0) + len(queries)
            await _checkpoint(run_id, usage, checkpoint)
            reserved_cost = len(queries) * settings.job_search_tavily_credit_usd
            usage["search_reserved_usd"] = usage.get("search_reserved_usd", 0) + reserved_cost
            await quota.record_global_spend(redis, reserved_cost)
            provider = TavilySearch(settings)
            responses = await asyncio.gather(
                *(provider.search(query) for query in queries), return_exceptions=True
            )
            successful = [
                response for response in responses if not isinstance(response, BaseException)
            ]
            if queries and not successful:
                raise PostingVerificationError("Search provider is unavailable")
            usage["failed_search_queries"] = len(responses) - len(successful)
            usage["search_provider_usage"] = [response.usage for response in successful]
            candidates = collect_candidates(successful)
            checkpoint["candidates"] = [asdict(item) for item in candidates]
            await _checkpoint(run_id, usage, checkpoint)
        candidates = [_Candidate(**item) for item in checkpoint["candidates"]]
        if candidates and "pages" not in checkpoint:
            await _spending_allowed(settings, redis, profile)
            if usage.get("posting_fetches", 0) + len(candidates) > 30:
                raise PostingVerificationError(
                    "Posting verification interrupted before its checkpoint"
                )
            usage["posting_fetches"] = usage.get("posting_fetches", 0) + len(candidates)
            await _checkpoint(run_id, usage, checkpoint)
            reserved_cost = ((len(candidates) + 4) // 5) * settings.job_search_tavily_credit_usd
            usage["extraction_reserved_usd"] = (
                usage.get("extraction_reserved_usd", 0) + reserved_cost
            )
            await quota.record_global_spend(redis, reserved_cost)
            pages, provider_usage = await TavilyExtraction(settings).extract(
                [item.url for item in candidates]
            )
            checkpoint["pages"], usage["extraction_provider_usage"] = pages, provider_usage
            await _checkpoint(run_id, usage, checkpoint)
        verified = [
            replace(item, page_text=checkpoint.get("pages", {}).get(item.url))
            for item in candidates
            if checkpoint.get("pages", {}).get(item.url)
        ]
        usage["unreadable_postings"] = len(candidates) - len(verified)
        usage["candidate_count"] = len(candidates)
        usage["verified_count"] = len(verified)
        if candidates and not verified:
            raise PostingVerificationError("No posting pages could be read")
        await _spending_allowed(settings, redis, profile)
        model_usage: dict[str, int] = {}
        try:
            accepted = await EvidenceRanker(settings).rank(profile, verified, model_usage)
        finally:
            usage["model_input_tokens"] = usage.get("model_input_tokens", 0) + model_usage.get(
                "input", 0
            )
            usage["model_output_tokens"] = usage.get("model_output_tokens", 0) + model_usage.get(
                "output", 0
            )
            model_cost = model_catalog.estimate_cost_usd(
                "gemini-flash",
                input_tokens=model_usage.get("input", 0),
                output_tokens=model_usage.get("output", 0),
            )
            if model_cost:
                await quota.record_global_spend(redis, model_cost)
            usage["model_estimated_usd"] = usage.get("model_estimated_usd", 0) + (model_cost or 0)
            usage["failed_ranking_batches"] = model_usage.get("failed_ranking_batches", 0)
        partial = bool(
            usage.get("failed_search_queries")
            or usage.get("unreadable_postings")
            or usage.get("failed_ranking_batches")
            or model_usage.get("unassessed_postings")
        )
        # Deduplicate only URL or explicit employer+requisition identity.
        distinct: dict[str, _AcceptedJob] = {}
        for item in accepted:
            key = item.posting_identity or item.candidate.canonical_url
            distinct.setdefault(key, item)
        await publish(
            run_id,
            profile,
            list(distinct.values())[: profile.result_count],
            partial=partial,
            usage=usage,
        )
    except Exception as exc:
        async with SessionLocal() as session:
            run = await session.get(JobSearchRun, run_id)
            if run and run.state == "running":
                run.state = "limited" if isinstance(exc, PermissionError) else "failed"
                run.failure_reason = (
                    str(exc)
                    if isinstance(exc, PermissionError | PostingVerificationError)
                    else "Search provider could not complete the request"
                )
                run.finished_at, run.lease_until, run.usage = datetime.now(UTC), None, usage
                profile_row = await session.get(JobSearchProfile, run.profile_id)
                if profile_row:
                    profile_row.last_run_at, profile_row.last_run_status = (
                        datetime.now(UTC),
                        "error",
                    )
                    if not run.manual:
                        profile_row.next_run_at = datetime.now(UTC) + timedelta(minutes=15)
                await session.commit()
        # Failed requests are terminal and visible. Crash recovery reclaims only
        # leased runs; it never silently spends a second logical reservation.

    finally:
        async with SessionLocal() as session:
            outcome = await session.get(JobSearchRun, run_id)
            if outcome:
                logger.info(
                    "my_job_run_finished",
                    extra={
                        "run_id": str(run_id),
                        "state": outcome.state,
                        "partial": outcome.partial,
                        "qualifying_count": outcome.qualifying_count,
                        "possible_count": outcome.possible_count,
                        "new_match_count": outcome.new_match_count,
                        "usage": usage,
                        "latency_seconds": (
                            outcome.finished_at - outcome.created_at
                        ).total_seconds()
                        if outcome.finished_at
                        else None,
                    },
                )
