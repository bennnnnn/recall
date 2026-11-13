"""A function the maths readers do not model is never dropped and never certified.

"solve floor(x) = 3" was read as (x) = 3 and certified x = 3 (the answer is 3 <= x < 4), and
"solve sign(sin(x)) = 1 for 0 <= x <= 2pi" as sin(x) = 1, certified x = pi/2 (it is
0 < x < pi). Two guards hold the class: a reading that lost a written function is no reading
(``function_calls.py``, checked in ``extract_math_intent`` and the request audit), and an
equation or inequality that applies a step, remainder, lattice or other unmodelled function to
its unknown declines the solve (``solve/solved_functions.py``).
"""

from __future__ import annotations

import pytest
import sympy

from app.modules.math.function_calls import _spelling, unread_functions, written_functions
from app.modules.math.function_names import MATH_FUNCTION_NAMES
from app.modules.math.function_table import (
    FUNCTIONS,
    REQUEST_WORDS,
    SOLVED_SYMPY,
    UNSOLVED_WRITTEN,
    WRITTEN,
)
from app.modules.math.request_consumption import audit_math_request
from app.modules.math.schemas import EquationInput, MathIntent, SystemOfEquationsInput
from app.modules.math.solve.equations import solve_equation
from app.modules.math.solve.inequalities import solve_compound_inequality, solve_inequality
from app.modules.math.solve.solved_functions import unsolved_function
from app.modules.math.solve.systems import solve_system
from app.modules.math.tools.extract import extract_math_intent
from app.services.solving import SolveServiceError


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("solve floor(x) = 3", {"floor": 1}),
        ("solve sign(sin(x)) = 1", {"sign": 1, "sin": 1}),
        ("solve sgn(x) = 1", {"sign": 1}),
        ("solve ceil(x) + ceiling(2x) = 5", {"ceiling": 2}),
        ("solve foo(x) = 3", {"foo": 1}),
        ("solve x mod 3 = 1", {"mod": 1}),
        ("17 modulo 5", {"mod": 1}),
        ("solve the floor of x equals 3", {"floor": 1}),
        ("the greatest integer function of x", {"floor": 1}),
        ("solve \\lfloor x \\rfloor = 3", {"floor": 1}),
        ("solve ⌈x⌉ = 3", {"ceiling": 1}),
        ("solve \\operatorname{sgn}(x) = 1", {"sign": 1}),
        ("solve \\sin(x) = 1/2", {"sin": 1}),
        ("solve arcsin(x) = 0.5", {"asin": 1}),
        ("evaluate ln(5) + log(2)", {"log": 2}),
        ("solve 2xsin(x) = 0", {"sin": 1}),
        # A name before a bar, the bars themselves, a remainder sign and a Greek function.
        ("solve ln|x| = 2", {"log": 1, "abs": 1}),
        ("solve sqrt|x| = 3", {"sqrt": 1, "abs": 1}),
        ("solve x|x| = 4", {"abs": 1}),
        ("solve \\left|2x - 1\\right| = 5", {"abs": 1}),
        ("solve |x + 1| + |x - 1| = 4", {"abs": 2}),
        ("solve x % 3 = 1", {"mod": 1}),
        ("solve 3^x%5 = 1", {"mod": 1}),
        ("what is 17 % 5", {"mod": 1}),
        ("solve Γ(x) = 6", {"gamma": 1}),
        ("solve ζ(x) = 2", {"zeta": 1}),
        ("solve φ(n) = 4", {"φ": 1}),
        ("solve 2x ≡ 3 mod 5", {"mod": 1, "congruence": 1}),
        ("solve cbrt(x) = 2", {"cbrt": 1}),
        # Notation, products, request verbs, LaTeX brackets and prose are not functions.
        ("f(x) = 2x + 3", {}),
        ("solve ab(x+1) = 4", {}),
        ("Solve(2x + 1 = 5)", {}),
        ("factor(x^2 - 1)", {}),
        ("solve \\left(x + 1\\right) = 3", {}),
        ("what is the sign (positive or negative) of -3 * 4", {}),
        ("round 3.456 to two decimal places", {}),
        ("the floor area of a room is 12 by 15", {}),
        ("find the max of y = -x^2 + 4x", {}),
        ("what is 15% of 80", {}),
        ("solve 20% of x = 15", {}),
        ("the area is π(r + 1)", {}),
        ("is 17 ≡ 2 mod 5", {"mod": 1}),
        # A call written after a word is one mod, not a call and a remainder (review of #2322).
        ("evaluate mod(17,5)", {"mod": 1}),
        ("find x if x mod(4) = 1", {"mod": 1}),
        # A plural marker is no call (review of #2322).
        ("Find the root(s) of x^2 - 5x + 6 = 0", {}),
        ("what are the sum(s) of the digits", {}),
        ("list the design(s) and their box(es)", {}),
        # A percentage is no remainder (review of #2322).
        ("what is 20% (one fifth) of 80", {}),
        ("it grows 5% a year", {}),
        ("x % (y + 1)", {"mod": 1}),
        ("x % y", {"mod": 1}),
        ("5% x 20", {}),
        ("17%5", {"mod": 1}),
    ],
)
def test_written_functions_names_each_applied_function(text: str, expected: dict[str, int]) -> None:
    assert dict(written_functions(text)) == expected


