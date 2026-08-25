"""turn_prep parallelization: fetches run concurrently and inject in stable order.

Guards the refactor that split fetch from inject in ``build_stream_prompt_context``:
- Phase A overlaps ``build_prompt_messages`` with instant-reply resolution.
- Phase B gathers the integration fetch and the web+tools fetch concurrently.
- Phase C injects in the stable order (integration -> web -> math) so the final
  prompt is byte-identical to the prior serial pipeline.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.services.chat.turn_prep.context import build_stream_prompt_context
from app.services.chat.turn_prep.mode import _TurnMode


class _FakeSessionCM:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *args):
        return False


def _make_user() -> MagicMock:
    user = MagicMock()
    user.id = uuid4()
    user.response_style = "balanced"
    user.locale = "en"
    user.timezone = None
    user.memory_enabled = True
    user.location_enabled = False
    user.location = None
    return user


def _make_chat() -> MagicMock:
    chat = MagicMock()
    chat.id = uuid4()
    chat.summary = None
    chat.project_id = None
    chat.quiz_mode = None
    return chat


def _rich_turn_mode() -> _TurnMode:
    return _TurnMode(
        lightweight=False,
        rich_context=True,
        minimal_personal=False,
        minimal_quiz=False,
        minimal_vocab_answer=False,
        active_vocab_turn=False,
        day_planning=False,
        day_reflection=False,
        quiz_assistant=None,
    )


def _slim_turn_mode() -> _TurnMode:
    return _TurnMode(
        lightweight=False,
        rich_context=False,
        minimal_personal=False,
        minimal_quiz=False,
        minimal_vocab_answer=False,
        active_vocab_turn=False,
        day_planning=False,
        day_reflection=False,
        quiz_assistant=None,
    )


@pytest.mark.asyncio
async def test_fetches_run_concurrently_not_serially():
    """Phase A (build_prompt | instant_reply) and Phase B (integration | web+tools)
    must overlap, so total time is the max of each pair -- not the sum."""
    user = _make_user()
    chat = _make_chat()

    base_messages = [{"role": "system", "content": "BASE"}, {"role": "user", "content": "hi"}]

    async def slow_prompt(*_a, **_kw):
        await asyncio.sleep(0.25)
        return list(base_messages)

    async def slow_instant_reply(*_a, **_kw):
        await asyncio.sleep(0.25)
        return None

    async def slow_integration(*_a, **_kw):
        await asyncio.sleep(0.30)
        return ["INTEGRATION_BLOCK"]

    async def slow_web(*_a, **_kw):
        await asyncio.sleep(0.30)
        return (None, None, [], None)

    async def fast_inject(*_a, **_kw):
        return list(base_messages)

    with (
        patch("app.services.chat.turn_prep.context.SessionLocal", _FakeSessionCM),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(side_effect=slow_prompt),
        ),
        patch(
            "app.services.chat.turn_prep.context._resolve_instant_reply",
            AsyncMock(side_effect=slow_instant_reply),
        ),
        patch(
            "app.services.chat.turn_prep.context.fetch_integration_blocks",
            AsyncMock(side_effect=slow_integration),
        ),
        patch(
            "app.services.chat.turn_prep.context.fetch_web_and_tools",
            AsyncMock(side_effect=slow_web),
        ),
        patch(
            "app.services.chat.turn_prep.context.inject_web_and_tools",
            AsyncMock(side_effect=fast_inject),
        ),
        patch(
            "app.services.chat.turn_prep.context._load_prior_user_messages",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.chat.turn_prep.context._load_has_calendar_write",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.services.chat.turn_prep.context.extract_settings_changes",
            return_value=[],
        ),
    ):
        loop = asyncio.get_event_loop()
        start = loop.time()
        bundle = await build_stream_prompt_context(
            user.id,
            chat.id,
            "explain photosynthesis",
            "free-chat",
            Settings(
                max_output_tokens=1000,
                mcp_tool_loop_enabled=False,
                mcp_tools_enabled=False,
                math_tools_enabled=True,
                web_search_enabled=True,
                gmail_enabled=False,
                google_calendar_enabled=False,
            ),
            MagicMock(),
            client_timezone=None,
            client_location=None,
            client_latitude=None,
            client_longitude=None,
            user=user,
            chat=chat,
            turn_mode=_rich_turn_mode(),
        )
        elapsed = loop.time() - start

    # Serial would be 0.25 + 0.25 (A) + 0.30 + 0.30 (B) ~= 1.10s. Parallel is
    # max(0.25, 0.25) + max(0.30, 0.30) ~= 0.55s. Allow slack for slow CI.
    assert elapsed < 0.90, f"fetches ran serially (elapsed={elapsed:.2f}s)"
    assert bundle.instant_reply is None
    assert bundle.search_sources == []


@pytest.mark.asyncio
async def test_injects_in_stable_order_integration_then_web_then_math():
    """Real inject functions must place blocks in the historical order:
    integration appended to the system message; web then math inserted
    before the last user message — byte-identical to the serial pipeline."""
    user = _make_user()
    chat = _make_chat()

    base_messages = [{"role": "system", "content": "BASE"}, {"role": "user", "content": "hi"}]

    async def fast_prompt(*_a, **_kw):
        return list(base_messages)

    with (
        patch("app.services.chat.turn_prep.context.SessionLocal", _FakeSessionCM),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(side_effect=fast_prompt),
        ),
        patch(
            "app.services.chat.turn_prep.context._resolve_instant_reply",
            AsyncMock(return_value=None),
        ),
        # Only the FETCHES are mocked; the real inject functions run so we can
        # assert the final prompt shape end-to-end.
        patch(
            "app.services.chat.turn_prep.context.fetch_integration_blocks",
            AsyncMock(return_value=["INTEGRATION_BLOCK"]),
        ),
        patch(
            "app.services.chat.turn_prep.context.fetch_web_and_tools",
            AsyncMock(return_value=("WEB_BLOCK", "MATH_BLOCK", [], None)),
        ),
        patch(
            "app.services.chat.turn_prep.context._load_prior_user_messages",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.chat.turn_prep.context._load_has_calendar_write",
            AsyncMock(return_value=False),
        ),
        patch(
            "app.services.chat.turn_prep.context.extract_settings_changes",
            return_value=[],
        ),
    ):
        bundle = await build_stream_prompt_context(
            user.id,
            chat.id,
            "explain photosynthesis",
            "free-chat",
            Settings(
                max_output_tokens=1000,
                mcp_tool_loop_enabled=False,
                mcp_tools_enabled=False,
                math_tools_enabled=True,
                web_search_enabled=True,
                gmail_enabled=False,
                google_calendar_enabled=False,
            ),
            MagicMock(),
            client_timezone=None,
            client_location=None,
            client_latitude=None,
            client_longitude=None,
            user=user,
            chat=chat,
            turn_mode=_rich_turn_mode(),
        )

    messages = bundle.prompt_messages
    # Integration block appended to the system message.
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "BASE\n\nINTEGRATION_BLOCK"
    # Web then math inserted before the last user message (stable order).
    assert messages[1] == {"role": "system", "content": "WEB_BLOCK"}
    assert messages[2] == {"role": "system", "content": "MATH_BLOCK"}
    assert messages[3] == {"role": "user", "content": "hi"}


@pytest.mark.asyncio
async def test_slim_coaching_turn_skips_phase_b_fetches():
    """Help-me-think must not load gmail-nudge or web/math/chem prefetch."""
    user = _make_user()
    chat = _make_chat()
    base_messages = [{"role": "system", "content": "BASE"}, {"role": "user", "content": "hi"}]
    fetch_integration = AsyncMock(return_value=[])
    fetch_web = AsyncMock(return_value=(None, None, [], None))
    load_prior = AsyncMock(return_value=[])
    load_cal_write = AsyncMock(return_value=False)

    with (
        patch("app.services.chat.turn_prep.context.SessionLocal", _FakeSessionCM),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(return_value=list(base_messages)),
        ),
        patch(
            "app.services.chat.turn_prep.context._resolve_instant_reply",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.chat.turn_prep.context.fetch_integration_blocks",
            fetch_integration,
        ),
        patch(
            "app.services.chat.turn_prep.context.fetch_web_and_tools",
            fetch_web,
        ),
        patch(
            "app.services.chat.turn_prep.context._load_prior_user_messages",
            load_prior,
        ),
        patch(
            "app.services.chat.turn_prep.context._load_has_calendar_write",
            load_cal_write,
        ),
        patch(
            "app.services.chat.turn_prep.context.extract_settings_changes",
            return_value=[],
        ),
    ):
        await build_stream_prompt_context(
            user.id,
            chat.id,
            "I want to talk something through — ask me a good opening question.",
            "free-chat",
            Settings(
                max_output_tokens=1000,
                mcp_tool_loop_enabled=False,
                mcp_tools_enabled=False,
                math_tools_enabled=True,
                web_search_enabled=True,
                gmail_enabled=True,
                google_calendar_enabled=True,
            ),
            MagicMock(),
            client_timezone=None,
            client_location=None,
            client_latitude=None,
            client_longitude=None,
            user=user,
            chat=chat,
            turn_mode=_slim_turn_mode(),
        )

    fetch_integration.assert_not_awaited()
    fetch_web.assert_not_awaited()
    load_prior.assert_not_awaited()
    load_cal_write.assert_not_awaited()


@pytest.mark.asyncio
async def test_calendar_question_skips_prior_messages():
    """Inbox/calendar turns must not load recent user contents for web search."""
    user = _make_user()
    chat = _make_chat()
    base_messages = [{"role": "system", "content": "BASE"}, {"role": "user", "content": "hi"}]
    fetch_integration = AsyncMock(return_value=[])
    fetch_web = AsyncMock(return_value=(None, None, [], None))
    load_prior = AsyncMock(return_value=["earlier question"])
    load_cal_write = AsyncMock(return_value=False)

    with (
        patch("app.services.chat.turn_prep.context.SessionLocal", _FakeSessionCM),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(return_value=list(base_messages)),
        ),
        patch(
            "app.services.chat.turn_prep.context._resolve_instant_reply",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.chat.turn_prep.context.fetch_integration_blocks",
            fetch_integration,
        ),
        patch(
            "app.services.chat.turn_prep.context.fetch_web_and_tools",
            fetch_web,
        ),
        patch(
            "app.services.chat.turn_prep.context._load_prior_user_messages",
            load_prior,
        ),
        patch(
            "app.services.chat.turn_prep.context._load_has_calendar_write",
            load_cal_write,
        ),
        patch(
            "app.services.chat.turn_prep.context.extract_settings_changes",
            return_value=[],
        ),
    ):
        await build_stream_prompt_context(
            user.id,
            chat.id,
            "what's on my calendar tomorrow",
            "free-chat",
            Settings(
                max_output_tokens=1000,
                mcp_tool_loop_enabled=False,
                mcp_tools_enabled=False,
                math_tools_enabled=True,
                web_search_enabled=True,
                gmail_enabled=True,
                google_calendar_enabled=True,
            ),
            MagicMock(),
            client_timezone=None,
            client_location=None,
            client_latitude=None,
            client_longitude=None,
            user=user,
            chat=chat,
            turn_mode=_rich_turn_mode(),
        )

    fetch_integration.assert_awaited()
    fetch_web.assert_not_awaited()
    load_prior.assert_not_awaited()
    load_cal_write.assert_not_awaited()


@pytest.mark.asyncio
async def test_web_augment_loads_priors_without_preloading_calendar_write():
    """Web/math prefetch needs priors; the write flag is not a Phase B barrier."""
    user = _make_user()
    chat = _make_chat()
    base_messages = [{"role": "system", "content": "BASE"}, {"role": "user", "content": "hi"}]
    load_prior = AsyncMock(return_value=["earlier question"])
    load_cal_write = AsyncMock(return_value=True)

    with (
        patch("app.services.chat.turn_prep.context.SessionLocal", _FakeSessionCM),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(return_value=list(base_messages)),
        ),
        patch(
            "app.services.chat.turn_prep.context._resolve_instant_reply",
            AsyncMock(return_value=None),
        ),
        patch(
            "app.services.chat.turn_prep.context.fetch_integration_blocks",
            AsyncMock(return_value=[]),
        ),
        patch(
            "app.services.chat.turn_prep.context.fetch_web_and_tools",
            AsyncMock(return_value=(None, None, [], None)),
        ),
        patch(
            "app.services.chat.turn_prep.context._load_prior_user_messages",
            load_prior,
        ),
        patch(
            "app.services.chat.turn_prep.context._load_has_calendar_write",
            load_cal_write,
        ),
        patch(
            "app.services.chat.turn_prep.context.extract_settings_changes",
            return_value=[],
        ),
    ):
        await build_stream_prompt_context(
            user.id,
            chat.id,
            "explain photosynthesis",
            "free-chat",
            Settings(
                max_output_tokens=1000,
                mcp_tool_loop_enabled=False,
                mcp_tools_enabled=False,
                math_tools_enabled=True,
                web_search_enabled=True,
                gmail_enabled=False,
                google_calendar_enabled=False,
            ),
            MagicMock(),
            client_timezone=None,
            client_location=None,
            client_latitude=None,
            client_longitude=None,
            user=user,
            chat=chat,
            turn_mode=_rich_turn_mode(),
        )

    load_prior.assert_awaited()
    load_cal_write.assert_not_awaited()


@pytest.mark.asyncio
async def test_calendar_write_check_overlaps_calendar_fetch():
    """Create-event write access must share the gather with the calendar API."""
    from app.services.calendar import CALENDAR_WRITE_HINT
    from app.services.chat.turn_prep.integrations import fetch_integration_blocks

    user = _make_user()

    async def slow_cal(*_a: object, **_kw: object) -> str:
        await asyncio.sleep(0.20)
        return "CAL"

    async def slow_write(*_a: object, **_kw: object) -> bool:
        await asyncio.sleep(0.20)
        return True

    with (
        patch(
            "app.services.chat.turn_prep.integrations.calendar_service.should_inject_calendar_block",
            return_value=True,
        ),
        patch(
            "app.services.chat.turn_prep.integrations.email_service.should_inject_gmail_block",
            return_value=False,
        ),
        patch(
            "app.services.chat.turn_prep.integrations._load_calendar_prompt_block",
            AsyncMock(side_effect=slow_cal),
        ),
        patch(
            "app.services.chat.turn_prep.integrations._load_has_calendar_write",
            AsyncMock(side_effect=slow_write),
        ),
    ):
        loop = asyncio.get_event_loop()
        start = loop.time()
        blocks = await fetch_integration_blocks(
            "schedule a meeting tomorrow",
            user,
            MagicMock(),
            Settings(
                gmail_enabled=False,
                google_calendar_enabled=True,
                mcp_tools_enabled=False,
            ),
            instant_reply=None,
            lightweight=False,
            minimal_personal=False,
            minimal_quiz=False,
            day_reflection=False,
            gmail_context=None,
            on_status=None,
        )
        elapsed = loop.time() - start

    assert elapsed < 0.35, f"write check ran serially (elapsed={elapsed:.2f}s)"
    assert any("CAL" in block for block in blocks)
    assert CALENDAR_WRITE_HINT in blocks


@pytest.mark.asyncio
async def test_non_create_turn_skips_calendar_write_session():
    from app.services.chat.turn_prep.integrations import fetch_integration_blocks

    user = _make_user()
    load_write = AsyncMock(return_value=True)

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
            "app.services.chat.turn_prep.integrations._load_has_calendar_write",
            load_write,
        ),
        patch(
            "app.services.chat.turn_prep.integrations._load_pending_email_nudge",
            AsyncMock(return_value=None),
        ),
    ):
        await fetch_integration_blocks(
            "explain photosynthesis",
            user,
            MagicMock(),
            Settings(gmail_enabled=True, google_calendar_enabled=True, mcp_tools_enabled=False),
            instant_reply=None,
            lightweight=False,
            minimal_personal=False,
            minimal_quiz=False,
            day_reflection=False,
            gmail_context=None,
            on_status=None,
        )

    load_write.assert_not_awaited()
