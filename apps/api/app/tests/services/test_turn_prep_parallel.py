"""turn_prep parallelization: fetches run concurrently and inject in stable order.

Guards the refactor that split fetch from inject in ``build_stream_prompt_context``:
- Phase A overlaps ``build_prompt_messages`` with instant-reply resolution.
- Phase B gathers the integration fetch and the web+tools fetch concurrently.
- Phase C injects in the stable order (integration -> web -> math) so the final
  prompt is byte-identical to the prior serial pipeline.
"""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from typing import Any
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
            "differentiate x^2",
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
            "differentiate x^2",
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


def _vocab_turn_mode() -> _TurnMode:
    return _TurnMode(
        lightweight=False,
        rich_context=True,
        minimal_personal=False,
        minimal_quiz=False,
        minimal_vocab_answer=False,
        active_vocab_turn=True,
        day_planning=False,
        day_reflection=False,
        quiz_assistant=None,
    )


def _tool_loop_settings(**kwargs: Any) -> Settings:
    values: dict[str, Any] = {
        "max_output_tokens": 1000,
        "mcp_tool_loop_enabled": True,
        "mcp_tools_enabled": False,
        "math_tools_enabled": True,
        "web_search_enabled": True,
        "web_search_classifier_enabled": True,
        "gmail_enabled": False,
        "google_calendar_enabled": False,
    }
    values.update(kwargs)
    return Settings(**values)


def _prep_patches(*, prompt, instant=None, classify=None):
    patches = [
        patch("app.services.chat.turn_prep.context.SessionLocal", _FakeSessionCM),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(side_effect=prompt)
            if not isinstance(prompt, list)
            else AsyncMock(return_value=list(prompt)),
        ),
        patch(
            "app.services.chat.turn_prep.context._resolve_instant_reply",
            AsyncMock(return_value=instant),
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
    ]
    if classify is not None:
        patches.append(
            patch(
                "app.services.chat.turn_prep.context.web_search_service.should_web_search",
                classify,
            )
        )
    return patches


@pytest.mark.asyncio
async def test_classifier_yes_nudges_and_flags_search():
    from app.services.web_search.detection import WEB_SEARCH_TOOL_NUDGE

    user = _make_user()
    chat = _make_chat()
    messages = [
        {"role": "system", "content": "BASE"},
        {"role": "user", "content": "Who is the CEO of Anthropic?"},
    ]
    classify = AsyncMock(return_value=True)
    with ExitStack() as stack:
        for p in _prep_patches(prompt=messages, classify=classify):
            stack.enter_context(p)
        bundle = await build_stream_prompt_context(
            user.id,
            chat.id,
            "Who is the CEO of Anthropic?",
            "free-chat",
            _tool_loop_settings(),
            MagicMock(),
            client_timezone=None,
            client_location=None,
            client_latitude=None,
            client_longitude=None,
            user=user,
            chat=chat,
            turn_mode=_rich_turn_mode(),
        )
    classify.assert_awaited()
    assert bundle.needs_web_search is True
    assert any(
        m.get("role") == "system" and WEB_SEARCH_TOOL_NUDGE in (m.get("content") or "")
        for m in bundle.prompt_messages
    )


@pytest.mark.asyncio
async def test_classifier_no_skips_nudge_for_stable_topic():
    from app.services.web_search.detection import WEB_SEARCH_TOOL_NUDGE

    user = _make_user()
    chat = _make_chat()
    messages = [
        {"role": "system", "content": "BASE"},
        {"role": "user", "content": "Explain how recursion works in Python"},
    ]
    classify = AsyncMock(return_value=False)
    with ExitStack() as stack:
        for p in _prep_patches(prompt=messages, classify=classify):
            stack.enter_context(p)
        bundle = await build_stream_prompt_context(
            user.id,
            chat.id,
            "Explain how recursion works in Python",
            "free-chat",
            _tool_loop_settings(),
            MagicMock(),
            client_timezone=None,
            client_location=None,
            client_latitude=None,
            client_longitude=None,
            user=user,
            chat=chat,
            turn_mode=_rich_turn_mode(),
        )
    classify.assert_awaited()
    assert bundle.needs_web_search is False
    assert all(
        WEB_SEARCH_TOOL_NUDGE not in (m.get("content") or "") for m in bundle.prompt_messages
    )


@pytest.mark.asyncio
async def test_vocab_quiz_skips_search_classifier():
    user = _make_user()
    chat = _make_chat()
    messages = [
        {"role": "system", "content": "BASE"},
        {"role": "user", "content": "B"},
    ]
    classify = AsyncMock(return_value=True)
    with ExitStack() as stack:
        for p in _prep_patches(prompt=messages, classify=classify):
            stack.enter_context(p)
        bundle = await build_stream_prompt_context(
            user.id,
            chat.id,
            "B",
            "free-chat",
            _tool_loop_settings(),
            MagicMock(),
            client_timezone=None,
            client_location=None,
            client_latitude=None,
            client_longitude=None,
            user=user,
            chat=chat,
            turn_mode=_vocab_turn_mode(),
        )
    classify.assert_not_awaited()
    assert bundle.needs_web_search is False