@pytest.mark.parametrize(
    ("text", "reading", "unread"),
    [
        ("solve floor(x) = 3", ["(x)", "3"], ("floor",)),
        ("solve sign(sin(x)) = 1", ["(sin(x))", "1"], ("sign",)),
        ("solve sin(x) + sin(2x) = 1", ["sin(x)", "1"], ("sin",)),
        ("solve arcsin(x) = 0.5", ["asin (x)", "0.5"], ()),
        ("solve arcsin(x) = 0.5", ["arcsin(x)", "0.5"], ()),
        # A whole word: sin is not inside arcsin.
        ("solve sin(x) = 0.5", ["arcsin(x)", "0.5"], ("sin",)),
        ("solve ln|x| = 2", ["(x)", "2"], ("abs", "log")),
        ("solve ln|x| = 2", ["ln(Abs(x))", "2"], ()),
        ("solve x % 3 = 1", ["3", "1"], ("mod",)),
        ("solve Γ(x) = 6", ["gamma(x)", "6"], ()),
        ("solve φ(n) = 4", ["phi*(n)", "4"], ("φ",)),
        ("evaluate exp(2)", ["e^2"], ()),
        ("solve |x| = 3", ["Abs(x)", "3"], ()),
        ("solve abs(x - 3) = 5", ["Abs(x - 3)", "5"], ()),
        ("gcd(12, 18)", ["gcd"], ()),
        ("17 mod 5", ["mod"], ()),
        ("integrate ln(x) dx", ["log(x)"], ()),
    ],
)
def test_unread_functions_finds_what_a_reading_lost(
    text: str, reading: list[str], unread: tuple[str, ...]
) -> None:
    assert unread_functions(text, reading) == unread


def test_unread_functions_spelling_cache_is_bounded() -> None:
    """Any word written before "(" is a name to spell, so its cache must not grow with them."""
    for number in range(1_000):
        made_up = "blorp" + "".join("bhjkuvwxyz"[int(digit)] for digit in str(number))
        assert unread_functions(f"solve {made_up}(x) = 3", ["x = 3"]) == (made_up,)
    info = _spelling.cache_info()
    assert info.maxsize is not None
    assert info.currsize <= info.maxsize


