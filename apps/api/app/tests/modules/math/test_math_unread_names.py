"""A card that restates the question is no answer (2026-11-01 live baseline).

"Find the cube root of 27a^3 + 54a^2b + 36ab^2 + 8b^3." went to the model reader, which wrote
``cube_root(27a^3 + …)``. The parser read ``cube_root`` as one symbol times the polynomial,
"simplified" that to itself, and the checked card was the question (right: 3a + 2b). A name
the parser does not know as a function or as one-letter variables declines, and so does a
simplification, factorisation or expansion that leaves the expression as written.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.modules.math import solve as math_solve
from app.modules.math.schemas import MathIntent
from app.modules.math.tool import SympyAdapter
from app.modules.math.tools import prompt as math_prompt
from app.modules.math.tools.block import _build_verified_block
from app.modules.math.tools.llm_extract import LLMMathExtract
from app.services.solving import SolveServiceError

_CUBE = "27a^3 + 54a^2b + 36ab^2 + 8b^3"


@pytest.mark.parametrize(
    "expr",
    [
        f"cube_root({_CUBE})",
        "cuberoot(8)",
        "nthroot(8, 3)",
        "foo(x)",
        "fog(x)",
        "speed + 2",
        "velocity*3",
        "area*2",
        "xx + 1",
    ],
)
def test_a_name_the_parser_does_not_know_declines(expr: str) -> None:
    with pytest.raises(SolveServiceError):
        math_solve.parse_expression(expr)


@pytest.mark.parametrize(
    "expr",
    [
        _CUBE,
        "a^3 + b^3 + c^3 - 3abc",
        "2xy + 3xz",
        "ab(a+b)",
        "sinx + cosx",
        "log2(8)",
        "theta + 1",
        "x_1 + x_2",
        "factorial(5)",
        "binomial(5, 2)",
        "sqrt(x) + exp(x) + Abs(x)",
        "cbrt(27) + root(8, 3)",
        "max(1, 2)",
        "pi*r^2",
        "oo",
        "2e5 + x",
    ],
)
def test_functions_constants_and_letters_written_together_still_parse(expr: str) -> None:
    math_solve.parse_expression(expr)


def _card(operation: str, expr: str) -> str | None:
    intent = MathIntent(kind="calculus", operation=operation, expr=expr, variable="x")
    block = _build_verified_block(intent, Settings())
    return None if block is None else block.canonical_answer


@pytest.mark.parametrize(
    ("operation", "expr"),
    [
        ("simplify", f"cube_root({_CUBE})"),
        ("simplify", _CUBE),
        ("simplify", "(x+1)/(x-1)"),
        ("simplify", "x - 1"),
        ("factor", "x^2 + 1"),
        ("factor", "x^2 - 2x + 3"),
        ("expand", "x^2 + 1"),
    ],
)
def test_a_result_that_is_the_expression_as_written_has_no_card(operation: str, expr: str) -> None:
    assert _card(operation, expr) is None


@pytest.mark.parametrize(
    ("operation", "expr", "answer"),
    [
        ("factor", _CUBE, r"\left(3 a + 2 b\right)^{3}"),
        ("simplify", "(x^2 - 1)/(x - 1)", "x + 1"),
        ("simplify", "2x + 3x", "5 x"),
        ("simplify", "x*x", "x^{2}"),
        ("simplify", "2/4", r"\frac{1}{2}"),
        ("expand", "2(x+3)", "2 x + 6"),
        ("expand", "(x+1)^2", "x^{2} + 2 x + 1"),
    ],
)
def test_a_result_that_changes_the_expression_keeps_its_card(
    operation: str, expr: str, answer: str
) -> None:
    assert _card(operation, expr) == answer


@pytest.mark.asyncio
async def test_the_model_readers_cube_root_gets_no_card(monkeypatch: pytest.MonkeyPatch) -> None:
    """The live turn: the regex readers miss, the model reader writes ``cube_root(…)``."""
    monkeypatch.setattr(math_prompt, "extract_math_intent", lambda _text: None)

    async def reader(**_kwargs: object) -> LLMMathExtract:
        return LLMMathExtract(
            found=True, kind="calculus", operation="simplify", expr=f"cube_root({_CUBE})"
        )

    monkeypatch.setattr(litellm_gateway, "complete_structured", reader)
    settings = Settings(math_tools_enabled=True, math_llm_extract_enabled=True)
    _note, verified = await math_prompt.build_math_augmentation(
        f"Find the cube root of {_CUBE}.", settings, needs_math=True
    )
    assert verified is None


@pytest.mark.asyncio
async def test_the_sympy_tool_certifies_no_restated_expression() -> None:
    """The model's own simplify call on the polynomial would repeat it as a checked card."""
    adapter = SympyAdapter(Settings())
    result = await adapter._action_expr_op({"action": "simplify", "expr": "27*a^3 + 8*b^3"})
    assert result.data is None or not result.data.get("canonical_answer")
    assert "Do NOT claim" in result.content
    changed = await adapter._action_expr_op({"action": "simplify", "expr": "2*x + 3*x"})
    assert changed.data and changed.data.get("canonical_answer") == "5 x"
