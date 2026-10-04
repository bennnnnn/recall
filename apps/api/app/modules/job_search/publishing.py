"""Publish verified results and their notification event in one transaction."""

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.orm import User
from app.modules.billing import is_pro
from app.modules.job_search.models import (
    JobMatch,
    JobNotificationEvent,
    JobSearchProfile,
    JobSearchRun,
)
from app.modules.job_search.posting import _canonical_url_hash
from app.modules.job_search.records import _AcceptedJob, _ProfileSnapshot
from app.modules.job_search.schemas import JobSearchFrequency
from app.modules.todos import next_recurring_due


async def publish(
    run_id: UUID,
    profile: _ProfileSnapshot,
    accepted: list[_AcceptedJob],
    *,
    partial: bool,
    usage: dict,
) -> list[UUID]:
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        current = await session.scalar(
            select(JobSearchProfile).where(JobSearchProfile.id == profile.id).with_for_update()
        )
        run = await session.scalar(
            select(JobSearchRun).where(JobSearchRun.id == run_id).with_for_update()
        )
        if run is None or run.state != "running":
            return []
        user = await session.get(User, profile.user_id)
        if (
            current is None
            or current.status != "active"
            or (current.revision or 1) != run.profile_revision
        ):
            run.state, run.failure_reason = (
                "cancelled",
                "Preferences changed or search paused before completion",
            )
        elif user is None or not is_pro(user):
            run.state, run.failure_reason = "limited", "Recall Pro expired before completion"
            current.status, current.suspension_reason = "paused", "pro_expired"
        else:
            canonical = [item.candidate.canonical_url for item in accepted]
            identities = [item.posting_identity for item in accepted if item.posting_identity]
            from sqlalchemy import or_

            rows = list(
                (
                    await session.scalars(
                        select(JobMatch).where(
                            JobMatch.profile_id == current.id,
                            or_(
                                JobMatch.canonical_url.in_(canonical),
                                JobMatch.posting_identity.in_(identities),
                            ),
                        )
                    )
                ).all()
            )
            by_url = {row.canonical_url: row for row in rows}
            by_identity = {row.posting_identity: row for row in rows if row.posting_identity}
            ids: list[UUID] = []
            new_count = 0
            published = []
            for item in accepted:
                match = by_url.get(item.candidate.canonical_url)
                if match is None and item.posting_identity:
                    match = by_identity.get(item.posting_identity)
                if match is not None and match.status == "hidden":
                    continue
                fresh = match is None
                published.append(item)
                if match is None:
                    match = JobMatch(
                        profile_id=current.id,
                        canonical_url=item.candidate.canonical_url,
                        canonical_url_hash=_canonical_url_hash(item.candidate.canonical_url),
                        found_at=now,
                        status="new",
                    )
                    session.add(match)
                first_qualifying = item.match_kind == "qualifying" and (
                    fresh or match.match_kind != "qualifying"
                )
                if first_qualifying and match.status != "hidden":
                    new_count += 1
                for field in (
                    "title",
                    "company",
                    "company_logo_url",
                    "location",
                    "work_mode",
                    "salary",
                    "experience",
                    "match_score",
                    "posted_at",
                    "summary",
                    "required_skills",
                    "match_reasons",
                    "gap",
                    "assessment",
                    "match_kind",
                    "posting_identity",
                ):
                    setattr(match, field, getattr(item, field))
                match.url, match.source = item.candidate.url, item.candidate.source
                match.assessment_revision, match.checked_at = run.profile_revision, now
                await session.flush()
                ids.append(match.id)
                by_url[item.candidate.canonical_url] = match
                if item.posting_identity:
                    by_identity[item.posting_identity] = match
            run.match_ids = [str(value) for value in ids]
            run.qualifying_count = sum(item.match_kind == "qualifying" for item in published)
            run.possible_count = sum(item.match_kind == "possible" for item in published)
            run.new_match_count, run.partial, run.usage = new_count, partial, usage
            run.state, run.failure_reason = "completed", None
            current.last_run_at, current.last_run_status = now, "ok"
            current.search_cursor = (current.search_cursor or 0) + 6
            if not run.manual:
                current.next_run_at = next_recurring_due(
                    current.next_run_at,
                    cast(JobSearchFrequency, current.frequency),
                    now=now,
                    timezone=profile.timezone,
                )
            if new_count:
                session.add(
                    JobNotificationEvent(
                        run_id=run.id, user_id=profile.user_id, new_match_count=new_count
                    )
                )
        run.finished_at, run.lease_until = now, None
        await session.commit()
        return [UUID(value) for value in run.match_ids] if run.state == "completed" else []