@pytest.mark.parametrize(
    "text",
    [
        "solve floor(x) = 3",
        "solve sign(sin(x)) = 1 for 0 <= x <= 2pi",
        "solve ceiling(x) = 3",
        "solve ceil(x)=2",
        "solve round(x) = 3",
        "solve frac(x) = 0.5",
        "solve sgn(x) = 1",
        "solve sign(x) = 1",
        "solve foo(x) = 3",
        "solve heaviside(x) = 1",
        "solve floor(x) + x = 5",
        "solve x + floor(x) = 7",
        "solve floor(2x - 1) = 4",
        "solve floor(x) < 3",
        "solve sign(x) > 0",
        "solve the floor of x equals 3",
        "solve \\lfloor x \\rfloor = 3",
        "solve ⌊x⌋ = 3",
        "solve \\operatorname{sgn}(x) = 1",
        "solve floor(x) = 3 and x + y = 5",
        "solve x + y = 5, floor(x) = y",
        "solve factorial(x) = 24",
        "floor(x) = 3",
        "solve ln|x| = 2",
        "solve log|x| = 1",
        "solve sqrt|x| = 3",
        "solve sin|x| = 0.5",
        "solve tan|x| = 1",
        "solve x|x| = 4",
        "solve x % 3 = 1",
        "solve x%3 = 1",
        "solve 3^x % 5 = 1",
        "solve Γ(x) = 6",
        "solve Γ(x+1) = 24",
        "solve gamma(x) = 6",
        "solve ζ(x) = 2",
        "solve φ(n) = 4",
        "solve erf(x) = 0.5",
        "solve 2x ≡ 3 mod 5",
        "solve x ≡ 2 (mod 3)",
        "solve trunc(x) = 2",
        "simplify floor(x) + x",
        "evaluate sign(-3)",
    ],
)
def test_extract_declines_a_reading_that_dropped_a_function(text: str) -> None:
    assert extract_math_intent(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "solve abs(x - 3) = 5",
        "solve |x - 3| = 5",
        "solve abs(x) < 3",
        "solve sin(x) = 1/2",
        "solve 2cos(x) - 1 = 0 for 0 <= x <= 2pi",
        "solve tan(x) = 1",
        "solve log(x) = 2",
        "solve ln(x) = 2",
        "solve exp(x) = 5",
        "solve sqrt(x + 1) = 3",
        "solve arcsin(x) = 0.5",
        "solve cosh(x) = 1",
        "evaluate sqrt(16)",
        "evaluate log(100)",
        "evaluate sin(pi/6)",
        "evaluate arctan(1)",
        "evaluate floor(3.7)",
        "evaluate ceiling(2.1)",
        "evaluate 5!",
        "evaluate 5C2",
        "gcd(12, 18)",
        "lcm(4, 6)",
        "17 mod 5",
        "derivative of sin(x)",
        "d/dx(x^2)",
        "integrate ln(x) dx",
        "limit of sin(x)/x as x->0",
        "solve 2x + 3 = 7",
        "what is 15% of 80",
        "evaluate 2^10 mod 7",
        "solve \\left|2x - 1\\right| = 5",
        "solve |x + 1| + |x - 1| = 4",
        "solve cbrt(x) = 2",
        "solve cbrt(x - 1) = 3",
    ],
)
def test_extract_keeps_modelled_functions(text: str) -> None:
    assert extract_math_intent(text) is not None


def test_audit_refuses_a_model_reading_that_dropped_a_function() -> None:
    """A model's reading is audited against the message as the regex readers' are."""
    dropped = MathIntent(kind="equation", lhs="x", rhs="3", operation="solve")
    kept = MathIntent(kind="equation", lhs="x + 1", rhs="3", operation="solve")
    assert "unconsumed function" in audit_math_request("solve floor(x) = 3", dropped).leftovers
    assert audit_math_request("solve x + 1 = 3", kept).complete


@pytest.mark.parametrize(
    ("lhs", "rhs"),
    [
        ("floor(x)", "3"),
        ("ceiling(x)", "3"),
        ("ceil(x)", "3"),
        ("sign(x)", "1"),
        ("frac(x)", "0.5"),
        ("Mod(x, 3)", "1"),
        ("x mod 3", "1"),
        ("Max(x, 2)", "5"),
        ("Min(x, 1)", "0"),
        ("gcd(x, 6)", "3"),
        ("lcm(x, 4)", "12"),
        ("Heaviside(x)", "1"),
        ("factorial(x)", "24"),
        ("binomial(x, 2)", "10"),
        ("Piecewise((x, x > 0), (0, True))", "2"),
        ("re(x)", "2"),
        ("arg(x)", "1"),
        ("floor(x) + x", "5"),
        ("\\lfloor x \\rfloor", "3"),
    ],
)
def test_solve_equation_declines_an_unmodelled_function(lhs: str, rhs: str) -> None:
    with pytest.raises(SolveServiceError):
        solve_equation(EquationInput(lhs=lhs, rhs=rhs, variables=["x"]))


def test_a_maths_word_is_never_split_into_letters() -> None:
    """The reading of "solve x mod 3 = 1" was mod 3 = 1 in d, solved as 3·m·o·d = 1."""
    with pytest.raises(SolveServiceError):
        solve_equation(EquationInput(lhs="mod 3", rhs="1", variables=["d"]))


