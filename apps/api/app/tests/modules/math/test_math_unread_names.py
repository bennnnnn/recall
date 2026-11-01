"""A card that restates the question is no answer (2026-11-01 live baseline).

"Find the cube root of 27a^3 + 54a^2b + 36ab^2 + 8b^3." went to the model reader, which wrote
``cube_root(27a^3 + …)``. The parser read ``cube_root`` as one symbol times the polynomial,
"simplified" that to itself, and the checked card was the question (right: 3a + 2b). A name
the parser does not know as a function or as one-letter variables declines, and a card that
is the question's expression, as a fraction or under a root, is no answer.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.gateways import litellm_gateway
from app.modules.chat.tool_verified import with_tool_verified
from app.modules.chat.whole_question import answers_the_question
from app.modules.math import solve as math_solve
from app.modules.math.tools import prompt as math_prompt
from app.modules.math.tools.llm_extract import LLMMathExtract
from app.services.solving import SolveServiceError, VerifiedSolveBlock

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
        "cube*2",
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
        "3abc(2a - b + c)",
        "xyz(x + y + z)",
        "2abcd + 3abcd",
        "12pqrs/(4pq)",
        "lwh",
        "nRT",
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


@pytest.mark.parametrize(
    "answer",
    [
        # The model's power of the whole expression, printed as a root.
        r"\sqrt[3]{27 a^{3} + 54 a^{2} b + 36 a b^{2} + 8 b^{3}}",
        "27 a^{3} + 54 a^{2} b + 36 a b^{2} + 8 b^{3}",
    ],
)
def test_a_card_that_restates_the_question_is_no_answer(answer: str) -> None:
    assert not answers_the_question(f"Find the cube root of {_CUBE}.", answer)


@pytest.mark.parametrize(
    ("question", "answer", "kept"),
    [
        ("simplify (x+1)/(x-1)", r"\frac{x + 1}{x - 1}", False),
        ("simplify 1/(x-1)", r"\frac{1}{x - 1}", False),
        # A fraction is matched whole, never across the question's terms.
        ("simplify (x+1)/(x-1) - x/(x-1)", r"\frac{1}{x - 1}", True),
        ("simplify sqrt(x^2+1)", r"\sqrt{x^{2} + 1}", False),
        # A rewrite a student asked for keeps its card.
        ("Simplify x^-2", r"\frac{1}{x^{2}}", True),
        ("Simplify 5^-2", r"\frac{1}{25}", True),
        ("Simplify -(-x)", "x", True),
        ("Simplify x + -2", "x - 2", True),
        ("simplify (x^2-1)/(x-1)", "x + 1", True),
        ("find the derivative of sqrt(x^2+1)", r"\frac{x}{\sqrt{x^{2} + 1}}", True),
        (f"Find the cube root of {_CUBE}.", "3 a + 2 b", True),
    ],
)
def test_a_card_is_kept_only_when_it_says_something_new(
    question: str, answer: str, kept: bool
) -> None:
    assert answers_the_question(question, answer) is kept


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


def test_the_tools_root_of_the_question_is_held_to_it() -> None:
    """The model's sympy call on the whole polynomial to the 1/3 is held to the question as
    the server's own card is (``tool_verified``): its root of the question goes."""
    tool = VerifiedSolveBlock(
        text="tool",
        subject="math",
        canonical_answer=r"\sqrt[3]{27 a^{3} + 54 a^{2} b + 36 a b^{2} + 8 b^{3}}",
    )
    assert with_tool_verified(None, tool, f"Find the cube root of {_CUBE}.") is None
