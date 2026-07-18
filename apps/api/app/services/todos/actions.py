"""Apply LLM-extracted or explicit todo/reminder mutations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import TodoItem
from app.models.schemas import TodoActionItem
from app.repositories import todos as todos_repo
from app.services import home as home_service
from app.services import time_context as time_context_service
from app.services.action_dispatch import ActionHandler, apply_action_batch
from app.services.todos.prompt_context import _due_local, _normalize, _topic_key

logger = logging.getLogger(__name__)

_ACTION_RELOAD_LIMIT = 500

# Defensive caps for LLM-inferred mutations applied from a chat transcript.
# The model extracts actions from arbitrary user text; these limits prevent a
# misparse from wiping large amounts of data in one turn.
MAX_TODO_ACTIONS_PER_TURN = 12
# Actions blocked from the post-reply background job only (assistant text must not
# trigger whole-list deletes). Pre-turn sync may apply delete_list when the user asks.
TODO_BLOCKED_FROM_TRANSCRIPT = frozenset({"delete_list"})

REMINDER_TOPIC = "Reminders"


def _fuzzy_match(needle: str, haystack: str) -> bool:
    if needle == haystack:
        return True
    if len(needle) < 6 or len(haystack) < 6:
        return False
    return SequenceMatcher(None, needle, haystack).ratio() >= 0.92


def _find_item(items: list[TodoItem], topic: str, content: str) -> TodoItem | None:
    needle = _normalize(content)
    topic_norm = _topic_key(topic)
    candidates = [i for i in items if _topic_key(i.topic) == topic_norm and not i.checked]
    for item in candidates:
        if _normalize(item.content) == needle:
            return item
    for item in candidates:
        if _fuzzy_match(needle, _normalize(item.content)):
            return item
    return None


def _find_item_any_state(items: list[TodoItem], topic: str, content: str) -> TodoItem | None:
    needle = _normalize(content)
    topic_norm = _topic_key(topic)
    candidates = [i for i in items if _topic_key(i.topic) == topic_norm]
    for item in candidates:
        if _normalize(item.content) == needle:
            return item
    for item in candidates:
        if _fuzzy_match(needle, _normalize(item.content)):
            return item
    return None


def _due_local_date(item: TodoItem, user_timezone: str | None):
    tz = time_context_service.resolve_timezone(user_timezone)
    due = item.due_at
    if due is None:
        return None
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    return due.astimezone(tz).date()


def _shift_due_date_preserving_time(
    item: TodoItem,
    *,
    user_timezone: str | None,
    target_date,
) -> datetime:
    tz = time_context_service.resolve_timezone(user_timezone)
    due = item.due_at
    assert due is not None
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    due_local = due.astimezone(tz)
    shifted_local = due_local.replace(
        year=target_date.year,
        month=target_date.month,
        day=target_date.day,
    )
    return shifted_local.astimezone(UTC)


async def _apply_bulk_shift_due_today_to_tomorrow(
    session: AsyncSession,
    *,
    user_id: UUID,
    items: list[TodoItem],
    user_timezone: str | None,
) -> int:
    tz = time_context_service.resolve_timezone(user_timezone)
    today = datetime.now(tz).date()
    tomorrow = today + timedelta(days=1)
    applied = 0
    for item in items:
        if item.checked or item.due_at is None:
            continue
        if _due_local_date(item, user_timezone) != today:
            continue
        due_at = _shift_due_date_preserving_time(
            item,
            user_timezone=user_timezone,
            target_date=tomorrow,
        )
        await todos_repo.update(session, item, due_at=due_at)
        applied += 1
    return applied


async def _apply_delete_overdue_open_reminders(
    session: AsyncSession,
    *,
    user_id: UUID,
    items: list[TodoItem],
    user_timezone: str | None,
) -> int:
    """Delete open dated reminders whose due time is already past (local).

    Not wired into transcript sync — that path must use capped per-item
    ``delete`` actions only (unbounded regex wipe was too risky).
    """
    tz = time_context_service.resolve_timezone(user_timezone)
    now = datetime.now(tz)
    applied = 0
    for item in items:
        if item.checked or item.due_at is None:
            continue
        due_local = _due_local(item.due_at, user_timezone)
        if due_local >= now:
            continue
        await todos_repo.delete_by_id(session, item.id, user_id)
        applied += 1
    return applied


@dataclass
class _TodoApplyState:
    session: AsyncSession
    user_id: UUID
    chat_id: UUID | None
    user_timezone: str | None
    feedback: list[str] | None
    items: list[TodoItem]


def _prepare_todo_action(action: TodoActionItem) -> TodoActionItem | None:
    topic = action.topic.strip()
    if not topic:
        # Dated reminders don't need a list title — land in Reminders via due_at.
        if action.action == "add" and action.due_at is not None:
            return action.model_copy(update={"topic": REMINDER_TOPIC})
        return None
    if topic != action.topic:
        return action.model_copy(update={"topic": topic})
    return action


async def _todo_action_add(state: _TodoApplyState, action: TodoActionItem) -> int:
    content = action.content.strip()
    if not content:
        return 0
    topic = action.topic
    if _find_item_any_state(state.items, topic, content):
        return 0
    due_at = time_context_service.normalize_due_at(action.due_at, state.user_timezone)
    await todos_repo.create(
        state.session,
        user_id=state.user_id,
        content=content,
        topic=topic,
        chat_id=state.chat_id,
        due_at=due_at,
    )
    state.items = await todos_repo.list_for_user(
        state.session, state.user_id, limit=_ACTION_RELOAD_LIMIT
    )
    return 1


async def _todo_action_complete(state: _TodoApplyState, action: TodoActionItem) -> int:
    item = _find_item(state.items, action.topic, action.content)
    if item and not item.checked:
        await todos_repo.update(state.session, item, checked=True)
        return 1
    return 0


async def _todo_action_uncheck(state: _TodoApplyState, action: TodoActionItem) -> int:
    item = _find_item_any_state(state.items, action.topic, action.content)
    if item and item.checked:
        await todos_repo.update(state.session, item, checked=False)
        return 1
    return 0


async def _todo_action_delete(state: _TodoApplyState, action: TodoActionItem) -> int:
    item = _find_item_any_state(state.items, action.topic, action.content)
    if item:
        await todos_repo.delete_by_id(state.session, item.id, state.user_id)
        state.items = [i for i in state.items if i.id != item.id]
        return 1
    logger.warning(
        "Todo delete missed: user_id=%s topic=%s content=%r",
        state.user_id,
        action.topic,
        (action.content or "")[:120],
    )
    return 0


async def _todo_action_delete_list(state: _TodoApplyState, action: TodoActionItem) -> int:
    topic = action.topic
    list_items = [
        i for i in state.items if _topic_key(i.topic) == _topic_key(topic) and i.due_at is None
    ]
    open_count = sum(1 for i in list_items if not i.checked)
    if open_count > 0:
        if state.feedback is not None:
            state.feedback.append(
                f'Blocked delete list "{topic}": {open_count} item(s) still open.'
            )
        return 0
    removed = await todos_repo.delete_by_topic(state.session, state.user_id, topic)
    if removed:
        if state.feedback is not None:
            state.feedback.append(f'Deleted list "{topic}" ({removed} item(s)).')
        state.items = [i for i in state.items if _topic_key(i.topic) != _topic_key(topic)]
        return 1
    if state.feedback is not None:
        state.feedback.append(f'List "{topic}" not found or already empty.')
    return 0


async def _todo_action_set_due(state: _TodoApplyState, action: TodoActionItem) -> int:
    due_at = time_context_service.normalize_due_at(action.due_at, state.user_timezone)
    if action.content.strip() == "*":
        tz = time_context_service.resolve_timezone(state.user_timezone)
        today = datetime.now(tz).date()
        applied = 0
        for open_item in state.items:
            if open_item.checked or open_item.due_at is None:
                continue
            if _due_local_date(open_item, state.user_timezone) != today:
                continue
            await todos_repo.update(state.session, open_item, due_at=due_at)
            applied += 1
        return applied
    item = _find_item_any_state(state.items, action.topic, action.content)
    if item:
        await todos_repo.update(state.session, item, due_at=due_at)
        return 1
    return 0


async def _todo_action_clear_due(state: _TodoApplyState, action: TodoActionItem) -> int:
    item = _find_item_any_state(state.items, action.topic, action.content)
    if item and item.due_at is not None:
        await todos_repo.update(state.session, item, due_at=None)
        return 1
    return 0


_TODO_ACTION_HANDLERS: dict[str, ActionHandler[_TodoApplyState, TodoActionItem]] = {
    "add": _todo_action_add,
    "complete": _todo_action_complete,
    "uncheck": _todo_action_uncheck,
    "delete": _todo_action_delete,
    "delete_list": _todo_action_delete_list,
    "set_due": _todo_action_set_due,
    "clear_due": _todo_action_clear_due,
}


async def apply_todo_actions(
    session: AsyncSession,
    *,
    user_id: UUID,
    actions: list[TodoActionItem],
    chat_id: UUID | None = None,
    user_timezone: str | None = None,
    feedback: list[str] | None = None,
) -> int:
    if not actions:
        return 0
    items = await todos_repo.list_for_user(session, user_id, limit=_ACTION_RELOAD_LIMIT)
    state = _TodoApplyState(
        session=session,
        user_id=user_id,
        chat_id=chat_id,
        user_timezone=user_timezone,
        feedback=feedback,
        items=items,
    )

    def _on_error(action: TodoActionItem) -> None:
        logger.exception(
            "Failed todo action %s for user_id=%s topic=%s",
            action.action,
            user_id,
            action.topic,
        )

    def _log_summary(applied: int) -> None:
        logger.info(
            "Applied %d todo action(s) for user_id=%s chat_id=%s",
            applied,
            user_id,
            chat_id,
        )

    return await apply_action_batch(
        actions=actions,
        state=state,
        handlers=_TODO_ACTION_HANDLERS,
        action_name=lambda a: a.action,
        prepare=_prepare_todo_action,
        on_error=_on_error,
        log_summary=_log_summary,
        invalidate_home=lambda: home_service.invalidate_home_cache(user_id),
    )
