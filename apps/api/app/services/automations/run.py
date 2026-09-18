"""Headless execution of one Automation run through the chat turn engine.

Same turn engine WS/SSE use (`stream_chat_response`) — no transport, no
client. `is_automation=True` restricts the tool loop to `web_search` only
(enforced in `services/tool_loop.py`); this module owns the
gating/scheduling/notification wrapper around that one turn.

Called from the `automation_run` job handler (`background/handlers.py`),
one automation per invocation. The periodic scheduler
(`background/automations_scheduler.py`) only enqueues; this module owns
every schedule mutation (`next_run_at` / `status` / `last_run_*`) so a
skipped or failed run still advances past today's occurrence instead of
being re-picked forever.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis

from app.core.config import Settings
from app.core.db import SessionLocal
from app.exceptions import ChatServiceError, QuotaExceededError
from app.gateways.litellm_gateway import ModelUnavailableError
from app.models.orm import Automation, User
from app.repositories import automations as automations_repo
from app.repositories import users as users_repo
from app.services import plan as plan_service
from app.services.chat.stream import stream_chat_response
from app.services.chat.stream_events import (
    await_finalize_commit,
    persist_finalize_if_pending,
    pop_finalize_tasks,
)
from app.services.notifications import push as push_notifications
from app.services.todos.recurrence import is_recurrence_rule, next_recurring_due

logger = logging.getLogger(__name__)

# Outlives one calendar day (with slack for clock skew) — one counter per
# automation per UTC day, used only for the automations_daily_run_cap guard.
_DAILY_RUN_COUNT_TTL_SECONDS = 26 * 60 * 60
_AUTOMATION_MODEL_ALIAS = "smart-chat"


def _daily_run_count_key(automation_id: UUID, now: datetime) -> str:
    return f"recall:automations:runs:{automation_id}:{now.date().isoformat()}"


async def _daily_run_count(redis: Redis, automation_id: UUID, *, now: datetime) -> int:
    raw = await redis.get(_daily_run_count_key(automation_id, now))
    try:
        return int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        return 0


async def _bump_daily_run_count(redis: Redis, automation_id: UUID, *, now: datetime) -> None:
    key = _daily_run_count_key(automation_id, now)
    await redis.incr(key)
    await redis.expire(key, _DAILY_RUN_COUNT_TTL_SECONDS)


def _advance_or_complete(
    automation: Automation, user: User, *, now: datetime
) -> tuple[datetime, str]:
    """Return the `(next_run_at, status)` this occurrence advances to.

    Applied unconditionally after every run attempt (ok, skipped, or error)
    — otherwise a skipped occurrence would sit at the same `next_run_at`
    forever: the job's own dedupe key (`automation_id:next_run_at`) marks
    itself done after this attempt, so an unadvanced row would never be
    retried, but it also would never reach its *next* legitimate occurrence.
    """
    if automation.frequency == "once":
        return automation.next_run_at, "completed"
    if is_recurrence_rule(automation.frequency):
        nxt = next_recurring_due(
            automation.next_run_at, automation.frequency, now=now, timezone=user.timezone
        )
        return nxt, "active"
    logger.warning(
        "automation_run: unknown frequency=%r id=%s; marking completed",
        automation.frequency,
        automation.id,
    )
    return automation.next_run_at, "completed"


async def run_automation(settings: Settings, redis: Redis, *, automation_id: UUID) -> None:
    """Re-check gating, run one headless chat turn, advance schedule, notify.

    Every gating miss records `last_run_status` and returns without raising
    — quota/plan/pause misses are expected, not job failures, and retrying
    them would not help (same-day quota, or the user explicitly paused it).
    """
    now = datetime.now(UTC)

    async with SessionLocal() as session:
        automation = await session.get(Automation, automation_id)
        if automation is None:
            logger.info("automation_run: gone id=%s", automation_id)
            return
        # Re-check status/plan at run time, not just at enqueue time — the
        # user may have paused/deleted the automation or downgraded plan
        # in the window between the scheduler tick and this job running.
        if automation.status != "active":
            logger.info(
                "automation_run: no longer active id=%s status=%s",
                automation_id,
                automation.status,
            )
            return
        user = await users_repo.get_by_id(session, automation.user_id)
        if user is None:
            logger.info("automation_run: user gone id=%s", automation_id)
            return
        if not plan_service.is_pro(user):
            await automations_repo.update(
                session,
                automation,
                status="paused",
                last_run_at=now,
                last_run_status="error",
            )
            return

        daily_cap = settings.automations_daily_run_cap
        if daily_cap > 0 and await _daily_run_count(redis, automation.id, now=now) >= daily_cap:
            next_at, status = _advance_or_complete(automation, user, now=now)
            await automations_repo.update(
                session,
                automation,
                next_run_at=next_at,
                status=status,
                last_run_at=now,
                last_run_status="skipped_quota",
            )
            return

        chat_id = automation.chat_id
        user_id = user.id
        prompt = automation.prompt

    # Run the headless turn outside that short-lived session — the LLM
    # round trip (and its own turn-prep DB reads) must not hold this Neon
    # checkout open for the duration of generation.
    run_status = "ok"
    result: dict[str, str] = {}
    try:
        async for _token in stream_chat_response(
            redis,
            settings,
            user_id=user_id,
            chat_id=chat_id,
            content=prompt,
            model_alias=_AUTOMATION_MODEL_ALIAS,
            is_automation=True,
            result=result,
        ):
            pass
        finalize_db_task = pop_finalize_tasks(result)
        commit_status = await await_finalize_commit(finalize_db_task)
        if commit_status == "failed":
            run_status = "error"
    except QuotaExceededError:
        run_status = "skipped_quota"
    except (ChatServiceError, ModelUnavailableError):
        logger.warning("automation_run: turn rejected id=%s", automation_id)
        run_status = "error"
    except Exception:
        logger.exception("automation_run: turn failed id=%s", automation_id)
        run_status = "error"
    finally:
        # A raised exception above must not orphan a still-pending DB
        # commit — same invariant WS/SSE keep in their `finally` blocks.
        await persist_finalize_if_pending(result)

    await _bump_daily_run_count(redis, automation_id, now=now)

    automation_snapshot: Automation | None = None
    async with SessionLocal() as session:
        automation = await session.get(Automation, automation_id)
        if automation is not None:
            user = await users_repo.get_by_id(session, automation.user_id)
            if user is not None:
                next_at, status = _advance_or_complete(automation, user, now=now)
                automation_snapshot = await automations_repo.update(
                    session,
                    automation,
                    next_run_at=next_at,
                    status=status,
                    last_run_at=now,
                    last_run_status=run_status,
                )

    if run_status == "ok" and automation_snapshot is not None:
        async with SessionLocal() as session:
            await push_notifications.notify_automation_run(
                session, redis, settings, automation_snapshot
            )
