"""Build and dispatch Expo push notifications for reminders, learning, and email."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways import expo_push_gateway
from app.models.orm import PushToken, SuggestedReminder, TodoItem, User
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.repositories import push_tokens as push_repo
from app.services import time_context as time_context_service
from app.services.projects import group_programming_items
from app.services.reminder_timing import (
    MAX_REMINDER_LEAD_MINUTES,
    OVERDUE_MAX_HOURS,
    resolve_reminder_lead_minutes,
    should_notify_todo,
)

logger = logging.getLogger(__name__)

LEARNING_REDIS_PREFIX = "recall:push:learning"


def _user_local_hour(user: User) -> int:
    tz = time_context_service.resolve_timezone(user.timezone)
    return datetime.now(tz).hour


def _user_day_key(user: User) -> str:
    tz = time_context_service.resolve_timezone(user.timezone)
    return datetime.now(tz).strftime("%Y-%m-%d")


def _learning_redis_key(user_id: UUID, day_key: str) -> str:
    return f"{LEARNING_REDIS_PREFIX}:{user_id}:{day_key}"


def _append_messages(
    messages: list[dict[str, Any]],
    tokens: list[PushToken],
    *,
    title: str,
    body: str,
    data: dict[str, Any],
) -> None:
    for token in tokens:
        messages.append(
            {
                "to": token.expo_push_token,
                "title": title,
                "body": body[:240],
                "data": data,
                "sound": "default",
            }
        )


def _suggest_programming_topic(groups) -> str | None:
    best: tuple[str, float] | None = None
    for group in groups:
        items = group.items
        total = len(items)
        if total == 0:
            continue
        mastered = sum(1 for item in items if item.status == "mastered" or item.mastered)
        learning = sum(1 for item in items if item.status == "learning")
        pending = total - mastered
        if pending == 0:
            continue
        score = pending + learning * 0.25
        if best is None or score > best[1]:
            best = (group.list_title, score)
    return best[0] if best else None


async def _tokens_for_user(session: AsyncSession, user_id: UUID) -> list[PushToken]:
    return await push_repo.list_for_user(session, user_id)


async def process_todo_reminders(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    window_end = now + timedelta(minutes=MAX_REMINDER_LEAD_MINUTES)
    overdue_cutoff = now - timedelta(hours=OVERDUE_MAX_HOURS)

    result = await session.execute(
        select(TodoItem, User)
        .join(User, User.id == TodoItem.user_id)
        .where(
            TodoItem.checked.is_(False),
            TodoItem.due_at.isnot(None),
            TodoItem.notification_sent_at.is_(None),
            User.push_notifications_enabled.is_(True),
            (
                (TodoItem.due_at <= window_end)
                | ((TodoItem.due_at < now) & (TodoItem.due_at >= overdue_cutoff))
            ),
        )
    )
    rows = list(result.all())
    if not rows:
        return []

    messages: list[dict[str, Any]] = []
    for todo, user in rows:
        if todo.due_at is None:
            continue
        lead = resolve_reminder_lead_minutes(getattr(user, "reminder_lead_minutes", None))
        if not should_notify_todo(todo.due_at, now=now, lead_minutes=lead):
            continue
        tokens = await _tokens_for_user(session, todo.user_id)
        if not tokens:
            continue
        is_overdue = todo.due_at < now
        title = "Overdue reminder" if is_overdue else "Reminder"
        _append_messages(
            messages,
            tokens,
            title=title,
            body=todo.content,
            data={
                "type": "todo_reminder",
                "screen": "todos",
                "todo_id": str(todo.id),
                "focus": "reminders",
            },
        )
        todo.notification_sent_at = now

    if messages:
        await session.commit()
    return messages


async def process_email_suggestions(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    result = await session.execute(
        select(SuggestedReminder, User)
        .join(User, User.id == SuggestedReminder.user_id)
        .where(
            SuggestedReminder.status == "pending",
            SuggestedReminder.notification_sent_at.is_(None),
            User.push_notifications_enabled.is_(True),
        )
        .order_by(SuggestedReminder.user_id, SuggestedReminder.created_at.desc())
    )
    rows = list(result.all())
    if not rows:
        return []

    by_user: dict[UUID, list[SuggestedReminder]] = {}
    users: dict[UUID, User] = {}
    for row, user in rows:
        by_user.setdefault(row.user_id, []).append(row)
        users[row.user_id] = user

    messages: list[dict[str, Any]] = []
    for user_id, reminders in by_user.items():
        tokens = await _tokens_for_user(session, user_id)
        if not tokens:
            continue
        count = len(reminders)
        if count == 1:
            body = reminders[0].title
        else:
            body = f"{count} reminders from your email — tap to review"
        _append_messages(
            messages,
            tokens,
            title="From your inbox",
            body=body,
            data={
                "type": "email_suggestion",
                "screen": "todos",
                "focus": "reminders",
            },
        )
        for reminder in reminders:
            reminder.notification_sent_at = now

    await session.commit()
    return messages


async def process_learning_nudges(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    now = now or datetime.now(UTC)
    result = await session.execute(
        select(User.id)
        .join(PushToken, PushToken.user_id == User.id)
        .where(User.push_notifications_enabled.is_(True))
        .distinct()
    )
    user_ids = [row[0] for row in result.all()]
    if not user_ids:
        return []

    messages: list[dict[str, Any]] = []
    for user_id in user_ids:
        user = await session.get(User, user_id)
        if user is None:
            continue
        if _user_local_hour(user) < settings.push_learning_hour:
            continue
        day_key = _user_day_key(user)
        redis_key = _learning_redis_key(user_id, day_key)
        if not await redis.set(redis_key, "1", nx=True, ex=86_400):
            continue

        projects = await projects_repo.list_for_user(session, user_id, include_archived=False)
        best: tuple[str, float, dict[str, Any]] | None = None

        for project in projects:
            if project.kind in ("language", "vocabulary"):
                stats = await project_items_repo.count_stats(session, project.id, user_id)
                if stats["total"] == 0:
                    continue
                if stats["due_for_review"] > 0:
                    score = float(stats["due_for_review"] + 10)
                    body = f'{stats["due_for_review"]} words ready to review in "{project.title}"'
                    payload = {
                        "type": "learning_review",
                        "screen": "project",
                        "project_id": str(project.id),
                    }
                elif stats["new_count"] > 0:
                    score = float(stats["new_count"])
                    body = f'Keep going with "{project.title}" — {stats["new_count"]} new words'
                    payload = {
                        "type": "learning_continue",
                        "screen": "project",
                        "project_id": str(project.id),
                    }
                else:
                    continue
                if best is None or score > best[1]:
                    best = (body, score, payload)

            elif project.kind == "programming":
                items = await project_items_repo.list_for_user(
                    session, user_id, project_id=project.id, limit=5000
                )
                if not items:
                    continue
                groups = group_programming_items(items)
                topic = _suggest_programming_topic(groups)
                if not topic:
                    continue
                pending = sum(
                    1 for item in items if item.status != "mastered" and not item.mastered
                )
                score = float(pending + 5)
                body = f'Continue "{project.title}" — work on {topic}'
                payload = {
                    "type": "learning_continue",
                    "screen": "project",
                    "project_id": str(project.id),
                    "topic": topic,
                }
                if best is None or score > best[1]:
                    best = (body, score, payload)

        if best is None:
            await redis.delete(redis_key)
            continue

        tokens = await _tokens_for_user(session, user_id)
        if not tokens:
            await redis.delete(redis_key)
            continue

        _append_messages(
            messages,
            tokens,
            title="Time to learn",
            body=best[0],
            data=best[2],
        )

    return messages


async def run_push_cycle(session: AsyncSession, redis: Redis, settings: Settings) -> int:
    if not settings.push_enabled:
        return 0

    todo_msgs = await process_todo_reminders(session)
    email_msgs = await process_email_suggestions(session)
    learning_msgs = await process_learning_nudges(session, redis, settings)

    all_messages = todo_msgs + email_msgs + learning_msgs
    if not all_messages:
        return 0

    if settings.mock_llm_enabled and settings.environment == "development":
        logger.debug("Skipping expo push in dev mock mode count=%s", len(all_messages))
        return len(all_messages)

    await expo_push_gateway.send_push_messages(all_messages)
    return len(all_messages)
