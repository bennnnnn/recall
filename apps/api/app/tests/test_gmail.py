"""Tests for Gmail gateway and email service."""

from datetime import UTC, datetime
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
        )
    ]
    answer = email_service.format_inbox_answer(
        google_email="me@example.com",
        messages=messages,
        pending_suggestions=[],
    )
    assert "me@example.com" in answer
    assert "**Hello**" in answer
    assert "Quick update" in answer


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

    with patch(
        "app.services.email.suggested_repo.get_by_id",
        AsyncMock(return_value=row),
    ), patch(
        "app.services.email.suggested_repo.mark_dismissed",
        AsyncMock(return_value=row),
    ) as mark_mock:
        ok = await email_service.dismiss_suggested_reminder(session, user_id, reminder_id)
    assert ok is True
    mark_mock.assert_awaited_once()
