"""Live done.final_content must match the string we persist."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.gateways.web_search_gateway import WebSearchHit
from app.modules.web_search.formatting import format_sources_fence
from app.services import web_search as web_search_service
from app.services.chat.stream_pipeline import _replace_failed_subject_fences, enrich_final_content
from app.services.solving import VerifiedPhysicsBlock


def _passthrough_math(content: str, verified: object = None) -> str:
    return content


async def _run_sympy_inline(fn: Any, *args: Any, **_kwargs: Any) -> Any:
    return fn(*args)


@asynccontextmanager
async def _fake_session() -> Any:
    yield MagicMock()


def _seams() -> MagicMock:
    seams = MagicMock()
    seams.SessionLocal = _fake_session
    seams.users_repo.get_by_id = AsyncMock(return_value=MagicMock())

    async def _passthrough_calendar(
        _session: object,
        _redis: object,
        _user: object,
        _settings: object,
        text: str,
    ) -> str:
        return text

    async def _passthrough_reminders(_session: object, **kwargs: Any) -> tuple[str, int]:
        return str(kwargs["assistant_text"]), 0

    seams.calendar_service.materialize_calendar_proposals = AsyncMock(
        side_effect=_passthrough_calendar
    )
    seams.todos_service.materialize_reminder_fences = AsyncMock(side_effect=_passthrough_reminders)
    seams.todos_service.transcript_implies_todo_sync = MagicMock(return_value=False)
    seams.math_fence_service.validate_math_fences_worker = _passthrough_math
    seams.math_fence_service.replace_unclosed_graph_fence_safe = lambda content, _canonical: content
    seams.web_search_service = web_search_service
    return seams


def _ctx(
    *, search_sources: list[WebSearchHit] | None = None, local_places: bool = False
) -> MagicMock:
    ctx = MagicMock()
    ctx.user = MagicMock()
    ctx.user.timezone = "UTC"
    ctx.user_timezone = "UTC"
    ctx.user_id = uuid4()
    ctx.chat_id = uuid4()
    ctx.search_sources = search_sources or []
    ctx.verified_subject = None
    ctx.local_places = local_places
    ctx.skip_memory_jobs = False
    ctx.instant_reply = None
    ctx.user_message_content = "what's the news"
    ctx.solver_unverified = False
    ctx.unverified_subject = None
    return ctx


def test_exception_fallback_dispatches_to_chemistry_owner() -> None:
    from app.modules.chemistry.block import build_verified_chemistry
    from app.modules.chemistry.extract import extract_chemistry_intent

    seams = _seams()
    math_safe = MagicMock(return_value="math-safe")
    seams.math_fence_service.replace_unclosed_graph_fence_safe = math_safe
    intent = extract_chemistry_intent("Find pH when [H+] = 0.001")
    assert intent is not None
    verified = build_verified_chemistry(intent)
    assert verified is not None

    result = _replace_failed_subject_fences(seams, "```answer\n4\n```", verified)

    assert "notation: chemistry\npH = 3" in result
    assert "```answer\n4\n```" not in result
    math_safe.assert_not_called()


def test_exception_fallback_dispatches_to_physics_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seams = _seams()
    math_safe = MagicMock(return_value="math-safe")
    seams.math_fence_service.replace_unclosed_graph_fence_safe = math_safe
    verified = VerifiedPhysicsBlock(text="verified", canonical_answer="10 N")
    safe = MagicMock(return_value="physics-safe")
    monkeypatch.setattr(
        "app.modules.physics.fence.replace_unclosed_physics_fences_safe",
        safe,
    )

    result = _replace_failed_subject_fences(seams, "raw", verified)

    assert result == "physics-safe"
    safe.assert_called_once_with("raw", verified)
    math_safe.assert_not_called()


@pytest.mark.asyncio
async def test_reminder_finalization_uses_effective_client_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.modules.math.sympy_executor.run_sympy", _run_sympy_inline)
    seams = _seams()
    ctx = _ctx()
    ctx.user.timezone = "UTC"
    ctx.user_timezone = "America/Los_Angeles"
    ctx.user_message_content = "Remind me tomorrow at 3 PM to submit my application."

    await enrich_final_content(
        seams,
        MagicMock(),
        Settings(chemistry_enabled=False),
        ctx,
        assistant_text="I'll help with that.",
        usage={"input": 1, "output": 2},
        result={},
        was_cancelled=False,
        assistant_parts=["I'll help with that."],
        should_cancel=None,
    )

    kwargs = seams.todos_service.materialize_reminder_fences.await_args.kwargs
    assert kwargs["user_timezone"] == "America/Los_Angeles"


@pytest.mark.asyncio
async def test_search_sources_final_content_matches_persisted_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Appending ```sources used to update persist only; done.final_content
    stayed stripped. Mobile then saw a different string live vs on reload."""
    monkeypatch.setattr("app.modules.math.sympy_executor.run_sympy", _run_sympy_inline)

    hits = [
        WebSearchHit(
            title="Example Source",
            url="https://example.com/a",
            snippet="A snippet about the topic.",
        )
    ]
    prose = "Here is the latest on the topic."
    result: dict[str, Any] = {}
    persisted = await enrich_final_content(
        _seams(),
        MagicMock(),
        Settings(chemistry_enabled=False),
        _ctx(search_sources=hits),
        assistant_text=prose,
        usage={"input": 10, "output": 20},
        result=result,
        was_cancelled=False,
        assistant_parts=[prose],
        should_cancel=None,
    )

    expected_fence = format_sources_fence(hits)
    assert persisted == f"{prose}{expected_fence}".strip()
    assert result["final_content"] == persisted
    assert "```sources" in result["final_content"]
    assert "https://example.com/a" in result["search_sources"]


