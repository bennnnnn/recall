"""A SymPy tool result is the verified answer only when it computes what the question asks.

Live, grade 12 book (2026-11-14): the model called the server's SymPy tool for a step of its
working, the call's formula was the user's, and the step became the checked card. f'(x) =
2x - 1 stood for lim_{h->0} (f(3 + h) - f(3))/h (asked: 5), the first derivative for
d^2y/dx^2, f'(x) for the absolute maximum and minimum and for the local extreme values,
and the simplified f for a curve sketch. A step stays a step: its result reaches the model
with a note, and the model's own answer stands unchecked.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.gateways import litellm_gateway
from app.gateways.mcp import registry as mcp_registry
from app.modules.chat import tool_loop
from app.modules.math.subject import MathTool
from app.modules.math.tool_check import tool_call_matches_user_text

from .tool_loop_support import settings

_LIMIT = "Let f(x) = x² − x + 3. Find lim_{h→0} (f(3 + h) − f(3))/h."
_SECOND = "Find d²y/dx² for y = cos²(2x + 1)."
_ABSOLUTE = (
    "Identify the critical numbers and find the absolute maximum and absolute minimum values "
    "of f(x) = 2cos x + x on [0, 2π]."
)
_LOCAL = "Find the local maximum and minimum values of f(x) = 2x − 3x^(2/3)."
_SKETCH = (
    "Sketch the graph of f(x) = {f}, indicating the domain, the intercepts, the asymptotes "
    "(if any), the intervals of monotonicity, the local extreme values, the intervals of "
    "concavity and the inflection points."
)


async def _inline(fn: Any, *args: Any, **_kwargs: Any) -> Any:
    return fn(*args)


def _round(args: dict[str, Any]) -> AsyncMock:
    function = {"name": "sympy", "arguments": json.dumps(args)}
    call: dict[str, Any] = {"id": "s1", "type": "function", "function": function}
    return AsyncMock(side_effect=[{"content": None, "tool_calls": [call]}])


def _result(answer: str) -> MagicMock:
    return MagicMock(
        content=f"Verified result: {answer}",
        data={"canonical_fence": {"type": "answer", "content": answer}, "canonical_answer": answer},
    )


async def _run(prompt: str, args: dict[str, Any], answer: str) -> tuple[list[Any], Any]:
    with (
        patch.object(litellm_gateway, "complete_with_tools", _round(args)),
        patch.object(mcp_registry, "invoke_validated", AsyncMock(return_value=_result(answer))),
        patch("app.core.sympy_executor.run_sympy", _inline),
    ):
        out, verified, _terminal, _hits = await tool_loop.run_tool_rounds(
            settings=settings(mcp_tool_loop_enabled=True, mcp_tool_loop_max_rounds=1),
            messages=[{"role": "user", "content": prompt}],
            usage={},
        )
    return out, verified


@pytest.mark.parametrize(
    ("prompt", "args", "answer"),
    [
        (_LIMIT, {"action": "diff", "expr": "x**2 - x + 3"}, "2 x - 1"),
        (_SECOND, {"action": "diff", "expr": "cos(2*x + 1)**2"}, "- 2 \\sin{(4 x + 2)}"),
        (_ABSOLUTE, {"action": "diff", "expr": "2*cos(x) + x"}, "1 - 2 \\sin{(x)}"),
        (_LOCAL, {"action": "diff", "expr": "2*x - 3*x**(2/3)"}, "2 - 2/x^{1/3}"),
        (
            _SKETCH.format(f="(1/4)x⁴ − 2x²"),
            {"action": "diff", "expr": "x**4/4 - 2*x**2"},
            "x (x^{2} - 4)",
        ),
        (
            _SKETCH.format(f="(2x − 6)/(x² − 9)"),
            {"action": "simplify", "expr": "(2*x - 6)/(x**2 - 9)"},
            "\\frac{2}{x + 3}",
        ),
    ],
)
async def test_a_step_of_the_working_is_not_the_verified_answer(
    sympy_registered: None, prompt: str, args: dict[str, Any], answer: str
) -> None:
    out, verified = await _run(prompt, args, answer)
    assert verified is None
    tool_message = next(m for m in out if m.get("role") == "tool")
    # The result reaches the model with a note that it is no verified answer.
    assert tool_message["content"] != f"Verified result: {answer}"


@pytest.mark.parametrize(
    ("prompt", "args", "answer"),
    [
        (_SECOND, {"action": "diff", "expr": "cos(2*x + 1)**2", "order": 2}, "-8 cos(4x + 2)"),
        ("Differentiate x^3 sin x", {"action": "diff", "expr": "x**3*sin(x)"}, "x^2 (...)"),
        (
            "Integrate x^2 from 0 to 3",
            {"action": "integrate", "expr": "x**2", "lower": "0", "upper": "3"},
            "9",
        ),
        ("Solve 2x + 5 = 17", {"action": "solve", "lhs": "2*x + 5", "rhs": "17"}, "x = 6"),
    ],
)
async def test_the_quantity_asked_is_the_verified_answer(
    sympy_registered: None, prompt: str, args: dict[str, Any], answer: str
) -> None:
    _out, verified = await _run(prompt, args, answer)
    assert verified is not None
    assert verified.canonical_answer == answer


@pytest.mark.parametrize(
    ("user_texts", "args", "matched"),
    [
        # A follow-up that asks: its operation, the earlier question's formula.
        (
            ["now integrate it", "Find the derivative of y = x^3"],
            {"action": "integrate", "expr": "x**3"},
            True,
        ),
        (
            ["what are its critical numbers?", "Find the derivative of y = x^3 - 3x"],
            {"action": "diff", "expr": "x**3 - 3*x"},
            False,
        ),
        # A follow-up that names no operation: the question the call works on asks.
        (["why?", "Find the derivative of y = x^3"], {"action": "diff", "expr": "x**3"}, True),
        (
            ["show the steps", "Find the absolute maximum of f(x) = x^3 - 3x on [0, 2]"],
            {"action": "diff", "expr": "x**3 - 3*x"},
            False,
        ),
    ],
)
def test_the_newest_message_that_asks_decides(
    user_texts: list[str], args: dict[str, Any], matched: bool
) -> None:
    assert (MathTool().call_matches(json.dumps(args), user_texts) is not None) is matched


@pytest.mark.parametrize(
    ("args", "user", "matches"),
    [
        # SymPy reads f(3 + h) as f*(3 + h): the limit came back a checked "f".
        (
            {"action": "limit", "expr": "(f(3+h) - f(3))/h", "point": "0", "variable": "h"},
            _LIMIT,
            False,
        ),
        (
            {"action": "system", "equations": [["g*x", "2"], ["x + y", "5"]]},
            "Let g(x) = 2x. Solve g(x) = 2 and x + y = 5.",
            False,
        ),
        # The function's own formula is the user's.
        ({"action": "graph", "expr": "x**2 - x + 3"}, _LIMIT, True),
        (
            {"action": "limit", "expr": "(x**2 - 4)/(x - 2)", "point": "2"},
            "limit as x approaches 2 of (x^2-4)/(x-2)",
            True,
        ),
    ],
)
def test_a_call_that_applies_a_defined_function_is_not_the_users_maths(
    args: dict[str, Any], user: str, matches: bool
) -> None:
    assert tool_call_matches_user_text(json.dumps(args), [user]) is matches
