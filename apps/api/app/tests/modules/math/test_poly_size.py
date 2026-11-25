"""A polynomial's size read off its tree: the degree guard and expand/factor never expand a
huge polynomial just to refuse it (audit 2026-11-25: 1.6 s to expand (x+1)^3000)."""

from __future__ import annotations

import pytest
from sympy import Expr, Symbol, sympify

from app.modules.math.schemas import EquationInput
from app.modules.math.solve.equations import solve_equation
from app.modules.math.solve.expressions import expand_expression, factor_expression
from app.modules.math.solve.poly_size import degree_bound, expanded_terms, total_degree_bound
from app.services.solving import SolveServiceError

_X = Symbol("x")


@pytest.mark.parametrize(
    "expr, degree",
    [
        ("(x+1)**3000", 3000),
        ("x**2 - 5*x + 6", 2),
        ("(x+1)*(x-2)**3", 4),
        ("y**7 + 2", 0),
        ("sin(x) + x", None),
        ("1/x + 1", None),
        ("x**y", None),
    ],
)
def test_degree_bound_reads_the_tree(expr: str, degree: int | None) -> None:
    assert degree_bound(sympify(expr), _X) == degree


@pytest.mark.parametrize(
    "expr, terms",
    [("x + 1", 2), ("(x + 1)**2", 3), ("(a + b + c)**10", 66), ("(x + 1)*(y + 1)", 4)],
)
def test_expanded_terms_bounds_what_expand_writes(expr: str, terms: int) -> None:
    assert expanded_terms(sympify(expr)) == terms


def test_expanded_terms_of_a_huge_power_stops_at_its_cap() -> None:
    assert expanded_terms(sympify("(a + b + c + d + e)**3000")) >= 10**6
    assert total_degree_bound(sympify("(x + y)**40 - 1")) == 80


def test_the_degree_guard_refuses_a_huge_power_without_expanding_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def expanded(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("the guard expanded the polynomial")

    monkeypatch.setattr(Expr, "as_poly", expanded)
    with pytest.raises(SolveServiceError, match="degree too high"):
        solve_equation(EquationInput(lhs="(x+1)**3000", rhs="0", variables=["x"]))


def test_the_degree_guard_still_reads_a_cancelled_degree() -> None:
    """Above the cap as written, small enough to expand: the true degree decides."""
    result = solve_equation(EquationInput(lhs="(x+1)**9 - (x+1)**9 + x", rhs="0", variables=["x"]))
    assert result.solutions_latex == ["x = 0"]


def test_expand_refuses_an_expansion_too_large_to_write() -> None:
    with pytest.raises(SolveServiceError, match="too large"):
        expand_expression("(x+1)**3000")
    assert expand_expression("(x+1)**2").result == "x**2 + 2*x + 1"


def test_factor_refuses_a_sum_of_too_high_a_degree() -> None:
    with pytest.raises(SolveServiceError, match="too large"):
        factor_expression("(x+1)**300 - 1")
    # A power of a small sum factors its base alone, at once.
    assert factor_expression("(x+1)**3000").result == "(x + 1)**3000"
    assert factor_expression("x**2 - 5*x + 6").result == "(x - 3)*(x - 2)"
