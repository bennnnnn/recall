from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat.turn_prep.integrations import _inject_integration_blocks


@pytest.mark.asyncio
async def test_injects_pending_email_nudge_on_unrelated_turn():
    user = MagicMock()
    user.id = uuid4()
    settings = Settings(gmail_enabled=True, google_calendar_enabled=False)
    with (
        patch(
            "app.services.chat.turn_prep.integrations.calendar_service.should_inject_calendar_block",
            return_value=False,
        ),
        patch(
            "app.services.chat.turn_prep.integrations.email_service.should_inject_gmail_block",
            return_value=False,
        ),
        patch(
            "app.services.chat.turn_prep.integrations._load_pending_email_nudge",
            AsyncMock(return_value="- Amazon delivery (from Amazon)"),
        ),
    ):
        out = await _inject_integration_blocks(
            [{"role": "system", "content": "base"}],
            "plan my day",
            user,
            MagicMock(),
            settings,
            instant_reply=None,
            lightweight=False,
            minimal_personal=False,
            minimal_quiz=False,
            day_reflection=False,
            has_calendar_write=False,
            gmail_context=None,
            on_status=None,
            allow_email_nudge=True,
        )
    assert "Amazon delivery" in out[0]["content"]
    assert "unrelated turns" in out[0]["content"]


@pytest.mark.asyncio
async def test_skips_email_nudge_when_full_gmail_block_present():
    user = MagicMock()
    user.id = uuid4()
    settings = Settings(gmail_enabled=True, google_calendar_enabled=False)
    load_nudge = AsyncMock(return_value="- should not appear")
    with (
        patch(
            "app.services.chat.turn_prep.integrations.calendar_service.should_inject_calendar_block",
            return_value=False,
        ),
        patch(
            "app.services.chat.turn_prep.integrations.email_service.should_inject_gmail_block",
            return_value=True,
        ),
        patch(
            "app.services.chat.turn_prep.integrations._load_pending_email_nudge",
            load_nudge,
        ),
        patch(
            "app.services.chat.turn_prep.integrations.email_service.format_gmail_block",
            return_value="full inbox",
        ),
        patch(
            "app.services.chat.turn_prep.integrations.email_service.is_external_email_question",
            return_value=True,
        ),
    ):
        out = await _inject_integration_blocks(
            [{"role": "system", "content": "base"}],
            "check my email",
            user,
            MagicMock(),
            settings,
            instant_reply=None,
            lightweight=False,
            minimal_personal=False,
            minimal_quiz=False,
            day_reflection=False,
            has_calendar_write=False,
            gmail_context=("me@example.com", [], [], None),
            on_status=None,
        )
    load_nudge.assert_not_awaited()
    assert "full inbox" in out[0]["content"]
    assert "should not appear" not in out[0]["content"]


@pytest.mark.asyncio
async def test_skips_email_nudge_on_casual_explain():
    user = MagicMock()
    user.id = uuid4()
    settings = Settings(gmail_enabled=True, google_calendar_enabled=False)
    load_nudge = AsyncMock(return_value="- Amazon delivery (from Amazon)")
    with (
        patch(
            "app.services.chat.turn_prep.integrations.calendar_service.should_inject_calendar_block",
            return_value=False,
        ),
        patch(
            "app.services.chat.turn_prep.integrations.email_service.should_inject_gmail_block",
            return_value=False,
        ),
        patch(
            "app.services.chat.turn_prep.integrations._load_pending_email_nudge",
            load_nudge,
        ),
    ):
        out = await _inject_integration_blocks(
            [{"role": "system", "content": "base"}],
            "explain photosynthesis",
            user,
            MagicMock(),
            settings,
            instant_reply=None,
            lightweight=False,
            minimal_personal=False,
            minimal_quiz=False,
            day_reflection=False,
            has_calendar_write=False,
            gmail_context=None,
            on_status=None,
        )
    load_nudge.assert_not_awaited()
    assert out[0]["content"] == "base"