def test_an_unknown_named_like_a_function_is_solved() -> None:
    """``gamma`` declared as the unknown is a symbol, not Γ (review of #2322)."""
    result = solve_equation(EquationInput(lhs="2*gamma + 1", rhs="7", variables=["gamma"]))
    assert result.solutions_latex == [r"\gamma = 3"]


@pytest.mark.parametrize(
    ("lhs", "rhs", "solutions"),
    [
        ("abs(x - 3)", "5", ["x = -2", "x = 8"]),
        ("Abs(x)", "3", ["x = -3", "x = 3"]),
        ("sqrt(x + 1)", "3", ["x = 8"]),
        ("log(x)", "2", ["x = 100"]),
        ("exp(x)", "1", ["x = 0"]),
        ("2x + 3", "7", ["x = 2"]),
        # A function of numbers alone is a number: the unknown is outside it.
        ("x + floor(2.5)", "5", ["x = 3"]),
        # A cube root is a power the solvers work, a negative value included.
        ("cbrt(x)", "2", ["x = 8"]),
        ("cbrt(x - 1)", "3", ["x = 28"]),
        ("cbrt(x)", "-2", ["x = -8"]),
    ],
)
def test_solve_equation_keeps_modelled_functions(lhs: str, rhs: str, solutions: list[str]) -> None:
    result = solve_equation(EquationInput(lhs=lhs, rhs=rhs, variables=["x"]))
    assert result.solutions_latex == solutions


@pytest.mark.parametrize(
    ("lhs", "rhs", "comparator"),
    [
        ("floor(x)", "3", "<"),
        ("sign(x)", "0", ">"),
        ("Mod(x, 3)", "1", "<"),
        ("Max(x, 2)", "5", "<"),
        ("ceiling(x)", "2", ">="),
    ],
)
def test_solve_inequality_declines_an_unmodelled_function(
    lhs: str, rhs: str, comparator: str
) -> None:
    with pytest.raises(SolveServiceError):
        solve_inequality(lhs, rhs, "x", comparator)


def test_solve_inequality_keeps_absolute_value() -> None:
    assert solve_inequality("abs(x)", "3", "x", "<").solutions_latex == ["-3 < x < 3"]


def test_compound_inequality_declines_an_unmodelled_function() -> None:
    with pytest.raises(SolveServiceError):
        solve_compound_inequality("0", "<", "floor(x)", "<", "3", "x")


def test_system_declines_an_unmodelled_function() -> None:
    with pytest.raises(SolveServiceError):
        solve_system(
            SystemOfEquationsInput(
                equations=[("x + y", "5"), ("floor(x)", "y")], variables=["x", "y"]
            )
        )


@pytest.mark.parametrize(
    ("side", "unknown", "unsolved"),
    [
        ("floor(x) + 1", "x", True),
        ("2floor(x)", "x", True),
        ("gcd(x, 6)", "x", True),
        ("binomial(x, 2)", "x", True),
        ("erf(x)", "x", True),
        # A subscript is part of a quantity's name, and a function of numbers is a number.
        ("x_min + 2", "x_min", False),
        ("3t + v_max", "t", False),
        ("x_re - 1", "x_re", False),
        ("x + floor(2.5)", "x", False),
        # An unknown spelled like a function is the variable (review of #2322).
        ("2*gamma + 1", "gamma", False),
        ("mean - 3", "mean", False),
        ("gamma(x) + 1", "x", True),
    ],
)
def test_unsolved_function_reads_names_not_subscripts(
    side: str, unknown: str, unsolved: bool
) -> None:
    assert unsolved_function((side,), (), [unknown]) is unsolved


def test_function_table_is_one_source() -> None:
    """The reader, the parser's gates and the solver read one table of names."""
    assert MATH_FUNCTION_NAMES <= set(WRITTEN)
    assert not REQUEST_WORDS & set(WRITTEN)
    assert all(callable(getattr(sympy, name)) for name in SOLVED_SYMPY)
    assert {"choose", "comb", "binom", "perm", "gamma", "erf"} <= {
        name.lower() for name in UNSOLVED_WRITTEN
    }
    names = [function.name for function in FUNCTIONS]
    assert len(names) == len(set(names))
