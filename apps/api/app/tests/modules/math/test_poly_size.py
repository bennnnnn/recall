"""A polynomial's size read off its tree: the degree guard and expand/factor never expand a
huge polynomial just to refuse it (audit 2026-11-25: 1.6 s to expand (x+1)^3000)."""

from __future__ import annotations

import pytest
from sympy import Expr, Symbol, sympify

from app.modules.math.schemas import EquationInput
from app.modules.math.solve.equations import _reject_high_degree, solve_equation
from app.modules.math.solve.expressions import expand_expression, factor_expression
from app.modules.math.solve.poly_size import (
    degree_bound,
    expanded_terms,
    expansion_size,
    size_degree,
)
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


@pytest.mark.parametrize(
    "expr, degree",
    [
        ("(x + y)**40 - 1", 40),
        ("1/(x + 1)**300 - 1", 300),
        ("(x + 1)**(3001/2)", 1500),
        ("sin(x) + 1", None),
    ],
)
def test_size_degree_counts_every_power_by_its_size(expr: str, degree: int | None) -> None:
    assert size_degree(sympify(expr)) == degree


def test_expansion_size_is_no_more_than_a_polynomial_of_its_degree_has() -> None:
    """2^10 products, 11 terms: a product of ten linear factors expands."""
    product = sympify("*".join(f"(x + {k})" for k in range(1, 11)))
    assert expanded_terms(product) == 1024
    assert expansion_size(product) == 11
    assert expansion_size(sympify("(x + 1)**(-9999)")) == 10000


def test_the_degree_guard_refuses_a_huge_power_without_expanding_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def expanded(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("the guard expanded the polynomial")

    monkeypatch.setattr(Expr, "as_poly", expanded)
    with pytest.raises(SolveServiceError, match="degree too high"):
        solve_equation(EquationInput(lhs="(x+1)**3000", rhs="0", variables=["x"]))


def test_the_degree_guard_still_reads_a_cancelled_degree() -> None:
    """Degree 9 as written, 8 once expanded: small enough to expand, the true degree decides."""
    _reject_high_degree(sympify("(x+1)**9 - x**9"), sympify("0"), ["x"])
    with pytest.raises(SolveServiceError, match="degree too high"):
        _reject_high_degree(sympify("(x+1)**9 + x**9"), sympify("0"), ["x"])


def test_expand_refuses_an_expansion_too_large_to_write() -> None:
    with pytest.raises(SolveServiceError, match="too large"):
        expand_expression("(x+1)**3000")
    with pytest.raises(SolveServiceError, match="too large"):
        expand_expression("(x+1)**(-9999)")
    assert expand_expression("(x+1)**2").result == "x**2 + 2*x + 1"
    ten = "*".join(f"(x+{k})" for k in range(1, 11))
    assert expand_expression(ten).result.startswith("x**10 + 55*x**9")


def test_factor_refuses_a_sum_of_too_high_a_degree() -> None:
    with pytest.raises(SolveServiceError, match="too large"):
        factor_expression("(x+1)**300 - 1")
    with pytest.raises(SolveServiceError, match="too large"):
        factor_expression("1/(x+1)**300 - 1")
    # A power of a small sum factors its base alone, at once.
    assert factor_expression("(x+1)**3000").result == "(x + 1)**3000"
    assert factor_expression("x**2 - 5*x + 6").result == "(x - 3)*(x - 2)"