@pytest.mark.asyncio
async def test_unchanged_turn_omits_final_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.modules.math.sympy_executor.run_sympy", _run_sympy_inline)

    result: dict[str, Any] = {}
    persisted = await enrich_final_content(
        _seams(),
        MagicMock(),
        Settings(chemistry_enabled=False),
        _ctx(),
        assistant_text="Plain answer.",
        usage={"input": 4, "output": 8},
        result=result,
        was_cancelled=False,
        assistant_parts=["Plain answer."],
        should_cancel=None,
    )

    assert persisted == "Plain answer."
    assert "final_content" not in result


@pytest.mark.asyncio
async def test_cancelled_turn_closes_unclosed_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.modules.math.sympy_executor.run_sympy", _run_sympy_inline)

    result: dict[str, Any] = {}
    open_fence = "```mermaid\ngraph TD\n  A-->B"
    persisted = await enrich_final_content(
        _seams(),
        MagicMock(),
        Settings(chemistry_enabled=False),
        _ctx(),
        assistant_text=open_fence,
        usage={"input": 4, "output": 8},
        result=result,
        was_cancelled=True,
        assistant_parts=[open_fence],
        should_cancel=None,
    )

    assert persisted.rstrip().endswith("```")
    assert "Generation stopped" not in persisted
    assert result["final_content"] == persisted


@pytest.mark.asyncio
async def test_truncated_turn_closes_unclosed_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.modules.math.sympy_executor.run_sympy", _run_sympy_inline)

    result: dict[str, Any] = {}
    open_fence = "```python\nprint(1"
    persisted = await enrich_final_content(
        _seams(),
        MagicMock(),
        Settings(chemistry_enabled=False),
        _ctx(),
        assistant_text=open_fence,
        usage={"input": 4, "output": 8},
        result=result,
        was_cancelled=False,
        assistant_parts=[open_fence],
        should_cancel=None,
        completion="interrupted",
    )

    assert persisted.rstrip().endswith("```")
    assert "Generation stopped" not in persisted


