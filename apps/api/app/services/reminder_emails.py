"""Opt-in transactional email reminders (todo due + learning nudges).

Runs on the worker scheduler only — never on the chat path. Welcome and Pro
receipt emails stay on the Redis jobs stream and are not gated by
``email_reminders_enabled``.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Project, TodoItem, User
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.services import daily_learning, learning_insights
from app.services import time_context as time_context_service
from app.services import transactional_email as tx_email
from app.services.reminder_timing import (
    MAX_REMINDER_LEAD_MINUTES,
    OVERDUE_MAX_HOURS,
    resolve_reminder_lead_minutes,
    should_notify_todo,
)

logger = logging.getLogger(__name__)

LEARNING_EMAIL_REDIS_PREFIX = "recall:email:learning"


def _user_local_hour(user: User) -> int:
    tz = time_context_service.resolve_timezone(user.timezone)
    return datetime.now(tz).hour


def _user_day_key(user: User) -> str:
    tz = time_context_service.resolve_timezone(user.timezone)
    return datetime.now(tz).strftime("%Y-%m-%d")


def _learning_redis_key(user_id: UUID, day_key: str) -> str:
    return f"{LEARNING_EMAIL_REDIS_PREFIX}:{user_id}:{day_key}"


async def process_todo_reminder_emails(
    session: AsyncSession,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> int:
    now = now or datetime.now(UTC)
    window_end = now + timedelta(minutes=MAX_REMINDER_LEAD_MINUTES)
    overdue_cutoff = now - timedelta(hours=OVERDUE_MAX_HOURS)

    result = await session.execute(
        select(TodoItem, User)
        .join(User, User.id == TodoItem.user_id)
        .where(
            TodoItem.checked.is_(False),
            TodoItem.due_at.isnot(None),
            TodoItem.email_sent_at.is_(None),
            User.email_reminders_enabled.is_(True),
            (
                (TodoItem.due_at <= window_end)
                | ((TodoItem.due_at < now) & (TodoItem.due_at >= overdue_cutoff))
            ),
        )
    )
    rows = list(result.all())
    if not rows:
        return 0

    sent = 0
    for todo, user in rows:
        if todo.due_at is None or not user.email:
            continue
        lead = resolve_reminder_lead_minutes(getattr(user, "reminder_lead_minutes", None))
        if not should_notify_todo(todo.due_at, now=now, lead_minutes=lead):
            continue
        is_overdue = todo.due_at < now
        title = "Overdue reminder" if is_overdue else "Reminder"
        ok = await tx_email.send_todo_reminder(settings, user, title=title, content=todo.content)
        if ok:
            todo.email_sent_at = now
            sent += 1

    if sent:
        await session.commit()
    return sent


async def process_learning_nudge_emails(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> int:
    _ = now
    result = await session.execute(select(User).where(User.email_reminders_enabled.is_(True)))
    users = list(result.scalars().all())
    if not users:
        return 0

    candidates: list[tuple[User, str]] = []
    for user in users:
        if not user.email:
            continue
        if _user_local_hour(user) < settings.push_learning_hour:
            continue
        day_key = _user_day_key(user)
        redis_key = _learning_redis_key(user.id, day_key)
        if not await redis.set(redis_key, "1", nx=True, ex=86_400):
            continue
        candidates.append((user, redis_key))

    if not candidates:
        return 0

    user_by_id = {user.id: user for user, _ in candidates}
    user_ids = list(user_by_id)

    projects = await projects_repo.list_for_users(session, user_ids, include_archived=False)
    learning_projects = [p for p in projects if p.kind in ("language", "vocabulary", "trivia")]
    projects_by_user: dict[UUID, list[Project]] = {}
    for project in learning_projects:
        projects_by_user.setdefault(project.user_id, []).append(project)

    timezone_by_project = {
        project.id: user_by_id[project.user_id].timezone
        for project in learning_projects
        if project.user_id in user_by_id
    }
    stats_by_project = await project_items_repo.count_stats_by_project(
        session,
        [project.id for project in learning_projects],
        timezone_by_project=timezone_by_project,
    )
    for project in learning_projects:
        raw = stats_by_project.get(project.id)
        if raw is None:
            continue
        stats_by_project[project.id] = learning_insights.enrich_learning_stats(
            raw,
            project=project,
            items=[],
            timezone_name=timezone_by_project.get(project.id, "UTC"),
        )

    sent = 0
    for user, redis_key in candidates:
        user_projects = projects_by_user.get(user.id, [])
        best_pick = learning_insights.best_learning_nudge_for_user(
            user_projects,
            stats_by_project,
            daily_goal_for=daily_learning.resolve_daily_goal,
        )
        if best_pick is None:
            await redis.delete(redis_key)
            continue

        _project, body, _score, _nudge_type, _payload = best_pick
        ok = await tx_email.send_learning_nudge(settings, user, body=body)
        if ok:
            sent += 1
        else:
            await redis.delete(redis_key)

    return sent


async def run_email_reminder_cycle(session: AsyncSession, redis: Redis, settings: Settings) -> int:
    if not settings.email_enabled or not settings.email_reminders_scheduler_enabled:
        return 0
    now = datetime.now(UTC)
    todo_count = await process_todo_reminder_emails(session, settings, now=now)
    learning_count = await process_learning_nudge_emails(session, redis, settings, now=now)
    return todo_count + learning_count
