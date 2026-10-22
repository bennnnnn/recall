"""The finalize passes: one declared order, and what a pass's exception does."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.modules.chat import finalize_passes
from app.modules.chat.finalize_passes import (
    FALL_BACK,
    FinalizePass,
    FinalizeState,
    OnError,
    run_finalize_passes,
)
from app.modules.chat.finalize_subjects import (
    check_math_fences,
    draw_formula_charts,
    recover_math_fences,
)
from app.modules.chat.turn_outcome import TurnOutcome
from app.modules.chat.turn_prep import StreamContext
from app.tests.modules.chat.chat_test_support import turn_deps

_FORGED = "Done.\n\n```answer\nverified: true\nx = 7\n```"


def _state(raw: str) -> FinalizeState:
    ctx = StreamContext(
        user_id=uuid4(),
        chat_id=uuid4(),
        model="free-chat",
        prompt_messages=[{"role": "user", "content": "hi"}],
        run_title=False,
        user_message_content="hi",
        reserved_tokens=0,
        max_output_tokens=0,
        answer_photo_ids=[uuid4()],
    )
    return FinalizeState(
        deps=MagicMock(),
        settings=Settings(),
        ctx=ctx,
        raw=raw,
        text=raw,
        usage={},
        outcome=TurnOutcome(),
        was_cancelled=False,
        assistant_parts=[raw],
        should_cancel=None,
    )


def _append(mark: str) -> Any:
    return lambda state: f"{state.text}+{mark}"


def _raise(exc: Exception) -> Any:
    def run(_state: FinalizeState) -> str:
        raise exc

    return run


def test_the_passes_run_in_one_declared_order() -> None:
    order = [
        (finalize_pass.name, finalize_pass.on_error.log_as, finalize_pass.on_error.rewrite)
        for finalize_pass in finalize_passes.FINALIZE_PASSES
    ]
    assert [name for name, *_ in order] == [
        "drop_cut_reminder_fence",
        "prepare_model_reply",
        "answer_labels",
        "untrusted_media",
        "search_links",
        "generic_closer",
        "answer_photo",
        "reply_picture",
        "chemistry_fences",
        "physics_fences",
        "math_fences",
        "formula_charts",
        "server_answer_cards",
        "unverified_notes",
        "working_check",
        "text_plots",
        "solve_markers",
        "chemistry_enrich",
        "settings_card",
        "money_card",
        "request_sections",
        "search_sources",
        "instant_usage",
        "close_fences",
        "clarify_card",
        "requested_json",
        "recipient_placeholders",
        "prose",
        "mermaid_and_places",
        "presentation",
        "clock",
    ]
    # Only the subject fence passes, the chemistry enrichment, the closer strip, the
    # formula charts (left for the phone's note) and the two checks that only ever
    # narrow the reply (search links, requested JSON) go on after a failure; every
    # other pass falls back to the last committed text.
    kept = {name: (log_as, rewrite is not None) for name, log_as, rewrite in order if log_as}
    assert kept == {
        "generic_closer": ("generic_closer", False),
        "search_links": ("search_links", False),
        "requested_json": ("requested_json", False),
        "chemistry_fences": ("validate_math_fences", True),
        "physics_fences": ("validate_math_fences", True),
        "math_fences": ("validate_math_fences", True),
        "chemistry_enrich": ("enrich_chemistry_fences", False),
        "formula_charts": ("formula_charts", False),
    }


@pytest.mark.asyncio
async def test_a_fall_back_failure_stops_the_passes_and_persists_the_safe_raw_reply(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(
        finalize_passes,
        "FINALIZE_PASSES",
        (
            FinalizePass("first", _append("a"), FALL_BACK),
            FinalizePass("broken", _raise(RuntimeError("boom")), FALL_BACK),
            FinalizePass("after", _append("never"), FALL_BACK),
        ),
    )
    state = _state(_FORGED)

    with caplog.at_level(logging.ERROR):
        assert await run_finalize_passes(state) is False

    # The raw reply made safe: the model cannot forge the server's check.
    assert "verified" not in state.text
    assert "x = 7" in state.text
    assert "+a" not in state.text
    assert state.ctx.answer_photo_ids == []
    assert "Post-stream enrichment failed; persisting the last committed text" in caplog.text


@pytest.mark.asyncio
async def test_a_fall_back_failure_keeps_the_committed_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def commit(state: FinalizeState) -> str:
        state.committed = f"{state.text}+chips"
        return state.committed

    monkeypatch.setattr(
        finalize_passes,
        "FINALIZE_PASSES",
        (
            FinalizePass("commit", commit, FALL_BACK),
            # A timeout in a pass that cannot go on falls back like any failure.
            FinalizePass("broken", _raise(TimeoutError("slow")), FALL_BACK),
        ),
    )
    state = _state("reply")
    photo_ids = list(state.ctx.answer_photo_ids)

    assert await run_finalize_passes(state) is False

    assert state.text == "reply+chips"
    assert state.ctx.answer_photo_ids == photo_ids


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc", "level", "message"),
    [
        (TimeoutError("slow"), logging.WARNING, "step timed out; keeping raw assistant text"),
        (RuntimeError("boom"), logging.ERROR, "step failed; keeping raw assistant text"),
    ],
)
@pytest.mark.parametrize("rewrite", [None, _append("recovered")])
async def test_a_logged_failure_hands_on_the_input_or_its_recovery(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    exc: Exception,
    level: int,
    message: str,
    rewrite: Any,
) -> None:
    monkeypatch.setattr(
        finalize_passes,
        "FINALIZE_PASSES",
        (
            FinalizePass("first", _append("a"), FALL_BACK),
            FinalizePass("checked", _raise(exc), OnError(log_as="step", rewrite=rewrite)),
            FinalizePass("after", _append("b"), FALL_BACK),
        ),
    )
    state = _state("reply")

    with caplog.at_level(logging.WARNING):
        assert await run_finalize_passes(state) is True

    assert state.text == ("reply+a+recovered+b" if rewrite else "reply+a+b")
    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [(level, message)]


@pytest.mark.asyncio
async def test_a_failed_recovery_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        finalize_passes,
        "FINALIZE_PASSES",
        (
            FinalizePass(
                "checked",
                _raise(RuntimeError("boom")),
                OnError(log_as="step", rewrite=_raise(RuntimeError("recovery failed"))),
            ),
            FinalizePass("after", _append("never"), FALL_BACK),
        ),
    )
    state = _state("reply")

    assert await run_finalize_passes(state) is False
    assert state.text == "reply"


@pytest.mark.asyncio
async def test_the_maths_pass_runs_the_turns_own_math_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tests swap the maths fence through ``ChatTurnDeps``; the pass must use that one."""

    async def inline(fn: Any, *args: Any, **_kwargs: Any) -> Any:
        return fn(*args)

    monkeypatch.setattr("app.core.sympy_executor.run_sympy", inline)
    state = _state("x = 4")
    state.deps = turn_deps(
        math_fence=SimpleNamespace(
            needs_math_fence_validate=MagicMock(return_value=True),
            validate_math_fences_worker=MagicMock(return_value="checked"),
            replace_unclosed_graph_fence_safe=MagicMock(return_value="recovered"),
        )
    )

    assert await check_math_fences(state) == "checked"
    assert recover_math_fences(state) == "recovered"


@pytest.mark.asyncio
async def test_a_formula_chart_is_drawn_by_sympy_and_a_data_chart_is_left_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def inline(fn: Any, *args: Any, **_kwargs: Any) -> Any:
        return fn(*args)

    monkeypatch.setattr("app.core.sympy_executor.run_sympy", inline)
    formula = (
        "Both curves:\n\n```chart\n"
        '{"type":"function","series":[{"name":"sin","fn":"sin(x)"},{"name":"cos","fn":"cos(x)"}],'
        '"domain":[0,6.2832]}\n```\n\nThey cross twice.'
    )
    drawn = await draw_formula_charts(_state(formula))
    assert "```chart" not in drawn
    assert '```graph\n{"type":"function","expr":"sin(x)"' in drawn
    assert drawn.startswith("Both curves:") and drawn.endswith("They cross twice.")

    data = '```chart\n{"mark":"bar","data":{"values":[{"a":1}]}}\n```'
    assert await draw_formula_charts(_state(data)) == data
