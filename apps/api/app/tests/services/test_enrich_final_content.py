"""Live done.final_content must match the string we persist."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.gateways.web_search_gateway import WebSearchHit
from app.services import web_search as web_search_service
from app.services.chat.stream_pipeline import enrich_final_content
from app.services.web_search.formatting import format_sources_fence


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
    ctx.user_id = uuid4()
    ctx.chat_id = uuid4()
    ctx.search_sources = search_sources or []
    ctx.verified_math = None
    ctx.local_places = local_places
    ctx.skip_memory_jobs = False
    ctx.instant_reply = None
    ctx.user_message_content = "what's the news"
    return ctx


@pytest.mark.asyncio
async def test_search_sources_final_content_matches_persisted_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Appending ```sources used to update persist only; done.final_content
    stayed stripped. Mobile then saw a different string live vs on reload."""
    monkeypatch.setattr("app.services.sympy_executor.run_sympy", _run_sympy_inline)

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
    monkeypatch.setattr("app.services.sympy_executor.run_sympy", _run_sympy_inline)

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
    monkeypatch.setattr("app.services.sympy_executor.run_sympy", _run_sympy_inline)

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
async def test_mermaid_parenthetical_labels_quoted_on_persist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.sympy_executor.run_sympy", _run_sympy_inline)

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
    assert result["final_content"] == persisted