@pytest.mark.asyncio
async def test_normal_completion_also_closes_provider_unclosed_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A provider can emit done normally while forgetting the final backticks."""
    monkeypatch.setattr("app.modules.math.sympy_executor.run_sympy", _run_sympy_inline)

    result: dict[str, Any] = {}
    open_fence = "```message\nHappy birthday! Hope you have a wonderful day."
    persisted = await enrich_final_content(
        _seams(),
        MagicMock(),
        Settings(chemistry_enabled=False),
        _ctx(),
        assistant_text=open_fence,
        usage={"input": 4, "output": 8},
        result=result,
        was_cancelled=False,
        assistant_parts=[open_fence],
        should_cancel=None,
        completion="complete",
    )

    assert persisted.rstrip().endswith("```")
    assert result["final_content"] == persisted


@pytest.mark.asyncio
async def test_mermaid_parenthetical_labels_quoted_on_persist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.modules.math.sympy_executor.run_sympy", _run_sympy_inline)

    result: dict[str, Any] = {}
    raw = "```mermaid\nflowchart TD\n  D --> E[Grind Beans (Medium Grind)]\n```"
    persisted = await enrich_final_content(
        _seams(),
        MagicMock(),
        Settings(chemistry_enabled=False),
        _ctx(),
        assistant_text=raw,
        usage={"input": 4, "output": 8},
        result=result,
        was_cancelled=False,
        assistant_parts=[raw],
        should_cancel=None,
    )

    assert 'E["Grind Beans (Medium Grind)"]' in persisted
    assert "E[Grind Beans (Medium Grind)]" not in persisted


@pytest.mark.asyncio
async def test_verified_math_markers_are_stripped_from_final_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stripper must actually run in the pipeline, not just exist.

    Every other test asserts these markers are present in the *prompt*. This
    one asserts the post-stream path removes them from what is persisted and
    shown, since instruction alone never stopped a model echoing them.
    """
    monkeypatch.setattr("app.modules.math.sympy_executor.run_sympy", _run_sympy_inline)
    persisted = await enrich_final_content(
        _seams(),
        MagicMock(),
        Settings(chemistry_enabled=False),
        _ctx(),
        assistant_text=(
            "[BEGIN VERIFIED MATH]\nVerified result: 2.02 s\n[END VERIFIED MATH]\n\n"
            "So it lands after about 2 seconds."
        ),
        usage={"input": 1, "output": 2},
        result={},
        was_cancelled=False,
        assistant_parts=["ignored"],
        should_cancel=None,
    )

    assert "BEGIN VERIFIED" not in persisted
    assert "END VERIFIED" not in persisted
    assert "So it lands after about 2 seconds." in persisted


@pytest.mark.asyncio
async def test_unverified_math_note_appended_to_final_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.math import fence as math_fence_mod

    monkeypatch.setattr("app.modules.math.sympy_executor.run_sympy", _run_sympy_inline)
    seams = _seams()
    seams.math_fence_service.append_unverified_math_note = (
        math_fence_mod.append_unverified_math_note
    )
    ctx = _ctx()
    ctx.solver_unverified = True
    persisted = await enrich_final_content(
        seams,
        MagicMock(),
        Settings(chemistry_enabled=False),
        ctx,
        assistant_text="The mass is 12 kg.",
        usage={"input": 1, "output": 2},
        result={},
        was_cancelled=False,
        assistant_parts=["The mass is 12 kg."],
        should_cancel=None,
    )
    assert "*I couldn't automatically verify this result.*" not in persisted
    assert persisted == "The mass is 12 kg."
    assert "\n>" not in persisted
    assert "```answer" not in persisted


@pytest.mark.asyncio
async def test_unverified_chemistry_uses_the_chemistry_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.chemistry.context import unverified_chemistry_note

    monkeypatch.setattr("app.modules.math.sympy_executor.run_sympy", _run_sympy_inline)
    ctx = _ctx()
    ctx.solver_unverified = True
    ctx.unverified_subject = "chemistry"
    persisted = await enrich_final_content(
        _seams(),
        MagicMock(),
        Settings(chemistry_enabled=True),
        ctx,
        assistant_text="The pH is about 6.",
        usage={"input": 1, "output": 2},
        result={},
        was_cancelled=False,
        assistant_parts=["The pH is about 6."],
        should_cancel=None,
    )
    assert unverified_chemistry_note() not in persisted
    assert persisted == "The pH is about 6."
    assert "*I couldn't automatically verify this result.*" not in persisted


