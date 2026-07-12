"""Build and dispatch Expo push notifications for reminders, learning, and email.

Delivery semantics (do not conflate ticket accept with receipt polling):

- **Delivered** — set when Expo accepts a push ticket (`status: ok` on send). That is
  when we mark todos/suggestions as sent and keep the daily learning nudge lock.
- **Receipt polling** — deferred (see ``RECEIPT_MIN_AGE_SECONDS``) and used only to
  prune invalid device tokens. A missing or slow receipt must never block delivery
  marking or cause a resend on the next scheduler cycle.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways import expo_push_gateway, google_calendar_gateway
from app.models.orm import (
    Project,
    PushToken,
    SuggestedReminder,
    TodoItem,
    User,
    UserCalendarConnection,
)
from app.repositories import project_items as project_items_repo
from app.repositories import projects as projects_repo
from app.repositories import push_tokens as push_repo
from app.services import calendar as calendar_service
from app.services import calendar_nudges as calendar_nudge_service
from app.services import daily_learning, learning_insights
from app.services.locale import normalize_locale_code
from app.services.reminder_timing import (
    MAX_REMINDER_LEAD_MINUTES,
    OVERDUE_MAX_HOURS,
    learning_dedupe_key,
    resolve_reminder_lead_minutes,
    should_notify_todo,
    user_day_key,
    user_local_hour,
)

logger = logging.getLogger(__name__)

LEARNING_REDIS_PREFIX = "recall:push:learning"
RECEIPT_PENDING_ZSET = "recall:push:receipts:pending"
RECEIPT_MIN_AGE_SECONDS = 15 * 60
RECEIPT_MAX_AGE_SECONDS = 24 * 60 * 60


@dataclass
class OutboundPush:
    message: dict[str, Any]
    todos: list[TodoItem] = field(default_factory=list)
    suggestions: list[SuggestedReminder] = field(default_factory=list)
    learning_redis_key: str | None = None
    dedupe_redis_key: str | None = None


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


def _receipt_token_key(ticket_id: str) -> str:
    return f"recall:push:receipt:token:{ticket_id}"


def _redis_str_members(raw: list[object]) -> list[str]:
    ids: list[str] = []
    for item in raw:
        if isinstance(item, bytes):
            ids.append(item.decode())
        elif isinstance(item, str):
            ids.append(item)
    return ids


async def enqueue_push_receipts(redis: Redis, tickets: list[tuple[str, str]]) -> None:
    """Queue Expo ticket ids for deferred receipt polling (token pruning only)."""
    if not tickets:
        return
    now = time.time()
    pipe = redis.pipeline()
    for ticket_id, token in tickets:
        pipe.set(_receipt_token_key(ticket_id), token, ex=RECEIPT_MAX_AGE_SECONDS)
        pipe.zadd(RECEIPT_PENDING_ZSET, {ticket_id: now})
    await pipe.execute()


async def poll_deferred_push_receipts(session: AsyncSession, redis: Redis) -> None:
    """Poll Expo receipts old enough to be ready; prune dead tokens."""
    now = time.time()
    stale_before = now - RECEIPT_MAX_AGE_SECONDS
    stale_raw = await redis.zrangebyscore(RECEIPT_PENDING_ZSET, 0, stale_before)
    stale_ids = _redis_str_members(list(stale_raw))
    if stale_ids:
        await redis.zrem(RECEIPT_PENDING_ZSET, *stale_ids)
        for ticket_id in stale_ids:
            await redis.delete(_receipt_token_key(ticket_id))

    ready_before = now - RECEIPT_MIN_AGE_SECONDS
    ticket_ids = _redis_str_members(
        list(await redis.zrangebyscore(RECEIPT_PENDING_ZSET, 0, ready_before))
    )
    if not ticket_ids:
        return

    receipt_map = await expo_push_gateway.fetch_push_receipts(ticket_ids)
    pruned = False
    for ticket_id in ticket_ids:
        receipt = receipt_map.get(ticket_id)
        if not receipt:
            continue
        status = receipt.get("status")
        if status in (None, "pending"):
            continue

        await redis.zrem(RECEIPT_PENDING_ZSET, ticket_id)
        token_raw = await redis.get(_receipt_token_key(ticket_id))
        await redis.delete(_receipt_token_key(ticket_id))
        token = token_raw.decode() if isinstance(token_raw, bytes) else token_raw
        if (
            status == "error"
            and token
            and expo_push_gateway.receipt_indicates_invalid_token(receipt)
        ):
            try:
                await push_repo.delete_by_token(session, token)
                pruned = True
                logger.info("Pruned invalid push token from receipt ticket=%s", ticket_id[:12])
            except Exception:
                logger.debug("Failed to prune push token from receipt", exc_info=True)

    if pruned:
        await session.commit()


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
    dedupe_redis_key: str | None = None,
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
                dedupe_redis_key=dedupe_redis_key,
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
        # BUG FIX (was cycle-fatal): an unhandled exception for one todo/user
        # used to propagate out of the loop and drop every other user's
        # reminders for this cycle. Isolate and skip just this row.
        try:
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
        except Exception:
            logger.exception("Todo reminder failed user_id=%s todo_id=%s", todo.user_id, todo.id)
            continue

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
        # BUG FIX (was cycle-fatal): isolate per-user failures so one bad
        # reminder batch doesn't drop every other user's email suggestions.
        try:
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
        except Exception:
            logger.exception("Email suggestion push failed user_id=%s", user_id)
            continue

    return messages


async def process_learning_nudges(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> list[OutboundPush]:
    """Batched: one query each for users/projects/item-stats/tokens instead
    of one query per user (and one more per project inside that) — this loop
    runs every minute across every opted-in user, so N+1 here scales badly."""
    now = now or datetime.now(UTC)
    result = await session.execute(
        select(User)
        .join(PushToken, PushToken.user_id == User.id)
        .where(User.push_notifications_enabled.is_(True))
        .distinct()
    )
    users = list(result.scalars().all())
    if not users:
        return []

    # Filter to users due for a nudge (and claim today's Redis lock for them)
    # before doing any further batched fetch, so we don't pull projects/
    # tokens for users we're not going to message this cycle.
    candidates: list[tuple[User, str]] = []
    for user in users:
        if user_local_hour(user) < settings.push_learning_hour:
            continue
        day_key = user_day_key(user)
        redis_key = learning_dedupe_key(LEARNING_REDIS_PREFIX, user.id, day_key)
        if not await redis.set(redis_key, "1", nx=True, ex=86_400):
            continue
        candidates.append((user, redis_key))

    if not candidates:
        return []

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
        # BUG FIX (was cycle-fatal): isolate per-project stat enrichment so
        # one project's malformed data (e.g. daily_goal_history) doesn't
        # blow up nudge computation for every other project/user this cycle.
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

    tokens = await push_repo.list_for_users(session, user_ids)
    tokens_by_user: dict[UUID, list[PushToken]] = {}
    for token in tokens:
        tokens_by_user.setdefault(token.user_id, []).append(token)

    messages: list[OutboundPush] = []
    for user, redis_key in candidates:
        # BUG FIX (was cycle-fatal): isolate per-user nudge picking so a bad
        # record for one user doesn't drop learning nudges for every user.
        try:
            user_projects = projects_by_user.get(user.id, [])
            best_pick = learning_insights.best_learning_nudge_for_user(
                user_projects,
                stats_by_project,
                daily_goal_for=daily_learning.resolve_daily_goal,
            )
            if best_pick is None:
                await redis.delete(redis_key)
                continue

            _project, body, _score, _nudge_type, payload = best_pick
            user_tokens = tokens_by_user.get(user.id, [])
            if not user_tokens:
                await redis.delete(redis_key)
                continue

            strings = _push_strings(getattr(user, "locale", None))
            _append_outbound(
                messages,
                user_tokens,
                title=strings["time_to_learn"],
                body=body,
                data=payload,
                learning_redis_key=redis_key,
            )
        except Exception:
            logger.exception("Learning nudge failed user_id=%s", user.id)
            continue

    return messages


async def process_calendar_nudges(
    session: AsyncSession,
    redis: Redis,
    settings: Settings,
    *,
    now: datetime | None = None,
) -> list[OutboundPush]:
    if not settings.calendar_nudge_enabled or not settings.google_calendar_enabled:
        return []
    if not google_calendar_gateway.is_configured(settings):
        return []

    now = now or datetime.now(UTC)
    lead = max(1, settings.calendar_nudge_lead_minutes)

    result = await session.execute(
        select(User)
        .join(UserCalendarConnection, UserCalendarConnection.user_id == User.id)
        .join(PushToken, PushToken.user_id == User.id)
        .where(User.push_notifications_enabled.is_(True))
        .distinct()
    )
    users = list(result.scalars().all())
    if not users:
        return []

    messages: list[OutboundPush] = []
    for user in users:
        # BUG FIX (was cycle-fatal): isolate per-user failures so one user's
        # bad calendar data doesn't drop nudges for every other user.
        try:
            events = await calendar_service.fetch_upcoming_events(session, redis, user, settings)
            due = calendar_nudge_service.events_needing_nudge(events, now=now, lead_minutes=lead)
            if not due:
                continue
            tokens = await _tokens_for_user(session, user.id)
            if not tokens:
                continue

            for event in due:
                dedupe_key = calendar_nudge_service.calendar_nudge_redis_key(user.id, event.id)
                ttl = calendar_nudge_service.nudge_ttl_seconds(event, now=now)
                claimed = await redis.set(dedupe_key, "1", nx=True, ex=ttl)
                if not claimed:
                    continue
                title, body = calendar_nudge_service.format_calendar_nudge(
                    event,
                    now=now,
                    locale=getattr(user, "locale", None),
                )
                _append_outbound(
                    messages,
                    tokens,
                    title=title,
                    body=body,
                    data={
                        "type": "calendar_nudge",
                        "screen": "todos",
                        "focus": "reminders",
                        "event_id": event.id,
                        "event_title": event.title,
                    },
                    dedupe_redis_key=dedupe_key,
                )
        except Exception:
            logger.exception("Calendar nudge failed user_id=%s", user.id)
            continue

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
    dedupe_failures: list[str] = []

    for item, ok in zip(outbound, delivered, strict=False):
        if item.learning_redis_key is not None:
            key = item.learning_redis_key
            learning_success[key] = learning_success.get(key, False) or ok
        if item.dedupe_redis_key is not None and not ok:
            dedupe_failures.append(item.dedupe_redis_key)
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

    for key in dedupe_failures:
        await redis.delete(key)

    if todos_marked or suggestions_marked:
        await session.commit()


async def run_push_cycle(session: AsyncSession, redis: Redis, settings: Settings) -> int:
    if not settings.push_enabled:
        return 0

    await poll_deferred_push_receipts(session, redis)

    now = datetime.now(UTC)

    # Local (expo-notifications) reminders handle todo due-at alerts; server
    # todo push is disabled by default to avoid double notifications.
    # Re-enable via server_todo_push_enabled=true (e.g. for web-only clients).
    todo_msgs: list[OutboundPush] = []
    if settings.server_todo_push_enabled:
        todo_msgs = await process_todo_reminders(session, now=now)
    email_msgs = await process_email_suggestions(session, now=now)
    learning_msgs = await process_learning_nudges(session, redis, settings, now=now)
    calendar_msgs = await process_calendar_nudges(session, redis, settings, now=now)

    outbound = todo_msgs + email_msgs + learning_msgs + calendar_msgs
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
        if result.receipt_tickets:
            await enqueue_push_receipts(redis, result.receipt_tickets)

    await _finalize_push_deliveries(session, redis, outbound, delivered, now=now)
    return len(outbound)
