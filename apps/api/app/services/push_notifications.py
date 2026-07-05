"""Build and dispatch Expo push notifications for reminders, learning, and email."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
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
from app.services.locale import normalize_locale_code
from app.services.reminder_timing import (
    MAX_REMINDER_LEAD_MINUTES,
    OVERDUE_MAX_HOURS,
    resolve_reminder_lead_minutes,
    should_notify_todo,
)

logger = logging.getLogger(__name__)

LEARNING_REDIS_PREFIX = "recall:push:learning"


@dataclass
class OutboundPush:
    message: dict[str, Any]
    todos: list[TodoItem] = field(default_factory=list)
    suggestions: list[SuggestedReminder] = field(default_factory=list)
    learning_redis_key: str | None = None


_PUSH_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "reminder": "Reminder",
        "overdue": "Overdue reminder",
        "from_inbox": "From your inbox",
        "time_to_learn": "Time to learn",
        "email_plural": "{count} reminders from your email — tap to review",
    },
    "es": {
        "reminder": "Recordatorio",
        "overdue": "Recordatorio atrasado",
        "from_inbox": "Desde tu bandeja",
        "time_to_learn": "Hora de aprender",
        "email_plural": "{count} recordatorios de tu correo — toca para revisar",
    },
    "fr": {
        "reminder": "Rappel",
        "overdue": "Rappel en retard",
        "from_inbox": "Depuis votre boîte",
        "time_to_learn": "Temps d'apprendre",
        "email_plural": "{count} rappels de votre courriel — appuyez pour voir",
    },
    "de": {
        "reminder": "Erinnerung",
        "overdue": "Überfällige Erinnerung",
        "from_inbox": "Aus deinem Postfach",
        "time_to_learn": "Zeit zum Lernen",
        "email_plural": "{count} Erinnerungen aus deiner E-Mail — tippen zum Ansehen",
    },
    "it": {
        "reminder": "Promemoria",
        "overdue": "Promemoria in ritardo",
        "from_inbox": "Dalla tua casella",
        "time_to_learn": "Ora di imparare",
        "email_plural": "{count} promemoria dalla tua email — tocca per vedere",
    },
    "pt": {
        "reminder": "Lembrete",
        "overdue": "Lembrete atrasado",
        "from_inbox": "Da sua caixa de entrada",
        "time_to_learn": "Hora de aprender",
        "email_plural": "{count} lembretes do seu e-mail — toque para ver",
    },
    "ru": {
        "reminder": "Напоминание",
        "overdue": "Просроченное напоминание",
        "from_inbox": "Из вашего ящика",
        "time_to_learn": "Время учиться",
        "email_plural": "{count} напоминаний из почты — нажмите для просмотра",
    },
    "tr": {
        "reminder": "Hatırlatma",
        "overdue": "Gecikmiş hatırlatma",
        "from_inbox": "Gelen kutunuzdan",
        "time_to_learn": "Öğrenme zamanı",
        "email_plural": "E-postanızdan {count} hatırlatma — görmek için dokunun",
    },
}


def _push_strings(locale: str | None) -> dict[str, str]:
    code = normalize_locale_code(locale)
    return _PUSH_STRINGS.get(code, _PUSH_STRINGS["en"])


def _user_local_hour(user: User) -> int:
    tz = time_context_service.resolve_timezone(user.timezone)
    return datetime.now(tz).hour


def _user_day_key(user: User) -> str:
    tz = time_context_service.resolve_timezone(user.timezone)
    return datetime.now(tz).strftime("%Y-%m-%d")


def _learning_redis_key(user_id: UUID, day_key: str) -> str:
    return f"{LEARNING_REDIS_PREFIX}:{user_id}:{day_key}"


def _append_outbound(
    out: list[OutboundPush],
    tokens: list[PushToken],
    *,
    title: str,
    body: str,
    data: dict[str, Any],
    todos: list[TodoItem] | None = None,
    suggestions: list[SuggestedReminder] | None = None,
    learning_redis_key: str | None = None,
) -> None:
    seen_tokens: set[str] = set()
    for token in tokens:
        if token.expo_push_token in seen_tokens:
            continue
        seen_tokens.add(token.expo_push_token)
        out.append(
            OutboundPush(
                message={
                    "to": token.expo_push_token,
                    "title": title,
                    "body": body[:240],
                    "data": data,
                    "sound": "default",
                },
                todos=list(todos or []),
                suggestions=list(suggestions or []),
                learning_redis_key=learning_redis_key,
            )
        )


async def _tokens_for_user(session: AsyncSession, user_id: UUID) -> list[PushToken]:
    return await push_repo.list_for_user(session, user_id)


async def process_todo_reminders(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> list[OutboundPush]:
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

    messages: list[OutboundPush] = []
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
        strings = _push_strings(getattr(user, "locale", None))
        title = strings["overdue"] if is_overdue else strings["reminder"]
        _append_outbound(
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
            todos=[todo],
        )

    return messages


async def process_email_suggestions(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> list[OutboundPush]:
    _ = now
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

    messages: list[OutboundPush] = []
    for user_id, reminders in by_user.items():
        tokens = await _tokens_for_user(session, user_id)
        if not tokens:
            continue
        count = len(reminders)
        strings = _push_strings(getattr(users[user_id], "locale", None))
        if count == 1:
            body = reminders[0].title
        else:
            body = strings["email_plural"].format(count=count)
        _append_outbound(
            messages,
            tokens,
            title=strings["from_inbox"],
            body=body,
            data={
                "type": "email_suggestion",
                "screen": "todos",
                "focus": "reminders",
            },
            suggestions=reminders,
        )

    return messages


async def process_learning_nudges(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> list[OutboundPush]:
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

    messages: list[OutboundPush] = []
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

        if best is None:
            await redis.delete(redis_key)
            continue

        tokens = await _tokens_for_user(session, user_id)
        if not tokens:
            await redis.delete(redis_key)
            continue

        strings = _push_strings(getattr(user, "locale", None))
        _append_outbound(
            messages,
            tokens,
            title=strings["time_to_learn"],
            body=best[0],
            data=best[2],
            learning_redis_key=redis_key,
        )

    return messages


async def _finalize_push_deliveries(
    session: AsyncSession,
    redis: Redis,
    outbound: list[OutboundPush],
    delivered: list[bool],
    *,
    now: datetime,
) -> None:
    todos_marked: set[int] = set()
    suggestions_marked: set[int] = set()
    learning_success: dict[str, bool] = {}

    for item, ok in zip(outbound, delivered, strict=False):
        if item.learning_redis_key is not None:
            key = item.learning_redis_key
            learning_success[key] = learning_success.get(key, False) or ok
        if not ok:
            continue
        for todo in item.todos:
            todo_id = id(todo)
            if todo_id in todos_marked:
                continue
            todo.notification_sent_at = now
            todos_marked.add(todo_id)
        for suggestion in item.suggestions:
            suggestion_id = id(suggestion)
            if suggestion_id in suggestions_marked:
                continue
            suggestion.notification_sent_at = now
            suggestions_marked.add(suggestion_id)

    for key, had_success in learning_success.items():
        if not had_success:
            await redis.delete(key)

    if todos_marked or suggestions_marked:
        await session.commit()


async def run_push_cycle(session: AsyncSession, redis: Redis, settings: Settings) -> int:
    if not settings.push_enabled:
        return 0

    now = datetime.now(UTC)

    # Local (expo-notifications) reminders handle todo due-at alerts; server
    # todo push is disabled by default to avoid double notifications.
    # Re-enable via server_todo_push_enabled=true (e.g. for web-only clients).
    todo_msgs: list[OutboundPush] = []
    if settings.server_todo_push_enabled:
        todo_msgs = await process_todo_reminders(session, now=now)
    email_msgs = await process_email_suggestions(session, now=now)
    learning_msgs = await process_learning_nudges(session, redis, settings, now=now)

    outbound = todo_msgs + email_msgs + learning_msgs
    if not outbound:
        return 0

    if settings.mock_llm_enabled and settings.environment == "development":
        logger.debug("Skipping expo push in dev mock mode count=%s", len(outbound))
        delivered = [True] * len(outbound)
    else:
        result = await expo_push_gateway.send_push_messages(
            [item.message for item in outbound],
        )
        delivered = result.delivered
        if len(delivered) != len(outbound):
            delivered = [False] * len(outbound)
        if result.invalid_tokens:
            for token in result.invalid_tokens:
                try:
                    await push_repo.delete_by_token(session, token)
                    logger.info("Pruned invalid push token=%s", token[:20])
                except Exception:
                    logger.debug("Failed to prune push token", exc_info=True)

    await _finalize_push_deliveries(session, redis, outbound, delivered, now=now)
    return len(outbound)