@pytest.mark.asyncio
async def test_direct_verified_math_skips_sympy_pool_for_fence_rewrite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.solving import VerifiedMathBlock

    async def _must_not_run(*_a: Any, **_k: Any) -> str:
        raise AssertionError("direct math must not queue fence rewrite on the pool")

    monkeypatch.setattr("app.modules.math.sympy_executor.run_sympy", _must_not_run)
    ctx = _ctx()
    ctx.instant_reply = "$x = 2$\n\n```answer\nx = 2\n```"
    ctx.verified_subject = VerifiedMathBlock(
        text="verified",
        canonical_fence={"type": "answer", "content": "x = 2"},
        canonical_answer="x = 2",
    )
    ctx.user_message_content = "1+1=x"
    ctx.solver_unverified = False
    persisted = await enrich_final_content(
        _seams(),
        MagicMock(),
        Settings(chemistry_enabled=False),
        ctx,
        assistant_text=ctx.instant_reply,
        usage={"input": 0, "output": 8},
        result={},
        was_cancelled=False,
        assistant_parts=[ctx.instant_reply],
        should_cancel=None,
    )
    assert persisted == ctx.instant_reply


@pytest.mark.asyncio
async def test_paired_direct_reply_keeps_both_answer_fences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.math.fence import needs_math_fence_validate, validate_math_fences

    monkeypatch.setattr("app.modules.math.sympy_executor.run_sympy", _run_sympy_inline)
    seams = _seams()
    seams.math_fence_service.needs_math_fence_validate = needs_math_fence_validate
    seams.math_fence_service.validate_math_fences_worker = validate_math_fences
    reply = (
        "**Answer**\n\n```answer\nnotation: chemistry\nV₂ = 100 mL\n```\n\n"
        "**Answer**\n\n```answer\nx = 3 \\text{ or } x = 4\n```\n"
    )
    ctx = _ctx()
    ctx.instant_reply = reply
    ctx.verified_subject = None
    ctx.user_message_content = (
        "Dilute 25 mL of 1 M NaOH to 0.25 M, and also solve x^2 - 7x + 12 = 0."
    )
    persisted = await enrich_final_content(
        seams,
        MagicMock(),
        Settings(chemistry_enabled=True),
        ctx,
        assistant_text=reply,
        usage={"input": 0, "output": 0},
        result={},
        was_cancelled=False,
        assistant_parts=[reply],
        should_cancel=None,
    )
    assert persisted.count("```answer") == 2
    assert "notation: chemistry\nV₂ = 100 mL" in persisted
    assert "x = 3 \\text{ or } x = 4" in persisted


@pytest.mark.asyncio
async def test_verified_chemistry_replaces_model_answer_without_math_rewrite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.chemistry.block import build_verified_chemistry
    from app.modules.chemistry.extract import extract_chemistry_intent

    monkeypatch.setattr("app.modules.math.sympy_executor.run_sympy", _run_sympy_inline)
    seams = _seams()
    seams.math_fence_service.validate_math_fences_worker = MagicMock(
        side_effect=AssertionError("math fences must not rewrite chemistry")
    )
    question = "Find pH when [H+] = 0.001"
    intent = extract_chemistry_intent(question)
    assert intent is not None
    verified = build_verified_chemistry(intent)
    assert verified is not None
    ctx = _ctx()
    ctx.verified_subject = verified
    ctx.user_message_content = question
    invented = "The pH is 4.\n\n```answer\n4\n```\n\n```smiles\nCCO\n```"
    persisted = await enrich_final_content(
        seams,
        MagicMock(),
        Settings(chemistry_enabled=True),
        ctx,
        assistant_text=invented,
        usage={"input": 1, "output": 2},
        result={},
        was_cancelled=False,
        assistant_parts=[invented],
        should_cancel=None,
    )
    assert persisted.count("```answer") == 1
    assert "notation: chemistry\npH = 3" in persisted
    assert "```smiles" not in persisted
    assert "```answer\n4\n```" not in persisted