@pytest.mark.asyncio
async def test_search_classifier_overlaps_prompt_build():
    user = _make_user()
    chat = _make_chat()
    messages = [
        {"role": "system", "content": "BASE"},
        {"role": "user", "content": "Who is the CEO of Anthropic?"},
    ]

    async def slow_prompt(*_a, **_kw):
        await asyncio.sleep(0.25)
        return list(messages)

    async def slow_classify(*_a, **_kw):
        await asyncio.sleep(0.25)
        return True

    with (
        patch("app.services.chat.turn_prep.context.SessionLocal", _FakeSessionCM),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(side_effect=slow_prompt),
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
        patch(
            "app.services.chat.turn_prep.context.web_search_service.should_web_search",
            AsyncMock(side_effect=slow_classify),
        ),
    ):
        loop = asyncio.get_event_loop()
        start = loop.time()
        bundle = await build_stream_prompt_context(
            user.id,
            chat.id,
            "Who is the CEO of Anthropic?",
            "free-chat",
            _tool_loop_settings(),
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

    assert bundle.needs_web_search is True
    assert elapsed < 0.90, f"classifier sat on the critical path (elapsed={elapsed:.2f}s)"


@pytest.mark.asyncio
async def test_model_health_overlaps_prompt_build():
    user = _make_user()
    chat = _make_chat()
    messages = [
        {"role": "system", "content": "BASE"},
        {"role": "user", "content": "explain photosynthesis"},
    ]

    async def slow_prompt(*_a, **_kw):
        await asyncio.sleep(0.25)
        return list(messages)

    async def slow_health(*_a, **_kw):
        await asyncio.sleep(0.25)
        return {}

    with (
        patch("app.services.chat.turn_prep.context.SessionLocal", _FakeSessionCM),
        patch(
            "app.services.chat.turn_prep.context.build_prompt_messages",
            AsyncMock(side_effect=slow_prompt),
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
        patch(
            "app.services.chat.turn_prep.context.plan_service.model_pool",
            return_value=["free-chat"],
        ),
        patch(
            "app.services.model_health.enrich_models_health",
            AsyncMock(side_effect=slow_health),
        ) as health,
    ):
        loop = asyncio.get_event_loop()
        start = loop.time()
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
        elapsed = loop.time() - start

    health.assert_awaited()
    assert elapsed < 0.90, f"model health sat on the critical path (elapsed={elapsed:.2f}s)"


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["explain photosynthesis", "how are you"])
async def test_casual_slim_skips_phase_b_and_email_nudge(text: str):
    user = _make_user()
    chat = _make_chat()
    messages = [
        {"role": "system", "content": "BASE"},
        {"role": "user", "content": text},
    ]
    fetch_integration = AsyncMock(return_value=[])
    fetch_web = AsyncMock(return_value=(None, None, [], None))
    load_nudge = AsyncMock(return_value="- Amazon delivery")
    with ExitStack() as stack:
        for p in _prep_patches(prompt=messages):
            stack.enter_context(p)
        stack.enter_context(
            patch(
                "app.services.chat.turn_prep.context.fetch_integration_blocks",
                fetch_integration,
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.turn_prep.context.fetch_web_and_tools",
                fetch_web,
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.turn_prep.integrations._load_pending_email_nudge",
                load_nudge,
            )
        )
        bundle = await build_stream_prompt_context(
            user.id,
            chat.id,
            text,
            "free-chat",
            _tool_loop_settings(gmail_enabled=True),
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
    load_nudge.assert_not_awaited()
    assert bundle.needs_web_search is False
    assert bundle.verified_math is None


@pytest.mark.asyncio
async def test_math_turn_still_runs_phase_b_web():
    user = _make_user()
    chat = _make_chat()
    messages = [
        {"role": "system", "content": "BASE"},
        {"role": "user", "content": "differentiate x^2"},
    ]
    fetch_web = AsyncMock(return_value=(None, None, [], None))
    fetch_integration = AsyncMock(return_value=[])
    with ExitStack() as stack:
        for p in _prep_patches(prompt=messages):
            stack.enter_context(p)
        stack.enter_context(
            patch(
                "app.services.chat.turn_prep.context.fetch_web_and_tools",
                fetch_web,
            )
        )
        stack.enter_context(
            patch(
                "app.services.chat.turn_prep.context.fetch_integration_blocks",
                fetch_integration,
            )
        )
        await build_stream_prompt_context(
            user.id,
            chat.id,
            "differentiate x^2",
            "free-chat",
            _tool_loop_settings(),
            MagicMock(),
            client_timezone=None,
            client_location=None,
            client_latitude=None,
            client_longitude=None,
            user=user,
            chat=chat,
            turn_mode=_slim_turn_mode(),
        )
    fetch_web.assert_awaited()
    fetch_integration.assert_not_awaited()
