"""Tests for Gmail gateway and email service."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.gateways.google_gmail_gateway import GmailMessage, parse_ics_event
from app.services.email import _parse_from_ics


def test_is_external_email_question():
    from app.services import email as email_service

    assert email_service.is_external_email_question("check my email")
    assert email_service.is_external_email_question("what's in my inbox")
    assert not email_service.is_external_email_question("write an email to my boss")


def test_should_inject_gmail_block_for_inbox_and_day_planning():
    from app.services import email as email_service

    assert email_service.should_inject_gmail_block("check my email")
    assert email_service.should_inject_gmail_block(
        "How's my day looking so far — anything you think I should prioritize?"
    )
    assert not email_service.should_inject_gmail_block(
        "How did my day go? Help me reflect and wrap up loose ends."
    )
    assert not email_service.should_inject_gmail_block("solve x^2 = 4")
    assert not email_service.should_inject_gmail_block("best restaurants near me")


def test_format_inbox_answer_lists_messages():
    from app.gateways.google_gmail_gateway import GmailMessage
    from app.services import email as email_service

    messages = [
        GmailMessage(
            id="1",
            subject="Hello",
            snippet="Quick update",
            body_text="",
            received_at=None,
            from_address="Friend <friend@example.com>",
            label_ids=("INBOX", "UNREAD"),
        )
    ]
    answer = email_service.format_inbox_answer(
        google_email="me@example.com",
        messages=messages,
        pending_suggestions=[],
    )
    assert "me@example.com" in answer
    assert "Needs attention" in answer
    assert "Hello" in answer


def test_parse_ics_event_extracts_title_and_time():
    ics = """BEGIN:VCALENDAR
