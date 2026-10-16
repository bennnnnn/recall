"""The phone resamples a verified plot to the y values SymPy gives.

`docs/fixtures/graph_expr_cases.json` holds plot expressions as the graph fence
carries them, with sample x values and the expected y. This test recomputes each
y with SymPy through the server's own reading of the expression
(`_parse_expression`, the parse `sample_function` plots), so the fixture cannot
drift from the server. The phone test (`lib/__tests__/graphExpr.test.ts`)
evaluates the same cases with `lib/math/graphExpr.ts` and must agree within 1e-9.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pytest
from sympy import N, Rational, Symbol

from app.modules.math.solve import MathServiceError, _parse_expression

FIXTURE = Path(__file__).resolve().parents[6] / "docs" / "fixtures" / "graph_expr_cases.json"
CONTRACT: dict[str, Any] = json.loads(FIXTURE.read_text())
VARIABLE: str = CONTRACT["variable"]
# Working precision for each y, well past a double's 17 digits.
_DIGITS = 30


def _id(case: dict[str, Any]) -> str:
    return repr(case["expr"])


def _sympy_y(parsed: Any, x: float) -> float | None:
    """y at an exact x, or None where there is no real, finite value (domain edge or pole)."""
    value = N(parsed.subs(Symbol(VARIABLE), Rational(str(x))), _DIGITS)
    if value.is_real and value.is_finite:
        return float(value)
    return None


@pytest.mark.parametrize("case", CONTRACT["cases"], ids=_id)
def test_graph_expr_contract_matches_sympy(case: dict[str, Any]) -> None:
    if case.get("refused"):
        with pytest.raises(MathServiceError):
            _parse_expression(case["expr"], [VARIABLE])
        return
    parsed = _parse_expression(case["expr"], [VARIABLE])
    assert len(case["y"]) == len(case["x"])
    for x, expected in zip(case["x"], case["y"], strict=True):
        actual = _sympy_y(parsed, x)
        if expected is None:
            assert actual is None, f"x={x}: SymPy gives {actual}, fixture has no value"
        else:
            assert actual is not None, f"x={x}: SymPy gives no real value, fixture has {expected}"
            assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12), f"x={x}"
