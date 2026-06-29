"""Gmail sync and suggested reminder extraction."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.gateways import google_gmail_gateway as gmail_gateway
from app.gateways import litellm_gateway
from app.gateways.google_gmail_gateway import GmailMessage
from app.models.orm import User
from app.repositories import gmail_connections as gmail_repo
from app.repositories import suggested_reminders as suggested_repo
from app.repositories import todos as todos_repo

logger = logging.getLogger(__name__)

REMINDER_TOPIC = "From email"

GMAIL_HINT = (
    "The user may have Gmail connected (read-only) as a **separate integration** from their "
    "Recall sign-in. When a **Gmail** block is present, use it to answer questions about "
    "recent inbox mail. Suggested reminders from email live on the Reminders screen — "
    "mention them when relevant. If they ask to check email and no Gmail block is present, "
    "tell them to connect Gmail in **Settings → Gmail** (optional; not part of sign-in)."
)

_EXTERNAL_EMAIL = re.compile(
    r"\b("
    r"check my (?:email|inbox|mail)|"
    r"read my (?:email|inbox|mail)|"
    r"what(?:'s| is) in my (?:inbox|email)|"
    r"any (?:new )?emails|"
    r"recent emails|"
    r"my gmail|"
    r"unread (?:email|mail|messages)"
    r")\b",
    re.IGNORECASE,
)


def is_external_email_question(text: str) -> bool:
    cleaned = text.strip()
    if not cleaned:
        return False
    return bool(_EXTERNAL_EMAIL.search(cleaned))


def format_not_connected_answer() -> str:
    return (
        "Gmail isn't connected yet.\n\n"
        "Connecting Gmail is **separate from signing in to Recall** — it is an optional "
        "read-only inbox link you turn on in **Settings → Gmail**. Recall scans your inbox for "
        "actionable items and shows **suggested reminders** on the Reminders screen — "
        "you confirm before anything is added.\n\n"
        "After connecting, ask again and I can summarize recent mail."
    )


def format_inbox_answer(
    *,
    google_email: str,
    messages: list[GmailMessage],
    pending_suggestions: list,
    fetch_error: str | None = None,
) -> str:
    lines = [f"Here's a snapshot of **{google_email}** (read-only):"]

    if fetch_error:
        lines.append("")
        lines.append(f"**Could not load inbox:** {fetch_error}")

    if pending_suggestions:
        lines.append("")
        lines.append(
            f"**Suggested reminders from email** ({len(pending_suggestions)} pending — "
            "open **Reminders** to add or dismiss):"
        )
        for row in pending_suggestions[:6]:
            due = f" — due {row.due_at.strftime('%b %d')}" if row.due_at else ""
            lines.append(f"- {row.title}{due}")

    if messages:
        lines.append("")
        lines.append("**Recent inbox:**")
        for msg in messages[:10]:
            subj = msg.subject or "(no subject)"
            snippet = (msg.snippet or "").strip()
            if snippet:
                lines.append(f"- **{subj}** — {snippet[:160]}")
            else:
                lines.append(f"- **{subj}**")
    elif not pending_suggestions and not fetch_error:
        lines.append("")
        lines.append(
            "No messages in the last 7 days (or inbox is empty). "
            "Tap **Sync** under Settings → Gmail to refresh."
        )

    lines.append("")
    lines.append("Want a summary of a specific thread or help drafting a reply?")
    return "\n".join(lines)


def _cache_key(user_id: UUID) -> str:
    return f"gmail:recent:{user_id}"


async def write_gmail_cache(
    redis: Redis,
    user_id: UUID,
    messages: list[GmailMessage],
    settings: Settings,
) -> None:
    import json

    payload = [{"id": m.id, "subject": m.subject, "snippet": m.snippet} for m in messages]
    try:
        await redis.set(
            _cache_key(user_id),
            json.dumps(payload),
            ex=settings.gmail_cache_ttl,
        )
    except Exception:
        logger.debug("Gmail cache write failed", exc_info=True)


def _messages_from_cache(raw: str) -> list[GmailMessage]:
    import json

    messages: list[GmailMessage] = []
    payload = json.loads(raw)
    for item in payload:
        messages.append(
            GmailMessage(
                id=str(item.get("id") or ""),
                subject=str(item.get("subject") or ""),
                snippet=str(item.get("snippet") or ""),
                body_text="",
                received_at=None,
            )
        )
    return messages


async def is_connected(session: AsyncSession, user_id: UUID) -> bool:
    return await gmail_repo.get_for_user(session, user_id) is not None


def format_gmail_block(
    *,
    google_email: str,
    messages: list[GmailMessage],
    pending_suggestions: list,
    fetch_error: str | None = None,
) -> str:
    lines = [f"Gmail (read-only, {google_email}):"]
    if fetch_error:
        lines.append(f"Inbox fetch failed: {fetch_error}")
    if pending_suggestions:
        lines.append(f"Pending suggested reminders ({len(pending_suggestions)}):")
        for row in pending_suggestions[:8]:
            due = f" — due {row.due_at.isoformat()}" if row.due_at else ""
            lines.append(f"- {row.title}{due}")
    if messages:
        lines.append("Recent inbox (subjects + snippets):")
        for msg in messages[:12]:
            subj = msg.subject or "(no subject)"
            snippet = (msg.snippet or "")[:120]
            lines.append(f"- {subj}: {snippet}")
    elif not pending_suggestions and not fetch_error:
        lines.append("No recent inbox messages found in the last sync window.")
    return "\n".join(lines)


async def load_gmail_context(
    session: AsyncSession,
    redis: Redis,
    user: User,
    settings: Settings,
) -> tuple[str, list[GmailMessage], list, str | None] | None:
    """Return (google_email, recent messages, pending suggestions, fetch_error)."""
    if not gmail_gateway.is_configured(settings):
        return None
    conn = await gmail_repo.get_for_user(session, user.id)
    if conn is None:
        return None

    cache_key = _cache_key(user.id)
    messages: list[GmailMessage] = []
    fetch_error: str | None = None
    try:
        cached = await redis.get(cache_key)
        if cached:
            messages = _messages_from_cache(cached)
    except Exception:
        logger.debug("Gmail cache read failed", exc_info=True)

    if not messages:
        try:
            messages = await gmail_gateway.list_recent_messages(
                settings,
                conn.refresh_token,
                days=settings.gmail_fetch_days,
                max_messages=min(settings.gmail_max_messages, 15),
            )
            await write_gmail_cache(redis, user.id, messages, settings)
        except gmail_gateway.GoogleGmailError as exc:
            fetch_error = str(exc)
            messages = []

    pending = await suggested_repo.list_pending_for_user(session, user.id, limit=20)
    return conn.google_email, messages, pending, fetch_error


async def load_gmail_for_prompt(
    session: AsyncSession,
    redis: Redis,
    user: User,
    settings: Settings,
) -> str | None:
    ctx = await load_gmail_context(session, redis, user, settings)
    if ctx is None:
        return None
    google_email, messages, pending, fetch_error = ctx
    return format_gmail_block(
        google_email=google_email,
        messages=messages,
        pending_suggestions=pending,
        fetch_error=fetch_error,
    )


class SuggestedReminderItem(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    due_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class SuggestedReminderExtractionResult(BaseModel):
    reminders: list[SuggestedReminderItem] = Field(default_factory=list)


def _parse_from_ics(message: GmailMessage) -> SuggestedReminderItem | None:
    if not message.ics_content:
        return None
    title, due_at = gmail_gateway.parse_ics_event(message.ics_content)
    if not title:
        title = message.subject or "Calendar event"
    return SuggestedReminderItem(title=title, due_at=due_at, confidence=0.95, notes=message.snippet)


async def _extract_with_llm(
    settings: Settings, message: GmailMessage
) -> SuggestedReminderItem | None:
    prompt = (
        "Extract at most one actionable reminder from this email. "
        "Look for interviews, flights, appointments, deliveries, deadlines. "
        "If nothing actionable, return {\"reminders\": []}. "
        "Use ISO 8601 UTC for due_at when a specific date/time exists."
    )
    content = (
        f"Subject: {message.subject}\n"
        f"Snippet: {message.snippet}\n"
        f"Body: {(message.body_text or '')[:1500]}"
    )
    result = await litellm_gateway.complete_structured(
        settings=settings,
        model_alias="memory-model",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": content},
        ],
        schema=SuggestedReminderExtractionResult,
        max_tokens=400,
    )
    if not result or not result.reminders:
        return None
    item = result.reminders[0]
    if item.confidence < 0.4:
        return None
    return item


async def _process_message(
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
    message: GmailMessage,
) -> None:
    existing = await suggested_repo.get_by_message_id(session, user_id, message.id)
    if existing is not None:
        return

    extracted = _parse_from_ics(message)
    if extracted is None:
        extracted = await _extract_with_llm(settings, message)
    if extracted is None:
        return

    due_at = extracted.due_at
    if due_at is not None and due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)

    await suggested_repo.create(
        session,
        user_id=user_id,
        gmail_message_id=message.id,
        title=extracted.title.strip(),
        due_at=due_at,
        notes=extracted.notes,
        confidence=extracted.confidence,
        source_snippet=message.snippet[:500] if message.snippet else None,
    )


def gmail_sync_is_due(
    last_sync_at: datetime | None,
    settings: Settings,
    *,
    force: bool = False,
) -> bool:
    if force:
        return True
    if last_sync_at is None:
        return True
    last = last_sync_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    return datetime.now(UTC) - last >= timedelta(seconds=settings.gmail_sync_interval_seconds)


async def sync_gmail_for_user(
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
    *,
    redis: Redis | None = None,
) -> tuple[int, int]:
    """Fetch recent mail, cache for chat, create suggested reminders.

    Returns (message_count, reminders_created).
    """
    if not gmail_gateway.is_configured(settings):
        return 0, 0

    conn = await gmail_repo.get_for_user(session, user_id)
    if conn is None:
        return 0, 0

    try:
        messages = await gmail_gateway.list_recent_messages(
            settings,
            conn.refresh_token,
            days=settings.gmail_fetch_days,
            max_messages=settings.gmail_max_messages,
        )
    except gmail_gateway.GoogleGmailError:
        logger.exception("Gmail fetch failed for user_id=%s", user_id)
        raise

    if redis is not None:
        await write_gmail_cache(redis, user_id, messages, settings)

    created = 0
    for message in messages:
        before = await suggested_repo.get_by_message_id(session, user_id, message.id)
        if before is not None:
            continue
        try:
            await _process_message(session, settings, user_id, message)
            after = await suggested_repo.get_by_message_id(session, user_id, message.id)
            if after is not None:
                created += 1
        except Exception:
            logger.exception("Failed to process gmail message id=%s", message.id)

    await gmail_repo.update_last_sync(session, user_id)
    return len(messages), created


async def add_suggested_reminder(
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
    reminder_id: UUID,
) -> tuple[object | None, str | None]:
    """Convert a pending suggestion into a todo. Returns (todo, error)."""
    row = await suggested_repo.get_by_id(session, reminder_id, user_id)
    if row is None:
        return None, "Not found"
    if row.status != "pending":
        return None, "Already handled"

    content = row.title
    if row.notes:
        content = f"{row.title} — {row.notes}"

    todo = await todos_repo.create(
        session,
        user_id=user_id,
        content=content[:2000],
        topic=REMINDER_TOPIC,
        due_at=row.due_at,
    )
    await suggested_repo.mark_added(session, row, todo.id)
    return todo, None


async def dismiss_suggested_reminder(
    session: AsyncSession,
    user_id: UUID,
    reminder_id: UUID,
) -> bool:
    row = await suggested_repo.get_by_id(session, reminder_id, user_id)
    if row is None or row.status != "pending":
        return False
    await suggested_repo.mark_dismissed(session, row)
    return True
