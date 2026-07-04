import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import Message, TodoItem, User
from app.models.schemas import TodoActionItem, TodoExtractionResult
from app.repositories import todos as todos_repo
from app.repositories import users as users_repo
from app.repositories.todos import DEFAULT_TOPIC
from app.services import day_planning as day_planning_service
from app.services import home as home_service
from app.services import time_context as time_context_service

logger = logging.getLogger(__name__)

# Defensive caps for LLM-inferred mutations applied from a chat transcript.
# The model extracts actions from arbitrary user text; these limits prevent a
# misparse from wiping large amounts of data in one turn.
MAX_TODO_ACTIONS_PER_TURN = 3
# Actions blocked from the post-reply background job only (assistant text must not
# trigger whole-list deletes). Pre-turn sync may apply delete_list when the user asks.
TODO_BLOCKED_FROM_TRANSCRIPT = frozenset({"delete_list"})

TODO_SYNC_FEEDBACK_HEADER = (
    "Todo sync results (already applied before this reply — describe accurately):\n"
)

TODO_HINT = (
    "Recall has two todo features — do not confuse them:\n"
    "1) **Reminders** — items WITH a due date/time in the app's Reminders calendar.\n"
    "2) **Lists** — checklist items WITHOUT a due date (shopping lists, etc.).\n\n"
    "When they ask about their calendar, meetings, or external schedule → use **Google Calendar** "
    "if that block is present below. "
    "When they ask what's due, reminders, or in-app schedule → use **Reminders** below. "
    "If Google Calendar is not connected and they ask to check their calendar, tell them to "
    "connect it in Settings → Google Calendar.\n"
    "Reply directly with the schedule — use the same day headings (Today, Tomorrow, etc.) "
    "for Reminders. No apologies or explaining how the app works unless they ask.\n"
    "When they ask about lists, groceries, or checklist items → use the **Lists** section.\n\n"
    "Status questions — short prose; mention ✓ done vs ○ open. Do not paste huge checkbox dumps "
    "unless they ask for the full list.\n"
    "Proactively nudge overdue or due-soon open reminders only when the conversation is "
    "about tasks, planning, or productivity — not in general or identity questions.\n"
    "When a reminder appears under ### Today, say it is due today — never call it tomorrow.\n"
    "Creating lists via chat — ask for a list title first, then items; changes apply before your reply.\n"
    "Deleting lists via chat — whole-list delete runs before your reply when the user clearly asks. "
    "It only succeeds when every item in that list is checked off or removed; otherwise sync results "
    "below will say Blocked — explain that and never claim a list was deleted unless sync confirms it.\n"
    "Deleting items via chat — complete, uncheck, or delete individual items; same pre-reply sync.\n"
    "Deleting in the app (Lists tab) — trash on a row removes one item. To delete a whole list, "
    "check off or delete every item first; then a trash icon appears on the list header. "
    "Never invent swipe gestures or other UI.\n"
    "Due dates via chat — add/set_due/clear_due; bulk moves (e.g. all due today → tomorrow) sync "
    "automatically. Parse relative dates using the user's local time in the prompt.\n"
    "Do not invent list titles or due dates."
)