BEGIN:VEVENT
SUMMARY:Interview with Acme
DTSTART:20260630T140000Z
END:VEVENT
END:VCALENDAR"""
    title, due_at = parse_ics_event(ics)
    assert title == "Interview with Acme"
    assert due_at == datetime(2026, 6, 30, 14, 0, tzinfo=UTC)


def test_parse_from_ics_message():
    message = GmailMessage(
        id="msg1",
        subject="Invite",
        snippet="snippet",
        body_text="",
        received_at=None,
        ics_content="SUMMARY:Flight AA123\nDTSTART:20260701T080000Z",
    )
    item = _parse_from_ics(message)
    assert item is not None
    assert item.title == "Flight AA123"
    assert item.confidence >= 0.9


@pytest.mark.asyncio
async def test_sync_gmail_skips_when_not_connected():
    from app.services import email as email_service

    session = MagicMock()
    settings = Settings()
    with patch(
        "app.services.email.gmail_repo.get_for_user",
        AsyncMock(return_value=None),
    ):
        count = await email_service.sync_gmail_for_user(session, settings, uuid4())
    assert count == (0, 0)


@pytest.mark.asyncio
async def test_dismiss_suggested_reminder():
    from app.models.orm import SuggestedReminder
    from app.services import email as email_service

    user_id = uuid4()
    reminder_id = uuid4()
    row = SuggestedReminder(
        id=reminder_id,
        user_id=user_id,
        gmail_message_id="g1",
        title="Test",
        status="pending",
    )
    session = MagicMock()

    with (
        patch(
            "app.services.email.suggested_repo.get_by_id",
            AsyncMock(return_value=row),
        ),
        patch(
            "app.services.email.suggested_repo.mark_dismissed",
            AsyncMock(return_value=row),
        ) as mark_mock,
    ):
        ok = await email_service.dismiss_suggested_reminder(session, user_id, reminder_id)
    assert ok is True
    mark_mock.assert_awaited_once()


def test_format_not_connected_answer_mentions_settings():
    from app.services import email as email_service

    answer = email_service.format_not_connected_answer()
    assert "Settings" in answer
    assert "Gmail" in answer


def test_format_gmail_block_includes_pending_and_messages():
    from app.gateways.google_gmail_gateway import GmailMessage
    from app.services import email as email_service

    pending = MagicMock()
    pending.title = "Pay rent"
    pending.due_at = datetime(2026, 6, 30, tzinfo=UTC)
    block = email_service.format_gmail_block(
        google_email="me@example.com",
        messages=[
            GmailMessage(
                id="1",
                subject="Hello",
                snippet="Hi",
                body_text="",
                received_at=None,
                from_address="Friend <friend@example.com>",
                label_ids=("INBOX", "UNREAD"),
            )
        ],
        pending_suggestions=[pending],
    )
    assert "Pay rent" in block
    assert "Hello" in block


def test_gmail_sync_is_due():
    from app.core.config import Settings
    from app.services import email as email_service

    settings = Settings()
    assert email_service.gmail_sync_is_due(None, settings) is True
    assert email_service.gmail_sync_is_due(datetime.now(UTC), settings, force=True) is True
    old = datetime.now(UTC) - timedelta(days=2)
    assert email_service.gmail_sync_is_due(old, settings) is True


def test_messages_from_cache_roundtrip():
    import json

    from app.services import email as email_service

    raw = json.dumps([{"id": "1", "subject": "Hi", "snippet": "There"}])
    messages = email_service._messages_from_cache(raw)
    assert len(messages) == 1
    assert messages[0].subject == "Hi"


@pytest.mark.asyncio
async def test_write_gmail_cache_sets_redis():
    from app.core.config import Settings
    from app.gateways.google_gmail_gateway import GmailMessage
    from app.services import email as email_service

    redis = AsyncMock()
    settings = Settings()
    await email_service.write_gmail_cache(
        redis,
        uuid4(),
        [
            GmailMessage(
                id="1",
                subject="A",
                snippet="B",
                body_text="",
                received_at=None,
            )
        ],
        settings,
    )
    redis.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_is_connected():
    from app.services import email as email_service

    session = MagicMock()
    with patch(
        "app.services.email.gmail_repo.get_for_user",
        AsyncMock(return_value=MagicMock()),
    ):
        assert await email_service.is_connected(session, uuid4()) is True


@pytest.mark.asyncio
async def test_load_gmail_context_uses_cache():
    from app.gateways import google_gmail_gateway
    from app.services import email as email_service

    session = MagicMock()
    redis = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    settings = Settings()
    conn = MagicMock()
    conn.google_email = "me@example.com"
    conn.refresh_token = "refresh"

    cached = '[{"id": "1", "subject": "Cached", "snippet": "Hi"}]'

    with (
        patch.object(google_gmail_gateway, "is_configured", return_value=True),
        patch(
            "app.services.email.gmail_repo.get_for_user",
            AsyncMock(return_value=conn),
        ),
        patch.object(redis, "get", AsyncMock(return_value=cached)),
        patch(
            "app.services.email.suggested_repo.list_pending_for_user",
            AsyncMock(return_value=[]),
        ),
    ):
        ctx = await email_service.load_gmail_context(session, redis, user, settings)

    assert ctx is not None
    email, messages, pending, fetch_error = ctx
    assert email == "me@example.com"
    assert messages[0].subject == "Cached"
    assert pending == []
    assert fetch_error is None


@pytest.mark.asyncio
async def test_load_gmail_context_uses_empty_cache_without_refetch():
    from app.gateways import google_gmail_gateway
    from app.services import email as email_service

    session = MagicMock()
    redis = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    settings = Settings()
    conn = MagicMock()
    conn.google_email = "me@example.com"
    conn.refresh_token = "refresh"

    list_recent = AsyncMock()

    with (
        patch.object(google_gmail_gateway, "is_configured", return_value=True),
        patch(
            "app.services.email.gmail_repo.get_for_user",
            AsyncMock(return_value=conn),
        ),
        patch.object(redis, "get", AsyncMock(return_value="[]")),
        patch.object(google_gmail_gateway, "list_recent_messages", list_recent),
        patch(
            "app.services.email.suggested_repo.list_pending_for_user",
            AsyncMock(return_value=[]),
        ),
    ):
        ctx = await email_service.load_gmail_context(session, redis, user, settings)

    assert ctx is not None
    _, messages, _, fetch_error = ctx
    assert messages == []
    assert fetch_error is None
    list_recent.assert_not_called()


@pytest.mark.asyncio
async def test_load_gmail_for_prompt_returns_block():
    from app.services import email as email_service

    session = MagicMock()
    redis = AsyncMock()
    user = MagicMock()
    user.id = uuid4()
    settings = Settings()

    with patch(
        "app.services.email.load_gmail_context",
        AsyncMock(
            return_value=(
                "me@example.com",
                [],
                [],
                None,
            )
        ),
    ):
        block = await email_service.load_gmail_for_prompt(session, redis, user, settings)

    assert block is not None
    assert "me@example.com" in block


def test_format_gmail_block_fetch_error():
    from app.services import email as email_service

    block = email_service.format_gmail_block(
        google_email="me@example.com",
        messages=[],
        pending_suggestions=[],
        fetch_error="token expired",
    )
    assert "token expired" in block


@pytest.mark.asyncio
async def test_sync_gmail_processes_messages():
    from app.gateways.google_gmail_gateway import GmailMessage
    from app.services import email as email_service

    session = MagicMock()
    settings = Settings()
    user_id = uuid4()
    conn = MagicMock()
    conn.refresh_token = "refresh"
    conn.google_email = "me@example.com"

    message = GmailMessage(
        id="g1",
        subject="Flight",
        snippet="Your flight",
        body_text="",
        received_at=None,
        ics_content="SUMMARY:Flight AA123\nDTSTART:20260701T080000Z",
    )
    created_row = MagicMock()

    with (
        patch(
            "app.services.email.gmail_gateway.is_configured",
            return_value=True,
        ),
        patch(
            "app.services.email.gmail_repo.get_for_user",
            AsyncMock(return_value=conn),
        ),
        patch(
            "app.services.email.gmail_gateway.list_recent_messages",
            AsyncMock(return_value=[message]),
        ),
        patch(
            "app.services.email.suggested_repo.get_by_message_id",
            AsyncMock(side_effect=[None, None, created_row]),
        ),
        patch(
            "app.services.email.suggested_repo.create",
            AsyncMock(return_value=created_row),
        ) as create_mock,
        patch(
            "app.services.email.gmail_repo.update_last_sync",
            AsyncMock(),
        ),
    ):
        message_count, reminders_created = await email_service.sync_gmail_for_user(
            session, settings, user_id
        )

    assert message_count == 1
    assert reminders_created == 1
    create_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_disconnect_gmail_clears_redis_cache():
    from app.routers.gmail_integrations import disconnect_gmail
    from app.services import email as email_service

    user = MagicMock()
    user.id = uuid4()
    session = AsyncMock()
    redis = AsyncMock()

    with (
        patch(
            "app.routers.gmail_integrations.suggested_repo.delete_for_user",
            AsyncMock(),
        ),
        patch(
            "app.routers.gmail_integrations.gmail_repo.delete_for_user",
            AsyncMock(),
        ),
    ):
        await disconnect_gmail(user=user, session=session, redis=redis)

    redis.delete.assert_awaited_once_with(email_service._cache_key(user.id))
