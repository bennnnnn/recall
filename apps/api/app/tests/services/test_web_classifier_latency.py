"""Foreground classifier eligibility, overlap and bounded fallback behavior."""

import asyncio
from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.models.schemas import WebSearchClassification
from app.services.chat.stream_pipeline import run_tool_loop_path
from app.services.chat.turn_prep.context import (
    StreamContext,
    build_stream_prompt_context,
    stream_context_from_bundle,
)
from app.services.chat.turn_prep.mode import _TurnMode
from app.services.web_search.detection import should_web_search

QUESTION = "Who leads Acme Corporation?"


def _settings(**overrides):
    return Settings(_env_file=None, **overrides)


@pytest.fixture
def prompt_io():
    user = MagicMock(id=uuid4(), plan="free", locale="en", timezone="UTC")
    user.location_enabled = False
    chat = MagicMock(id=uuid4(), summary=None)
    with ExitStack() as stack:
        for target, value in [
            ("build_prompt_messages", [{"role": "user", "content": QUESTION}]),
            ("fetch_integration_blocks", []),
            ("fetch_web_and_tools", (None, None, [], None)),
            ("_load_prior_user_messages", []),
            ("_load_has_calendar_write", False),
        ]:
            stack.enter_context(
                patch(
                    f"app.services.chat.turn_prep.context.{target}", AsyncMock(return_value=value)
                )
            )
        stack.enter_context(
            patch("app.services.model_health.enrich_models_health", AsyncMock(return_value={}))
        )
        stack.enter_context(patch("app.services.plan.chat_fallback_models", return_value=[]))
        stack.enter_context(patch("app.services.plan.model_pool", return_value=[]))
        stack.enter_context(
            patch("app.services.chat.turn_prep.context._instant_reply_needs_db", return_value=False)
        )
        stack.enter_context(
            patch("app.services.time_context.maybe_local_now_reply", return_value=None)
        )
        stack.enter_context(
            patch(
                "app.services.chat.turn_prep.context.inject_web_and_tools",
                AsyncMock(side_effect=lambda messages, *_a, **_kw: messages),
            )
        )

        async def build(content=QUESTION, *, settings=None, rich=True, lightweight=False):
            return await build_stream_prompt_context(
                user.id,
                chat.id,
                content,
                "free-chat",
                settings or _settings(),
                AsyncMock(),
                client_timezone=None,
                client_location=None,
                client_latitude=None,
                client_longitude=None,
                user=user,
                chat=chat,
                turn_mode=_TurnMode(lightweight, rich, False, False, False),
            )

        yield build, user, chat


@pytest.mark.asyncio
async def test_prefetch_overlaps_phase_b_and_preserves_negative_verdict(prompt_io):
    build, user, chat = prompt_io
    integration_started = asyncio.Event()
    classifier_started = asyncio.Event()

    async def integration(*_a, **_kw):
        integration_started.set()
        await classifier_started.wait()
        return []

    async def classify(*_a, **_kw):
        classifier_started.set()
        await integration_started.wait()
        return False

    with (
        patch("app.services.chat.turn_prep.context.fetch_integration_blocks", integration),
        patch(
            "app.services.web_search.detection.should_web_search", AsyncMock(side_effect=classify)
        ) as classify_mock,
    ):
        bundle = await asyncio.wait_for(build(), timeout=1)
    classify_mock.assert_awaited_once()
    assert bundle.web_search_classified is False
    ctx = stream_context_from_bundle(
        bundle,
        user_id=user.id,
        chat_id=chat.id,
        model="free-chat",
        user_message_content=QUESTION,
        reserved_tokens=100,
        user=user,
        prior_count=1,
        chat_project_id=None,
    )
    assert ctx.web_search_classified is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "content,overrides,lightweight,instant,plan",
    [
        ("show me an ear", {}, False, None, "free"),
        ("draw a fox", {}, False, None, "pro"),
        ("What's the latest news on SpaceX?", {}, False, None, "free"),
        ("solve x + 2 = 4", {}, False, None, "free"),
        (QUESTION, {"mcp_tool_loop_enabled": False}, False, None, "free"),
        (QUESTION, {"web_search_enabled": False}, False, None, "free"),
        (QUESTION, {"web_search_classifier_enabled": False}, False, None, "free"),
        (QUESTION, {}, True, None, "free"),
        (QUESTION, {}, False, "Already answered", "free"),
    ],
)
async def test_prefetch_skips_turns_that_cannot_benefit(
    prompt_io, content, overrides, lightweight, instant, plan
):
    build, user, _chat = prompt_io
    user.plan = plan
    with (
        patch("app.services.web_search.detection.should_web_search", AsyncMock()) as classify,
        patch("app.services.time_context.maybe_local_now_reply", return_value=instant),
    ):
        bundle = await build(content, settings=_settings(**overrides), lightweight=lightweight)
    classify.assert_not_awaited()
    assert bundle.web_search_classified is None


@pytest.mark.asyncio
async def test_slim_turn_without_phase_b_work_defers_classification(prompt_io):
    build, _user, _chat = prompt_io
    with patch("app.services.web_search.detection.should_web_search", AsyncMock()) as classify:
        bundle = await build(rich=False)
    assert bundle.web_search_classified is None
    classify.assert_not_awaited()


