"""Shared learning-nudge candidate batching for push and email channels."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Project, User
from app.repositories import projects as projects_repo
from app.services import daily_learning, learning_insights
from app.services.projects import stats as project_stats
from app.services.reminder_timing import learning_dedupe_key, user_day_key, user_local_hour

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LearningNudgePick:
    user: User
    redis_key: str
    body: str
    payload: dict[str, str]
    project: Project
    nudge_type: learning_insights.NudgeType
    score: float


async def claim_learning_candidates(
    redis: Redis,
    users: list[User],
    *,
    learning_hour: int,
    redis_prefix: str,
    require_email: bool = False,
) -> list[tuple[User, str]]:
    """Claim today's Redis lock for users due for a learning nudge."""
    candidates: list[tuple[User, str]] = []
    for user in users:
        if require_email and not user.email:
            continue
        if user_local_hour(user) < learning_hour:
            continue
        day_key = user_day_key(user)
        redis_key = learning_dedupe_key(redis_prefix, user.id, day_key)
        if not await redis.set(redis_key, "1", nx=True, ex=86_400):
            continue
        candidates.append((user, redis_key))
    return candidates


async def load_learning_stats_for_candidates(
    session: AsyncSession,
    candidates: list[tuple[User, str]],
) -> tuple[dict[UUID, list[Project]], dict[UUID, dict[str, Any]]]:
    """Batch-load learning projects + enriched stats for claimed candidates."""
    user_by_id = {user.id: user for user, _ in candidates}
    user_ids = list(user_by_id)

    projects = await projects_repo.list_for_users(session, user_ids, include_archived=False)
    learning_projects = [
        project for project in projects if learning_insights.is_learning_project_kind(project.kind)
    ]
    projects_by_user: dict[UUID, list[Project]] = {}
    for project in learning_projects:
        projects_by_user.setdefault(project.user_id, []).append(project)

    timezone_by_project = {
        project.id: user_by_id[project.user_id].timezone
        for project in learning_projects
        if project.user_id in user_by_id
    }
    stats_by_project = await project_stats.count_stats_by_project(
        session,
        [project.id for project in learning_projects],
        timezone_by_project=timezone_by_project,
    )
    for project in learning_projects:
        raw = stats_by_project.get(project.id)
        if raw is None:
            continue
        # Isolate per-project enrichment so one bad row can't kill the cycle.
        try:
            stats_by_project[project.id] = learning_insights.enrich_learning_stats(
                raw,
                project=project,
                items=[],
                timezone_name=timezone_by_project.get(project.id, "UTC"),
            )
        except Exception:
            logger.exception(
                "Learning stat enrichment failed user_id=%s project_id=%s",
                project.user_id,
                project.id,
            )
            continue

    return projects_by_user, stats_by_project


async def collect_learning_nudge_picks(
    session: AsyncSession,
    redis: Redis,
    users: list[User],
    *,
    learning_hour: int,
    redis_prefix: str,
    require_email: bool = False,
) -> list[LearningNudgePick]:
    """Claim candidates, load stats, and return best nudge picks per user.

    Releases the Redis day lock when a user has no sendable nudge.
    """
    candidates = await claim_learning_candidates(
        redis,
        users,
        learning_hour=learning_hour,
        redis_prefix=redis_prefix,
        require_email=require_email,
    )
    if not candidates:
        return []

    projects_by_user, stats_by_project = await load_learning_stats_for_candidates(
        session, candidates
    )

    picks: list[LearningNudgePick] = []
    for user, redis_key in candidates:
        try:
            best_pick = learning_insights.best_learning_nudge_for_user(
                projects_by_user.get(user.id, []),
                stats_by_project,
                daily_goal_for=daily_learning.resolve_daily_goal,
            )
            if best_pick is None:
                await redis.delete(redis_key)
                continue
            project, body, score, nudge_type, payload = best_pick
            picks.append(
                LearningNudgePick(
                    user=user,
                    redis_key=redis_key,
                    body=body,
                    payload=payload,
                    project=project,
                    nudge_type=nudge_type,
                    score=score,
                )
            )
        except Exception:
            logger.exception("Learning nudge pick failed user_id=%s", user.id)
            continue
    return picks
