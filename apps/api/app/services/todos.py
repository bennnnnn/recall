import logging
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.orm import TodoItem, User
from app.models.schemas import TodoActionItem, TodoExtractionResult
from app.repositories import todos as todos_repo
from app.repositories import users as users_repo
from app.repositories.todos import DEFAULT_TOPIC
from app.services import time_context as time_context_service

logger = logging.getLogger(__name__)

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
    "Creating lists via chat — ask for a list title first, then items; changes sync after your reply.\n"
    "Deleting — delete_list removes a whole list; delete removes one item.\n"
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


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _topic_key(topic: str) -> str:
    return _normalize(topic or DEFAULT_TOPIC)


def _due_local(due_at: datetime, user_timezone: str | None):
    tz = time_context_service.resolve_timezone(user_timezone)
    due = due_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
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
                lines.append(
                    f"- {mark} {todo.content} at {clock}{rel} ({status}, list: {topic})"
                )

    if list_items:
        by_topic: dict[str, list[TodoItem]] = {}
        for item in list_items:
            topic = item.topic.strip() or DEFAULT_TOPIC
            by_topic.setdefault(topic, []).append(item)

        lines.append(
            "\nUser Lists (no due date — checklists only, not on the Reminders calendar):"
        )
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
) -> str:
    items = await todos_repo.list_for_user(session, user.id, limit=settings.todo_inject_limit)
    return format_todos_block(items, user_timezone=user.timezone)


def _find_item(items: list[TodoItem], topic: str, content: str) -> TodoItem | None:
    needle = _normalize(content)
    topic_norm = _topic_key(topic)
    candidates = [i for i in items if _topic_key(i.topic) == topic_norm and not i.checked]
    if not candidates:
        candidates = [i for i in items if not i.checked]
    for item in candidates:
        if _normalize(item.content) == needle:
            return item
    for item in candidates:
        if needle in _normalize(item.content) or _normalize(item.content) in needle:
            return item
    return None


def _find_item_any_state(items: list[TodoItem], topic: str, content: str) -> TodoItem | None:
    needle = _normalize(content)
    topic_norm = _topic_key(topic)
    candidates = [i for i in items if _topic_key(i.topic) == topic_norm]
    if not candidates:
        candidates = list(items)
    for item in candidates:
        if _normalize(item.content) == needle:
            return item
    for item in candidates:
        if needle in _normalize(item.content) or _normalize(item.content) in needle:
            return item
    return None


def _due_local_date(item: TodoItem, user_timezone: str | None):
    tz = time_context_service.resolve_timezone(user_timezone)
    due = item.due_at
    if due is None:
        return None
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
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
        due = due.replace(tzinfo=timezone.utc)
    due_local = due.astimezone(tz)
    shifted_local = due_local.replace(
        year=target_date.year,
        month=target_date.month,
        day=target_date.day,
    )
    return shifted_local.astimezone(timezone.utc)


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
                items = await todos_repo.list_for_user(session, user_id, limit=500)
            elif action.action == "complete":
                item = _find_item(items, topic, action.content)
                if item and not item.checked:
                    await todos_repo.update(session, item, checked=True)
                    applied += 1
            elif action.action == "uncheck":
                item = _find_item_any_state(items, topic, action.content)
                if item and item.checked:
                    await todos_repo.update(session, item, checked=False)
                    applied += 1
            elif action.action == "delete":
                item = _find_item_any_state(items, topic, action.content)
                if item:
                    await todos_repo.delete_by_id(session, item.id, user_id)
                    applied += 1
                    items = [i for i in items if i.id != item.id]
            elif action.action == "delete_list":
                removed = await todos_repo.delete_by_topic(session, user_id, topic)
                if removed:
                    applied += 1
                    items = [
                        i for i in items if _topic_key(i.topic) != _topic_key(topic)
                    ]
            elif action.action == "set_due":
                item = _find_item_any_state(items, topic, action.content)
                if item:
                    due_at = time_context_service.normalize_due_at(action.due_at, user_timezone)
                    await todos_repo.update(session, item, due_at=due_at)
                    applied += 1
            elif action.action == "clear_due":
                item = _find_item_any_state(items, topic, action.content)
                if item and item.due_at is not None:
                    await todos_repo.update(session, item, due_at=None)
                    applied += 1
        except Exception:
            logger.exception(
                "Failed todo action %s for user_id=%s topic=%s",
                action.action,
                user_id,
                topic,
            )
    return applied


async def sync_todos_from_transcript(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    chat_id: UUID,
    transcript: str,
) -> TodoExtractionResult | None:
    from app.gateways import litellm_gateway

    user = await users_repo.get_by_id(session, user_id)
    user_timezone = user.timezone if user else None

    items = await todos_repo.list_for_user(session, user_id, limit=settings.todo_inject_limit)
    snapshot = [
        {
            "topic": item.topic,
            "content": item.content,
            "checked": item.checked,
            "due_at": item.due_at.isoformat() if item.due_at else None,
        }
        for item in items
    ]
    try:
        result = await litellm_gateway.extract_todo_actions(
            settings,
            transcript,
            snapshot,
            user_timezone=user_timezone,
        )
        if result and result.actions:
            await apply_todo_actions(
                session,
                user_id=user_id,
                actions=result.actions,
                chat_id=chat_id,
                user_timezone=user_timezone,
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
                logger.info(
                    "Bulk-shifted %d todo(s) due today → tomorrow for user_id=%s",
                    bulk_applied,
                    user_id,
                )
        return result
    except Exception:
        logger.exception("Todo sync failed for user_id=%s", user_id)
        return None