_BULK_SHIFT_TO_TOMORROW = re.compile(
    r"("
    r"\b(move|shift|reschedule|push)\b.{0,40}\b(all|every|remaining|the rest|my reminders?)\b"
    r"|"
    r"\b(all|every|my)\b.{0,20}\b(reminders?|todos?|tasks?)\b.{0,40}\b(today|due today)\b.{0,40}\btomorrow\b"
    r"|"
    r"\b(reminders?|todos?|tasks?)\b.{0,30}\b(due )?today\b.{0,30}\btomorrow\b"
    r")",
    re.IGNORECASE | re.DOTALL,
)
_INCOMPLETE_BULK_SHIFT = re.compile(
    r"\b("
    r"only (?:moved |did )?one|not all|didn'?t move them all|didn'?t work|"
    r"missed (?:some|a few|one)|move the rest|do the rest|try again|"
    r"still (?:due|show) today|you missed|fix (?:it|them)"
    r")\b",
    re.IGNORECASE,
)
_TODO_QUERY = re.compile(
    r"\b("
    r"todo|todos|task|tasks|reminder|reminders|list|lists|checklist|"
    r"grocery|groceries|shopping|errand|errands|due|overdue|"
    r"what('?s| is) (?:on|in) my|show my|my (?:list|lists|reminders?|tasks?)|"
    r"add .+ to (?:my )?list|mark .+ (?:done|complete)|"
    r"move .+ to tomorrow|reschedule|shopping list"
    r")\b",
    re.IGNORECASE,
)
_TODO_SYNC_TRANSCRIPT = re.compile(
    r"\b("
    r"added (?:to|on)|removed from|marked (?:as )?(?:done|complete)|"
    r"new (?:list|reminder|task)|delete(?:d)? (?:the )?list|delete all|"
    r"set (?:a )?(?:due|reminder)|moved .+ to tomorrow|"
    r"check(?:ed)? off|uncheck(?:ed)?|groceries|shopping list|"
    r"reminder for|due (?:at|on|tomorrow|today)"
    r")\b",
    re.IGNORECASE,
)
_AFFIRMATIVE = re.compile(
    r"^(yes|yeah|yep|sure|ok(?:ay)?|do it|confirm(?:ed)?|go ahead|please)\.?!?$",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _topic_key(topic: str) -> str:
    return _normalize(topic or DEFAULT_TOPIC)


def _due_local(due_at: datetime, user_timezone: str | None):
    tz = time_context_service.resolve_timezone(user_timezone)
    due = due_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    return due.astimezone(tz)


def _reminder_day_group(todo: TodoItem, user_timezone: str | None) -> tuple[str, str]:
    """Sort key and heading for grouping reminders by calendar day."""
    assert todo.due_at is not None
    tz = time_context_service.resolve_timezone(user_timezone)
    now = datetime.now(tz)
    due_local = _due_local(todo.due_at, user_timezone)
    if not todo.checked and due_local < now:
        return ("0", "Overdue")
    due_date = due_local.date()
    if due_date == now.date():
        return ("1", "Today")
    if due_date == (now + timedelta(days=1)).date():
        return ("2", "Tomorrow")
    return ("3", due_local.strftime("%a %b %d"))


def _todo_priority(
    item: TodoItem,
    *,
    query_text: str | None,
    user_timezone: str | None,
) -> tuple[int, int, datetime]:
    """Lower tuple sorts first — overdue/today reminders beat distant lists."""
    tz = time_context_service.resolve_timezone(user_timezone)
    now = datetime.now(tz)
    bucket = 50
    if item.due_at is not None:
        due_local = _due_local(item.due_at, user_timezone)
        if not item.checked and due_local < now:
            bucket = 0
        elif due_local.date() == now.date():
            bucket = 1
        elif due_local.date() == (now + timedelta(days=1)).date():
            bucket = 2
        elif not item.checked:
            bucket = 4
        else:
            bucket = 6
        sort_due = due_local
    else:
        bucket = 8 if not item.checked else 9
        sort_due = datetime.max.replace(tzinfo=UTC)

    q = _normalize(query_text or "")
    match_rank = 0
    if q:
        hay = f"{_normalize(item.content)} {_topic_key(item.topic)}"
        if q in hay or any(token in hay for token in q.split() if len(token) >= 4):
            match_rank = -1
    return (bucket, match_rank, sort_due)


def select_todos_for_prompt(
    items: list[TodoItem],
    settings: Settings,
    *,
    query_text: str | None = None,
    user_timezone: str | None = None,
) -> list[TodoItem]:
    """Trim large todo snapshots — always keep overdue/today open reminders."""
    limit = max(8, settings.todo_prompt_limit)
    if len(items) <= limit:
        return items

    ranked = sorted(
        items,
        key=lambda item: _todo_priority(item, query_text=query_text, user_timezone=user_timezone),
    )
    return ranked[:limit]


def format_todos_block(items: list[TodoItem], *, user_timezone: str | None = None) -> str:
    if not items:
        return ""

    reminders = [item for item in items if item.due_at is not None]
    list_items = [item for item in items if item.due_at is None]

    overdue_open = [
        item
        for item in reminders
        if not item.checked
        and time_context_service.describe_due_at(item.due_at, user_timezone).startswith("overdue")
    ]

    lines: list[str] = []

    if overdue_open:
        names = ", ".join(f"{i.content} ({i.topic})" for i in overdue_open[:5])
        extra = f" (+{len(overdue_open) - 5} more)" if len(overdue_open) > 5 else ""
        lines.append(
            f"⚠ {len(overdue_open)} overdue reminder(s): {names}{extra} — nudge if relevant."
        )

    if reminders:
        lines.append("User Reminders (in-app calendar — grouped by day):")
        open_reminders = [item for item in reminders if not item.checked]
        done_reminders = [item for item in reminders if item.checked]
        display = open_reminders + done_reminders

        grouped: dict[tuple[str, str], list[TodoItem]] = {}
        for todo in display:
            key = _reminder_day_group(todo, user_timezone)
            grouped.setdefault(key, []).append(todo)

        for key in sorted(grouped.keys(), key=lambda item: item[0]):
            heading = key[1]
            lines.append(f"\n### {heading}")
            day_items = sorted(
                grouped[key],
                key=lambda item: _due_local(item.due_at, user_timezone),  # type: ignore[arg-type]
            )
            for todo in day_items:
                status = "done" if todo.checked else "open"
                mark = "✓" if todo.checked else "○"
                due_local = _due_local(todo.due_at, user_timezone)  # type: ignore[arg-type]
                clock = due_local.strftime("%H:%M")
                due_label = time_context_service.describe_due_at(
                    todo.due_at, user_timezone, checked=todo.checked
                )
                rel = f", {due_label}" if due_label else ""
                topic = todo.topic.strip() or DEFAULT_TOPIC
                lines.append(f"- {mark} {todo.content} at {clock}{rel} ({status}, list: {topic})")

    if list_items:
        by_topic: dict[str, list[TodoItem]] = {}
        for item in list_items:
            topic = item.topic.strip() or DEFAULT_TOPIC
            by_topic.setdefault(topic, []).append(item)

        lines.append("\nUser Lists (no due date — checklists only, not on the Reminders calendar):")
        for topic in sorted(by_topic.keys(), key=str.casefold):
            lines.append(f"\n## {topic}")
            for todo in by_topic[topic]:
                status = "done" if todo.checked else "open"
                mark = "✓" if todo.checked else "○"
                lines.append(f"- {mark} {todo.content} ({status})")

    return "\n".join(lines)


async def load_todos_for_prompt(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    client_timezone: str | None = None,
    query_text: str | None = None,
) -> str:
    items = await todos_repo.list_for_user(session, user.id, limit=settings.todo_inject_limit)
    tz = time_context_service.effective_timezone(user.timezone, client_timezone)
    if not should_inject_todos_prompt(items, query_text=query_text, user_timezone=tz):
        return ""
    selected = select_todos_for_prompt(items, settings, query_text=query_text, user_timezone=tz)
    return format_todos_block(selected, user_timezone=tz)


async def build_todos_system_section(
    session: AsyncSession,
    user: User,
    settings: Settings,
    *,
    client_timezone: str | None = None,
    query_text: str | None = None,
) -> str | None:
    """Todo hint + snapshot block, or None when the turn is unrelated."""
    items = await todos_repo.list_for_user(session, user.id, limit=settings.todo_inject_limit)
    tz = time_context_service.effective_timezone(user.timezone, client_timezone)
    if not should_inject_todos_prompt(items, query_text=query_text, user_timezone=tz):
        return None
    selected = select_todos_for_prompt(items, settings, query_text=query_text, user_timezone=tz)
    block = format_todos_block(selected, user_timezone=tz)
    if block:
        return f"{TODO_HINT}\n\n{block}"
    return TODO_HINT


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


def _transcript_implies_bulk_shift_to_tomorrow(transcript: str) -> bool:
    text = transcript.strip()
    if not text:
        return False
    if _BULK_SHIFT_TO_TOMORROW.search(text):
        return True
    if _INCOMPLETE_BULK_SHIFT.search(text):
        return True
    return False


def query_implies_todos(query_text: str | None) -> bool:
    text = (query_text or "").strip()
    if not text:
        return False
    return bool(_TODO_QUERY.search(text))


def transcript_implies_todo_sync(transcript: str) -> bool:
    text = transcript.strip()
    if not text:
        return False
    if _transcript_implies_bulk_shift_to_tomorrow(text):
        return True
    return bool(_TODO_SYNC_TRANSCRIPT.search(text))


def format_chat_transcript(messages: list[Message]) -> str:
    lines: list[str] = []
    for msg in messages:
        prefix = "User" if msg.role == "user" else "Assistant"
        lines.append(f"{prefix}: {msg.content}")
    return "\n".join(lines)


def should_pre_sync_todos(user_message: str, transcript: str) -> bool:
    if query_implies_todos(user_message):
        return True
    if transcript_implies_todo_sync(transcript):
        return True
    text = user_message.strip()
    if _AFFIRMATIVE.match(text) and re.search(r"\bdelete\b", transcript, re.IGNORECASE):
        return True
    return False


def format_todo_sync_feedback(feedback: list[str]) -> str | None:
    if not feedback:
        return None
    body = "\n".join(f"- {line}" for line in feedback)
    return f"{TODO_SYNC_FEEDBACK_HEADER}{body}"


def _has_overdue_open_reminders(items: list[TodoItem], user_timezone: str | None) -> bool:
    for item in items:
        if item.checked or item.due_at is None:
            continue
        label = time_context_service.describe_due_at(item.due_at, user_timezone)
        if label.startswith("overdue"):
            return True
    return False


def should_inject_todos_prompt(
    items: list[TodoItem],
    *,
    query_text: str | None = None,
    user_timezone: str | None = None,
) -> bool:
    """Skip todo blocks on unrelated turns to save tokens; keep overdue nudges."""
    if query_text and day_planning_service.is_day_planning_question(query_text):
        return True
    if query_implies_todos(query_text):
        return True
    return _has_overdue_open_reminders(items, user_timezone)


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
    items = await todos_repo.list_for_user(session, user_id, limit=500)
    applied = 0
    for action in actions:
        topic = action.topic.strip()
        if not topic:
            continue
        try:
            if action.action == "add":
                content = action.content.strip()
                if not content:
                    continue
                if _find_item_any_state(items, topic, content):
                    continue
                due_at = time_context_service.normalize_due_at(action.due_at, user_timezone)
                await todos_repo.create(
                    session,
                    user_id=user_id,
                    content=content,
                    topic=topic,
                    chat_id=chat_id,
                    due_at=due_at,
                )
                applied += 1
                logger.info(
                    "Todo action applied: user_id=%s action=add topic=%s chat_id=%s",
                    user_id,
                    topic,
                    chat_id,
                )
                items = await todos_repo.list_for_user(session, user_id, limit=500)
            elif action.action == "complete":
                item = _find_item(items, topic, action.content)
                if item and not item.checked:
                    await todos_repo.update(session, item, checked=True)
                    applied += 1
                    logger.info(
                        "Todo action applied: user_id=%s action=complete topic=%s chat_id=%s",
                        user_id,
                        topic,
                        chat_id,
                    )
            elif action.action == "uncheck":
                item = _find_item_any_state(items, topic, action.content)
                if item and item.checked:
                    await todos_repo.update(session, item, checked=False)
                    applied += 1
                    logger.info(
                        "Todo action applied: user_id=%s action=uncheck topic=%s chat_id=%s",
                        user_id,
                        topic,
                        chat_id,
                    )
            elif action.action == "delete":
                item = _find_item_any_state(items, topic, action.content)
                if item:
                    await todos_repo.delete_by_id(session, item.id, user_id)
                    applied += 1
                    logger.info(
                        "Todo action applied: user_id=%s action=delete topic=%s chat_id=%s",
                        user_id,
                        topic,
                        chat_id,
                    )
                    items = [i for i in items if i.id != item.id]
            elif action.action == "delete_list":
                list_items = [
                    i
                    for i in items
                    if _topic_key(i.topic) == _topic_key(topic) and i.due_at is None
                ]
                open_count = sum(1 for i in list_items if not i.checked)
                if open_count > 0:
                    if feedback is not None:
                        feedback.append(
                            f'Blocked delete list "{topic}": {open_count} item(s) still open.'
                        )
                    continue
                removed = await todos_repo.delete_by_topic(session, user_id, topic)
                if removed:
                    applied += 1
                    if feedback is not None:
                        feedback.append(f'Deleted list "{topic}" ({removed} item(s)).')
                    logger.info(
                        "Todo action applied: user_id=%s action=delete_list topic=%s chat_id=%s",
                        user_id,
                        topic,
                        chat_id,
                    )
                    items = [i for i in items if _topic_key(i.topic) != _topic_key(topic)]
                elif feedback is not None:
                    feedback.append(f'List "{topic}" not found or already empty.')
            elif action.action == "set_due":
                due_at = time_context_service.normalize_due_at(action.due_at, user_timezone)
                if action.content.strip() == "*":
                    tz = time_context_service.resolve_timezone(user_timezone)
                    today = datetime.now(tz).date()
                    for item in items:
                        if item.checked or item.due_at is None:
                            continue
                        if _due_local_date(item, user_timezone) != today:
                            continue
                        await todos_repo.update(session, item, due_at=due_at)
                        applied += 1
                        logger.info(
                            "Todo action applied: user_id=%s action=set_due(*) topic=%s chat_id=%s",
                            user_id,
                            topic,
                            chat_id,
                        )
                else:
                    item = _find_item_any_state(items, topic, action.content)
                    if item:
                        await todos_repo.update(session, item, due_at=due_at)
                        applied += 1
                        logger.info(
                            "Todo action applied: user_id=%s action=set_due topic=%s chat_id=%s",
                            user_id,
                            topic,
                            chat_id,
                        )
            elif action.action == "clear_due":
                item = _find_item_any_state(items, topic, action.content)
                if item and item.due_at is not None:
                    await todos_repo.update(session, item, due_at=None)
                    applied += 1
                    logger.info(
                        "Todo action applied: user_id=%s action=clear_due topic=%s chat_id=%s",
                        user_id,
                        topic,
                        chat_id,
                    )
        except Exception:
            logger.exception(
                "Failed todo action %s for user_id=%s topic=%s",
                action.action,
                user_id,
                topic,
            )
    if applied > 0:
        await home_service.invalidate_home_cache(user_id)
    return applied


@dataclass(frozen=True)
class _TodoSyncSnapshot:
    user_timezone: str | None
    snapshot: list[dict[str, Any]]


async def _load_todo_sync_snapshot(
    session: AsyncSession,
    user_id: UUID,
    settings: Settings,
) -> _TodoSyncSnapshot:
    user = await users_repo.get_by_id(session, user_id)
    user_timezone = user.timezone if user else None
    items = await todos_repo.list_for_user(session, user_id, limit=settings.todo_inject_limit)
    return _TodoSyncSnapshot(
        user_timezone=user_timezone,
        snapshot=[
            {
                "topic": item.topic,
                "content": item.content,
                "checked": item.checked,
                "due_at": item.due_at.isoformat() if item.due_at else None,
            }
            for item in items
        ],
    )


async def _apply_todo_extraction_result(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
    result: TodoExtractionResult | None,
    allow_delete_list: bool,
    user_timezone: str | None,
    feedback: list[str] | None = None,
) -> None:
    if result and result.actions:
        safe_actions: list[TodoActionItem] = []
        for action in result.actions:
            if not allow_delete_list and action.action in TODO_BLOCKED_FROM_TRANSCRIPT:
                logger.warning(
                    "Refused destructive todo action %s from transcript for "
                    "user_id=%s topic=%s (requires explicit user action)",
                    action.action,
                    user_id,
                    action.topic,
                )
                continue
            safe_actions.append(action)
            if len(safe_actions) >= MAX_TODO_ACTIONS_PER_TURN:
                break
        if safe_actions:
            await apply_todo_actions(
                session,
                user_id=user_id,
                actions=safe_actions,
                chat_id=chat_id,
                user_timezone=user_timezone,
                feedback=feedback,
            )
    if _transcript_implies_bulk_shift_to_tomorrow(transcript):
        items = await todos_repo.list_for_user(session, user_id, limit=500)
        bulk_applied = await _apply_bulk_shift_due_today_to_tomorrow(
            session,
            user_id=user_id,
            items=items,
            user_timezone=user_timezone,
        )
        if bulk_applied:
            if feedback is not None:
                feedback.append(f"Moved {bulk_applied} reminder(s) due today to tomorrow.")
            logger.info(
                "Bulk-shifted %d todo(s) due today → tomorrow for user_id=%s",
                bulk_applied,
                user_id,
            )
            await home_service.invalidate_home_cache(user_id)


async def _run_extracted_todo_actions(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
    allow_delete_list: bool,
    feedback: list[str] | None = None,
) -> TodoExtractionResult | None:
    from app.core.db import SessionLocal
    from app.gateways import litellm_gateway

    async with SessionLocal() as session:
        loaded = await _load_todo_sync_snapshot(session, user_id, settings)
        await session.commit()

    try:
        result = await litellm_gateway.extract_todo_actions(
            settings,
            transcript,
            loaded.snapshot,
            user_timezone=loaded.user_timezone,
        )
    except Exception:
        logger.exception("Todo action extraction failed for user_id=%s", user_id)
        return None

    async with SessionLocal() as session:
        await _apply_todo_extraction_result(
            session,
            settings,
            user_id=user_id,
            chat_id=chat_id,
            transcript=transcript,
            result=result,
            allow_delete_list=allow_delete_list,
            user_timezone=loaded.user_timezone,
            feedback=feedback,
        )
        await session.commit()
    return result


async def sync_todos_before_reply(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> list[str]:
    """Apply todo mutations before the assistant reply; return user-facing notes."""
    feedback: list[str] = []
    try:
        await _run_extracted_todo_actions(
            settings,
            user_id=user_id,
            chat_id=chat_id,
            transcript=transcript,
            allow_delete_list=True,
            feedback=feedback,
        )
    except Exception:
        logger.exception("Pre-reply todo sync failed for user_id=%s", user_id)
    return feedback


async def sync_todos_from_transcript(
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> TodoExtractionResult | None:
    try:
        return await _run_extracted_todo_actions(
            settings,
            user_id=user_id,
            chat_id=chat_id,
            transcript=transcript,
            allow_delete_list=False,
        )
    except Exception:
        logger.exception("Todo sync failed for user_id=%s", user_id)
        return None
