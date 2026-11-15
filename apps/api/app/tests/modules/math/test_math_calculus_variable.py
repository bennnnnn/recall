"""A derivative or an integral is worked with respect to a letter the expression holds.

Unnamed, the variable was the expression's one letter, else x. With a Greek letter read as a
variable, "Differentiate k sin θ" had two letters, so it was worked with respect to x, a letter
it does not hold: a checked 0, and "Integrate a cos θ" a checked a·x·cos θ + C (review,
2026-11-14). Before that, main read "k sin θ" in k (a checked sin θ) and "k sin t" in x (a
checked 0). Nothing says which letter is the variable there, so no card answers it; x among
several letters is still the variable, as it always was (``k sin x``). An expression
"y = f(x, y)" names y on both sides, so its dy/dx is implicit, never f's with y held still.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.math import solve as math_solve
from app.modules.math.tools.extractors.calculus_variable import implied_variable
from app.services.subjects.dispatch import build_subject_augmentation


async def _verified(text: str) -> str | None:
    """The turn's checked answer, with no model call."""
    settings = Settings(math_llm_extract_enabled=False, math_word_problems_enabled=False)
    verified = (await build_subject_augmentation(text, settings)).verified
    return getattr(verified, "canonical_answer", None) if verified is not None else None


@pytest.mark.parametrize(
    ("expr", "variable"),
    [
        ("k*sin(x)", "x"),
        ("a*x**3 + b*x**2 + c*x + d", "x"),
        ("x*sin(θ)", "x"),
        ("θ**2", "θ"),
        ("3*t**2 + 2*t", "t"),
        ("5", "x"),
        ("k*sin(θ)", None),
        ("r**2*θ", None),
        ("k*sin(t)", None),
        ("a*t**2 + b*t", None),
        ("exp(k*t)", None),
    ],
)
def test_the_implied_variable_is_one_letter_or_x(expr: str, variable: str | None) -> None:
    assert implied_variable(expr) == variable


@pytest.mark.parametrize(
    ("expr", "variable"),
    [("k*sin(t)", "x"), ("x**2", "t"), ("a", "x"), ("r**2*θ", "x")],
)
def test_the_solver_refuses_a_variable_the_expression_lacks(expr: str, variable: str) -> None:
    with pytest.raises(math_solve.SolveServiceError):
        math_solve.differentiate_expression(expr, variable)
    with pytest.raises(math_solve.SolveServiceError):
        math_solve.integrate_expression(expr, variable)
    with pytest.raises(math_solve.SolveServiceError):
        math_solve.integrate_definite(expr, variable, "0", "1")


def test_a_number_alone_is_still_worked_in_x() -> None:
    assert math_solve.integrate_expression("5", "x").latex == "5 x"
    assert math_solve.differentiate_expression("7", "x").latex == "0"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        # The review's seven: with respect to x, each was a checked 0 or a product with x.
        "Differentiate k sin θ",
        "Differentiate a cos φ",
        "Differentiate mθ²",
        "Differentiate θ² + c",
        "Differentiate r²θ",
        "Integrate a cos θ",
        "Integrate r²θ",
        # The same with Latin letters, checked 0 or "k t x + C" on main.
        "Differentiate k sin t",
        "Differentiate a t² + b t",
        "Integrate k t",
        "Differentiate e^(kt)",
        "Differentiate A sin(ωt)",
        "Differentiate t^n",
        # A named variable the expression lacks: implicit, or a letter held constant?
        "Differentiate x² with respect to t",
        "Integrate k dx",
        "∫ x² dθ",
        # At a point, another letter left "undefined" for 2k, and with respect to x a 0.
        "Find the derivative of a t^2 at t = 1",
        "Find the derivative of k x^2 at x = 1",
    ],
)
async def test_an_open_or_absent_variable_gets_no_card(question: str) -> None:
    assert await _verified(question) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("Integrate a cos θ dθ", r"a \sin{\left(θ \right)} + C"),
        ("Differentiate k sin θ with respect to θ", r"k \cos{\left(θ \right)}"),
        ("Differentiate k sin x", r"k \cos{\left(x \right)}"),
        ("Differentiate mx²", "2 m x"),
        ("Integrate r²x", r"\frac{r^{2} x^{2}}{2} + C"),
        ("Differentiate a x^3 + b x^2 + c x + d", r"3 a x^{2} + 2 b x + c"),
        ("Differentiate x sin θ", r"\sin{\left(θ \right)}"),
        ("Differentiate θ²", "2 θ"),
        ("Differentiate sin θ", r"\cos{\left(θ \right)}"),
        ("Find the derivative of 3t^2 + 2t", "6 t + 2"),
        ("Integrate 5 dx", "5 x + C"),
        ("Differentiate 7", "0"),
    ],
)
async def test_a_variable_the_expression_holds_is_still_worked(question: str, answer: str) -> None:
    assert await _verified(question) == answer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "answer"),
    [
        # Held still, y made each of these the explicit derivative: x^(y-1)·y, 3x²ʸ, y cos(xy).
        ("Find dy/dx if y = x^y", r"- \frac{x^{y - 1} y}{x^{y} \ln{\left(x \right)} - 1}"),
        (
            "Find dy/dx if y = x³ʸ",
            r"- \frac{3 x^{3 y - 1} y}{3 x^{3 y} \ln{\left(x \right)} - 1}",
        ),
        (
            "Find dy/dx if y = sin(xy)",
            r"- \frac{y \cos{\left(x y \right)}}{x \cos{\left(x y \right)} - 1}",
        ),
        ("Find dy/dx for y = x y + 1", r"- \frac{y}{x - 1}"),
        ("Differentiate y = x^y", r"- \frac{x^{y - 1} y}{x^{y} \ln{\left(x \right)} - 1}"),
        (
            "Find the derivative of y = x sin y",
            r"- \frac{\sin{\left(y \right)}}{x \cos{\left(y \right)} - 1}",
        ),
        # y on one side only is the explicit function it always was.
        ("Find dy/dx if y = x^2", "2 x"),
        ("Differentiate y = x^3 - 3x", r"3 x^{2} - 3"),
        ("Find dy/dx if x^2 + y^2 = 25", r"- \frac{x}{y}"),
    ],
)
async def test_y_on_both_sides_is_differentiated_implicitly(question: str, answer: str) -> None:
    assert await _verified(question) == answer


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        # No dy/dx: y cancels (idiff divided by 0, a checked zoo·x), or y is all there is.
        "Find dy/dx if y = x^2 + y",
        "Differentiate y = e^y",
        # The implicit solver works a first dy/dx only.
        "Find the second derivative of y = x^y",
        "Integrate y = x^y",
    ],
)
async def test_an_implicit_definition_it_cannot_work_gets_no_card(question: str) -> None:
    assert await _verified(question) is None
