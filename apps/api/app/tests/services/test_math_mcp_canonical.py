"""Tool follow-ups must keep the same answer contract as heuristic math."""

from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import Settings
from app.models.schemas.math import MathSeriesResult
from app.services import math_service, math_tools
from app.services.mcp.sympy_adapter import SympyAdapter


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question,args,answer",
    [
        ("integrate x^2", {"action": "integrate", "expr": "x^2"}, r"\frac{x^{3}}{3} + C"),
        (
            "integrate x^2 from 0 to 1",
            {"action": "integrate", "expr": "x^2", "lower": "0", "upper": "1"},
            r"\frac{1}{3}",
        ),
        (
            "limit of 1/x as x approaches 0 from the left",
            {"action": "limit", "expr": "1/x", "point": "0", "direction": "-"},
            r"-\infty",
        ),
        (
            "limit of 1/x as x approaches 0",
            {"action": "limit", "expr": "1/x", "point": "0"},
            None,
        ),
        (
            "sum (-1)^n from n=0 to infinity",
            {"action": "series", "expr": "(-1)^n", "variable": "n", "start": "0", "end": "oo"},
            None,
        ),
        (
            "sum 1/n^2 from n=1 to infinity",
            {"action": "series", "expr": "1/n^2", "variable": "n", "start": "1", "end": "oo"},
            r"\frac{\pi^{2}}{6}",
        ),
        (
            "sum -1 from n=1 to infinity",
            {"action": "series", "expr": "-1", "variable": "n", "start": "1", "end": "oo"},
            r"-\infty",
        ),
    ],
)
async def test_tool_and_heuristic_canonical_answers_agree(question, args, answer):
    settings = Settings(_env_file=None)
    intent = math_tools.extract_math_intent(question)
    assert intent is not None
    block = math_tools._build_verified_block(intent, settings)
    assert block is not None and block.canonical_answer == answer

    async def compute_locally(fn, *values):
        return fn(*values)

    adapter = SympyAdapter(settings)
    with patch.object(adapter, "_run_off_loop", side_effect=compute_locally):
        result = await adapter.invoke(args)
    if answer is None:
        assert result.data is None
    else:
        assert result.data is not None
        assert result.data["canonical_answer"] == answer
        assert result.data["canonical_fence"]["content"] == answer


@pytest.mark.asyncio
async def test_unsolved_tool_series_does_not_attach_an_answer():
    adapter = SympyAdapter(Settings(_env_file=None))
    with patch.object(
        adapter,
        "_run_off_loop",
        AsyncMock(
            return_value=MathSeriesResult(
                result="Sum(...)", latex="unevaluated", is_infinite=False, solved=False
            )
        ),
    ):
        result = await adapter.invoke({"action": "series", "expr": "x"})
    assert result.data is None
    assert "not evaluated" in result.content


@pytest.mark.asyncio
async def test_failed_definite_integral_does_not_retry_as_indefinite():
    adapter = SympyAdapter(Settings(_env_file=None))
    with patch.object(adapter, "_run_off_loop", AsyncMock(return_value=None)) as solve:
        result = await adapter.invoke(
            {"action": "integrate", "expr": "x^2", "lower": "0", "upper": "1"}
        )
    solve.assert_awaited_once_with(math_service.integrate_definite, "x^2", "x", "0", "1")
    assert result.data is None


@pytest.mark.asyncio
async def test_incomplete_integral_bounds_do_not_become_indefinite():
    adapter = SympyAdapter(Settings(_env_file=None))
    with patch.object(adapter, "_run_off_loop", AsyncMock()) as solve:
        result = await adapter.invoke({"action": "integrate", "expr": "x^2", "lower": "0"})
    solve.assert_not_awaited()
    assert result.data is None
    assert "both integral bounds" in result.content