@pytest.mark.asyncio
async def test_cancelling_prep_cancels_both_phase_b_fetches(prompt_io):
    build, _user, _chat = prompt_io
    started = {name: asyncio.Event() for name in ("integration", "classifier")}
    cancelled = set()

    async def pending(name):
        started[name].set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.add(name)

    with (
        patch(
            "app.services.chat.turn_prep.context.fetch_integration_blocks",
            lambda *_a, **_kw: pending("integration"),
        ),
        patch(
            "app.services.web_search.detection.should_web_search",
            lambda *_a, **_kw: pending("classifier"),
        ),
    ):
        task = asyncio.create_task(build())
        try:
            await asyncio.wait_for(asyncio.gather(*(event.wait() for event in started.values())), 1)
        finally:
            task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert cancelled == {"integration", "classifier"}


@pytest.mark.asyncio
async def test_failed_phase_b_fetch_cancels_classifier_before_returning(prompt_io):
    build, _user, _chat = prompt_io
    classifier_started = asyncio.Event()
    classifier_cancelled = asyncio.Event()

    async def fail(*_a, **_kw):
        await classifier_started.wait()
        raise RuntimeError("integration unavailable")

    async def classify(*_a, **_kw):
        classifier_started.set()
        try:
            await asyncio.Event().wait()
        finally:
            classifier_cancelled.set()

    with (
        patch("app.services.chat.turn_prep.context.fetch_integration_blocks", fail),
        patch("app.services.web_search.detection.should_web_search", classify),
    ):
        with pytest.raises(RuntimeError, match="integration unavailable"):
            await asyncio.wait_for(build(), timeout=1)
    assert classifier_cancelled.is_set()


def _context(**overrides):
    return StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": QUESTION}],
        run_title=False,
        user_message_content=QUESTION,
        reserved_tokens=100,
        max_output_tokens=100,
        **overrides,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("verdict", [True, False])
async def test_final_gate_reuses_both_prefetched_verdicts(verdict):
    ctx = _context(web_search_classified=verdict)
    seams = MagicMock()
    seams.quota_service.global_spend_exceeded = AsyncMock(return_value=False)
    with (
        patch("app.services.web_search.detection.should_web_search", AsyncMock()) as classify,
        patch(
            "app.services.tool_loop.run_tool_rounds",
            AsyncMock(return_value=(ctx.prompt_messages, None, None, [])),
        ) as run,
    ):
        await run_tool_loop_path(
            seams, AsyncMock(), _settings(), ctx, usage={}, on_status=None, should_cancel=None
        )
    classify.assert_not_awaited()
    assert run.await_count == int(verdict)
    if verdict:
        assert run.await_args.kwargs["web_search"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "overrides",
    [
        {"lightweight_turn": True},
        {"instant_reply": "Ready"},
        {"verified_math": MagicMock()},
        {"search_sources": [MagicMock()]},
    ],
)
async def test_final_gate_does_not_classify_ineligible_turns(overrides):
    ctx = _context(**overrides)
    seams = MagicMock()
    seams.quota_service.global_spend_exceeded = AsyncMock(return_value=False)
    with patch("app.services.web_search.detection.should_web_search", AsyncMock()) as classify:
        await run_tool_loop_path(
            seams, AsyncMock(), _settings(), ctx, usage={}, on_status=None, should_cancel=None
        )
    classify.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("slow_stage", ["spend_check", "completion", "accounting"])
async def test_classifier_budget_includes_spend_and_accounting(slow_stage):
    cancelled = asyncio.Event()

    async def slow(*_a, **_kw):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    stages = {
        "spend_check": AsyncMock(return_value=False),
        "completion": AsyncMock(return_value=WebSearchClassification(needs_search=True)),
        "accounting": AsyncMock(return_value=1),
    }
    stages[slow_stage] = AsyncMock(side_effect=slow)
    with (
        patch("app.services.web_search.classify.mock_llm.should_mock_llm", return_value=False),
        patch("app.services.web_search.classify.get_redis_client", return_value=AsyncMock()),
        patch(
            "app.services.web_search.classify.quota_service.global_spend_exceeded",
            stages["spend_check"],
        ),
        patch(
            "app.services.web_search.classify.litellm_gateway.complete_structured",
            stages["completion"],
        ),
        patch(
            "app.services.web_search.classify.quota_service.record_global_spend",
            stages["accounting"],
        ),
    ):
        result = await asyncio.wait_for(
            should_web_search(QUESTION, _settings(web_search_classifier_timeout_seconds=0.01)),
            timeout=1,
        )
    # A completed positive verdict survives slow bookkeeping; otherwise the
    # existing sync heuristic supplies the result after an incomplete call.
    assert result is (slow_stage == "accounting")
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_classifier_failure_keeps_heuristic_fallback():
    with (
        patch(
            "app.services.web_search.classify.classify_web_search_need",
            AsyncMock(side_effect=RuntimeError("unavailable")),
        ),
        patch("app.services.web_search.detection.needs_web_search_heuristic", return_value=True),
    ):
        assert await should_web_search(QUESTION, _settings()) is True


@pytest.mark.asyncio
async def test_explicit_cancellation_propagates_instead_of_becoming_a_verdict():
    entered = asyncio.Event()

    async def classify(*_a, **_kw):
        entered.set()
        await asyncio.Event().wait()

    with patch("app.services.web_search.classify.classify_web_search_need", classify):
        task = asyncio.create_task(should_web_search(QUESTION, _settings()))
        try:
            await asyncio.wait_for(entered.wait(), 1)
        finally:
            task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
