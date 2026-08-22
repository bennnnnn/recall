"""Tests for math tools heuristics and prompt injection."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.models.math_schemas import MathIntent
from app.services import math_tools


def test_math_intent_has_no_dead_expression_kind() -> None:
    """Schema used to list kind=\"expression\" with no extractor or block
    builder — dead surface that invited half-implemented paths. Removed."""
    with pytest.raises(ValidationError):
        MathIntent.model_validate({"kind": "expression", "expr": "x+1"})


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Solve x^2 + 2 = 6", True),
        ("What's the weather?", False),
        ("A rectangle is 8×5 cm. Find the diagonal angle.", True),
        ("Graph y = x^2", True),
        ("Draw a rectangle", True),
    ],
)
def test_needs_symbolic_math(text: str, expected: bool) -> None:
    assert math_tools.needs_symbolic_math(text) is expected


def test_extract_equation_intent() -> None:
    intent = math_tools.extract_math_intent("Solve x^2 + 2 = 6")
    assert intent is not None
    assert intent.kind == "equation"
    assert intent.lhs == "x^2 + 2"
    assert intent.rhs == "6"
    assert intent.variable == "x"


@pytest.mark.parametrize(
    "text, expected_var",
    [
        ("Solve for y: x+y=5", "y"),
        ("solve for y in x+y=5", "y"),
        ("find y if x+y=5", "y"),
        ("find the value of y in 2y = 10", "y"),
        ("Solve for x: x+y=5", "x"),
    ],
)
def test_extract_equation_respects_solve_for_variable(text: str, expected_var: str) -> None:
    """BUG FIX: 'Solve for y: x+y=5' used to solve for x (alphabetical first
    of guess_variables) and return the wrong answer in the verified card. The
    extractor now parses the explicit 'solve for <var>' / 'find <var>' cue."""
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "equation"
    assert intent.variable == expected_var


def test_extract_equation_solve_for_unknown_variable_falls_back() -> None:
    """'solve for z' where z is not in the equation must not solve for z —
    fall back to the guessed variable rather than producing an empty solve."""
    intent = math_tools.extract_math_intent("Solve for z: x + 2 = 5")
    assert intent is not None
    assert intent.kind == "equation"
    assert intent.variable == "x"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2x+3=7", True),
        ("y=x^2", True),
        ("a+b=10", True),
        ("the meeting = 3pm", False),
        ("What's the weather?", False),
    ],
)
def test_needs_symbolic_math_bare_equation(text: str, expected: bool) -> None:
    """Bare algebraic equations (no 'solve'/'find' keyword) now trigger SymPy.
    Prose with an '=' but no standalone single-letter variable does not."""
    assert math_tools.needs_symbolic_math(text) is expected


def test_extract_bare_equation_intent() -> None:
    intent = math_tools.extract_math_intent("2x+3=7")
    assert intent is not None
    assert intent.kind == "equation"
    assert intent.lhs == "2x+3"
    assert intent.rhs == "7"
    assert intent.variable == "x"


@pytest.mark.parametrize(
    "text, expected_lhs",
    [
        ("roots of x^2 - 4", "x^2 - 4"),
        ("find the roots of x^3 - 1", "x^3 - 1"),
        ("zeros of x^2 - 9", "x^2 - 9"),
    ],
)
def test_extract_roots_of_rewrites_to_equation(text: str, expected_lhs: str) -> None:
    """'roots of <expr>' / 'zeros of <expr>' have no '=', so they used to
    fall through every extractor and ship unverified. They now rewrite to
    'solve <expr> = 0' and solve as a plain equation."""
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "equation"
    assert intent.lhs == expected_lhs
    assert intent.rhs == "0"


def test_extract_system_intent_for_multiple_equations() -> None:
    """BUG FIX (most severe correctness bug found in the audit): before this
    fix, a message with 2+ equations fell through to the single-equation
    branch, which only ever looked at the first clause."""
    intent = math_tools.extract_math_intent("solve x+y=5, x-y=1")
    assert intent is not None
    assert intent.kind == "system"
    assert intent.system_equations == [("x+y", "5"), ("x-y", "1")]
    assert intent.system_variables is not None
    assert set(intent.system_variables) >= {"x", "y"}


@pytest.mark.asyncio
async def test_augment_prompt_injects_system_solve_block() -> None:
    settings = Settings(math_tools_enabled=True)
    text = "solve x+y=5, x-y=1"
    out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert "Equation 1:" in verified.text
    assert "Equation 2:" in verified.text
    assert "x = 3" in verified.text
    assert "y = 2" in verified.text
    assert any("x = 3" in m["content"] for m in out if m["role"] == "system")


@pytest.mark.asyncio
async def test_build_math_augmentation_verifies_kinematics_trajectory() -> None:
    settings = Settings(math_tools_enabled=True)
    note, verified = await math_tools.build_math_augmentation(
        "A ball is dropped from 20m. How long until it hits the ground?",
        settings,
    )

    assert verified is not None
    assert note == verified.text
    assert verified.canonical_answer == "2.02 s"
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "trajectory"
    assert verified.canonical_fence["trajectory_type"] == "position_vs_time"
    assert verified.canonical_fence["x_label"] == "Time (s)"
    assert verified.canonical_fence["y_label"] == "Height (m)"
    points = verified.canonical_fence["points"]
    assert len(points) == 100
    assert points[0] == [0.0, 20.0]
    assert points[-1][1] == 0.0


@pytest.mark.asyncio
async def test_augment_prompt_no_intent_forbids_invented_geometry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.math_tools import prompt as math_prompt

    monkeypatch.setattr(math_prompt, "extract_math_intent", lambda _text: None)
    settings = Settings(math_tools_enabled=True)
    note, verified = await math_prompt.build_math_augmentation(
        "find the angle",
        settings,
        needs_math=True,
    )
    assert verified is None
    assert note is not None
    assert "invent" in note.lower()
    assert "```geometry" in note


@pytest.mark.asyncio
async def test_augment_prompt_system_flags_inconsistent_equations() -> None:
    settings = Settings(math_tools_enabled=True)
    text = "solve x+y=5, x+y=10"
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert "inconsistent" in verified.text.lower()


@pytest.mark.parametrize(
    "text, expected_expr, expected_var, expected_guess",
    [
        (
            "use newton's method to find the root of x^3 - 2x - 5 = 0 starting at x0 = 2",
            "x^3 - 2x - 5",
            "x",
            2.0,
        ),
        ("newton's method for x^2 - 2 = 0 with initial guess of 1", "x^2 - 2", "x", 1.0),
        ("numerically solve x = cos(x) starting near 1", "(x)-(cos(x))", "x", 1.0),
        ("find the root of x^3 - 2x - 5 = 0 near x=2", "x^3 - 2x - 5", "x", 2.0),
    ],
)
def test_extract_numerical_method_intent(
    text: str, expected_expr: str, expected_var: str, expected_guess: float
) -> None:
    assert math_tools.needs_symbolic_math(text) is True
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "numerical_method"
    assert intent.expr == expected_expr
    assert intent.variable == expected_var
    assert intent.newton_guess == expected_guess


def test_extract_numerical_method_intent_defaults_guess_when_absent() -> None:
    intent = math_tools.extract_math_intent("use newton's method on x^2 - 2 = 0")
    assert intent is not None
    assert intent.kind == "numerical_method"
    assert intent.newton_guess == 1.0


@pytest.mark.asyncio
async def test_augment_prompt_injects_newton_iteration_table() -> None:
    settings = Settings(math_tools_enabled=True)
    text = "use newton's method to find the root of x^3 - 2x - 5 = 0 starting at x0 = 2"
    out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert "n=0" in verified.text
    assert "Converged" in verified.text
    assert "2.0945514817" in verified.text or "2.094551482" in verified.text
    assert any("Converged" in m["content"] for m in out if m["role"] == "system")
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "answer"
    assert "```answer" in verified.text
    assert verified.canonical_fence["content"]


@pytest.mark.asyncio
async def test_augment_prompt_newton_reports_non_convergence() -> None:
    """BUG FIX target: a request that can't converge within the iteration
    budget must say so explicitly rather than silently omitting a root or
    (worse) presenting the last iterate as a verified answer."""
    settings = Settings(math_tools_enabled=True)
    text = "use newton's method to find the root of x^3 - 2x - 5 = 0 starting at x0 = 2"
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    from app.models.math_schemas import NewtonMethodResult

    with patch(
        "app.services.math_tools.math_service.newton_method",
        return_value=NewtonMethodResult(
            iterations=[], converged=False, root=None, iterations_used=0
        ),
    ):
        block = math_tools._build_verified_block(intent, settings)
    assert block is not None
    assert "did not converge" in block.text.lower()
    assert "do not present a root" in block.text.lower()
    assert block.canonical_fence is None
    assert "```answer" not in block.text


def test_extract_rectangle_intent() -> None:
    intent = math_tools.extract_math_intent("rectangle 8 x 5 cm find diagonal")
    assert intent is not None
    assert intent.kind == "rectangle"
    assert intent.width == 8
    assert intent.height == 5


def test_extract_draw_rectangle_defaults() -> None:
    intent = math_tools.extract_math_intent("Draw a rectangle")
    assert intent is not None
    assert intent.kind == "rectangle"
    assert intent.width == 6
    assert intent.height == 4


@pytest.mark.parametrize(
    "text, wants_diagonal, wants_angle, wants_area, wants_perimeter",
    [
        ("rectangle area with 4 by 5", False, False, True, False),
        ("rectangle 8 x 5 cm find diagonal", True, False, False, False),
        ("rectangle 8 x 5 cm diagonal angle", True, True, False, False),
        ("rectangle perimeter 4 by 5", False, False, False, True),
        ("rectangle 4 by 5", False, False, False, False),
    ],
)
def test_extract_rectangle_intent_captures_what_was_asked(
    text: str, wants_diagonal: bool, wants_angle: bool, wants_area: bool, wants_perimeter: bool
) -> None:
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.wants_diagonal is wants_diagonal
    assert intent.wants_angle is wants_angle
    assert intent.wants_area is wants_area
    assert intent.wants_perimeter is wants_perimeter


def test_extract_circle_radius_intent() -> None:
    intent = math_tools.extract_math_intent("Draw a circle with radius 4 cm")
    assert intent is not None
    assert intent.kind == "circle"
    assert intent.radius == 4


def test_extract_circle_diameter_intent() -> None:
    intent = math_tools.extract_math_intent("circle diameter 10")
    assert intent is not None
    assert intent.kind == "circle"
    assert intent.radius == 5
    assert intent.wants_diameter is True


def test_extract_circle_intent_defaults_without_dims() -> None:
    intent = math_tools.extract_math_intent("Draw a circle")
    assert intent is not None
    assert intent.kind == "circle"
    assert intent.radius == 5


@pytest.mark.parametrize(
    "text",
    [
        "what is a circle?",
        "explain the unit circle",
        "the circle is a set of points",
        "what is a trapezoid?",
        "define a parallelogram",
        "area of a triangle",
        "what is a right triangle",
        "sector of a circle with radius 5",
        "what is a cylinder?",
        "what is a sphere",
    ],
)
def test_geometry_does_not_invent_dims_without_draw_or_measures(text: str) -> None:
    """BUG FIX: bare shape prose used to invent default dimensions and emit a
    SymPy-verified ```geometry fence (e.g. circle r=5, trap 4x8x5)."""
    intent = math_tools.extract_math_intent(text)
    assert intent is None or intent.kind not in {
        "circle",
        "trapezoid",
        "parallelogram",
        "triangle",
        "right_triangle",
        "sector",
        "square",
        "rectangle",
        "solid",
    }


@pytest.mark.parametrize(
    "text, expected_kind",
    [
        ("solve x^2 + y^2 = 25 for the circle of radius 5", "equation"),
        ("find the equation of a circle with radius 4", None),
        ("equation of the circle with center (0,0) and radius 5", None),
        ("solve x^2 + y^2 = 1 (unit circle)", "equation"),
    ],
)
def test_geometry_does_not_steal_algebra_asks(text: str, expected_kind: str | None) -> None:
    """Geometry extractors run before equation/graph. A radius/dim cue must
    not swallow an algebra ask into a ```geometry fence."""
    intent = math_tools.extract_math_intent(text)
    if expected_kind is None:
        assert intent is None or intent.kind not in {
            "circle",
            "triangle",
            "right_triangle",
            "trapezoid",
            "parallelogram",
            "sector",
        }
    else:
        assert intent is not None
        assert intent.kind == expected_kind


def test_draw_circle_with_radius_still_geometry() -> None:
    """Draw cue wins over algebra deferral — explicit diagram requests stay
    on the geometry path even if the sentence also says 'equation'."""
    intent = math_tools.extract_math_intent(
        "draw a circle with radius 4 and show the equation labels"
    )
    assert intent is not None
    assert intent.kind == "circle"
    assert intent.radius == 4


@pytest.mark.parametrize(
    "text",
    [
        "(2,3)",
        "(2, 3)",
        "(2.3)",  # BUG FIX: comma-for-period mobile keyboard slip
        "(-2, 3)",
        "plot the point (2, 3)",
        "mark point 2, 3",
    ],
)
def test_extract_bare_point_intent(text: str) -> None:
    """BUG FIX regression: a bare coordinate pair (e.g. answering "what
    point?" with "(2,3)") had no intent detection at all, so the model was
    left to freely improvise — observed inventing an unrequested line
    (y=1.5x) that merely happens to pass through the point instead of
    marking the point itself."""
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "point"
    assert intent.point_x == pytest.approx(-2.0 if text.startswith("(-2") else 2.0)
    assert intent.point_y == pytest.approx(3.0)


def test_bare_point_does_not_misfire_on_prose_with_a_decimal_in_parens() -> None:
    """The whole-message match requirement keeps this from misfiring on
    ordinary prose that happens to contain a parenthesized decimal."""
    intent = math_tools.extract_math_intent("The result is about (2.3) give or take")
    assert intent is None or intent.kind != "point"


def test_extract_square_intent() -> None:
    intent = math_tools.extract_math_intent("Draw a square with side 5 cm")
    assert intent is not None
    assert intent.kind == "square"
    assert intent.side == 5


@pytest.mark.parametrize(
    "text",
    [
        "solve square root of x = 4",
        "graph the square root of x",
        "factor this perfect square trinomial",
        "what is the square of 7",
    ],
)
def test_square_root_does_not_become_geometry_square(text: str) -> None:
    """BUG FIX: substring 'square' used to inject a default 5 cm square."""
    intent = math_tools.extract_math_intent(text)
    assert intent is None or intent.kind != "square"


def test_draw_square_without_side_still_defaults() -> None:
    intent = math_tools.extract_math_intent("Draw a square")
    assert intent is not None
    assert intent.kind == "square"
    assert intent.side == 5


@pytest.mark.parametrize(
    "text, shape, volume_asked, sa_asked",
    [
        ("volume of a cube with side 5 cm", "cube", True, False),
        ("surface area of a cube side 4", "cube", False, True),
        ("volume of a rectangular prism 3 by 4 by 5", "rectangular_prism", True, False),
        ("volume of a cuboid length 3 width 4 height 5", "rectangular_prism", True, False),
        ("volume of a cylinder radius 3 height 10", "cylinder", True, False),
        ("volume of a cone radius 3 height 4", "cone", True, False),
        ("volume of a sphere radius 3", "sphere", True, False),
        ("volume of a square pyramid base 6 height 4", "pyramid", True, False),
        ("surface area of a sphere with radius 3", "sphere", False, True),
    ],
)
def test_extract_solid_intent(text: str, shape: str, volume_asked: bool, sa_asked: bool) -> None:
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "solid"
    assert intent.solid_shape == shape
    assert intent.wants_volume is volume_asked
    assert intent.wants_surface_area is sa_asked


def test_rectangular_prism_does_not_become_2d_rectangle() -> None:
    intent = math_tools.extract_math_intent("volume of a rectangular prism 3 by 4 by 5")
    assert intent is not None
    assert intent.kind == "solid"
    assert intent.solid_shape == "rectangular_prism"


@pytest.mark.parametrize(
    "text",
    [
        "cube root of 8",
        "solve the cubic equation",
        "what is the cube of 7",
    ],
)
def test_algebraic_cube_is_not_a_solid(text: str) -> None:
    intent = math_tools.extract_math_intent(text)
    assert intent is None or intent.kind != "solid"


def test_verified_block_cube_volume() -> None:
    settings = Settings(math_tools_enabled=True)
    intent = math_tools.extract_math_intent("volume of a cube with side 5 cm")
    assert intent is not None
    block = math_tools._build_verified_block(intent, settings)
    assert block is not None
    assert block.canonical_answer == "125"
    assert "```answer" in block.text
    assert block.canonical_fence is not None
    assert block.canonical_fence["type"] == "answer"


def test_verified_block_prism_volume() -> None:
    settings = Settings(math_tools_enabled=True)
    intent = math_tools.extract_math_intent("volume of a rectangular prism 3 by 4 by 5")
    assert intent is not None
    block = math_tools._build_verified_block(intent, settings)
    assert block is not None
    assert block.canonical_answer == "60"


@pytest.mark.parametrize(
    "text, kind",
    [
        ("what is 7*8", "arithmetic"),
        ("what is 15% of 80", "arithmetic"),
        ("simplify the ratio 6:8", "arithmetic"),
        ("sin 30", "trig"),
        ("distance between (0,0) and (3,4)", "coord"),
        ("midpoint of (0,0) and (4,6)", "coord"),
        ("magnitude of <3,4>", "vector"),
        ("dot product of <1,2> and <3,4>", "vector"),
        ("binomial n=5 k=2 p=0.5", "probability"),
        ("convert 5 ft to m", "unit"),
        ("taylor of sin(x) at 0 order 3", "calculus"),
    ],
)
def test_extract_school_homework_kinds(text: str, kind: str) -> None:
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == kind


def test_verified_percent_and_distance() -> None:
    settings = Settings(math_tools_enabled=True)
    percent = math_tools.extract_math_intent("what is 15% of 80")
    assert percent is not None
    block = math_tools._build_verified_block(percent, settings)
    assert block is not None
    assert block.canonical_answer == "12"
    dist = math_tools.extract_math_intent("distance between (0,0) and (3,4)")
    assert dist is not None
    dblock = math_tools._build_verified_block(dist, settings)
    assert dblock is not None
    assert dblock.canonical_answer == "5"


@pytest.mark.parametrize(
    "text, expected_expr",
    [
        ("graph x^2 please", "x**2"),
        ("graph x^2 for me", "x**2"),
        ("plot sin(x) and explain it", "sin(x)"),
        ("can you graph x^2 now", "x**2"),
        # The composer/math keyboard wraps the expression in $...$ and can
        # emit a base-less superscript chain for "x²" — without stripping
        # the delimiters and folding ^{x}^{2} → x^{2} → x^2, SymPy's safe-char
        # gate rejects $/{/} and the turn ships with no verified fence.
        ("Graph $x^2$", "x**2"),
        ("Graph $^{x}^{2}$", "x**2"),
    ],
)
def test_extract_graph_intent_strips_trailing_prose(text: str, expected_expr: str) -> None:
    """BUG FIX regression: the graph-expr capture is greedy, so natural
    phrasing ('graph x^2 please') used to sweep trailing conversational
    words into the "expression" — which then failed to parse in SymPy and
    silently disabled the verified-graph augmentation entirely."""
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "graph"
    assert intent.expr == expected_expr


@pytest.mark.parametrize(
    "text, expected_expr",
    [
        ("graph x=2y", "x/2"),
        ("plot x = 2*y", "x/2"),
        ("graph x=-3y", "-x/3"),
        ("graph 2x=y", "2*x"),
    ],
)
def test_extract_graph_intent_solves_equation_for_y(text: str, expected_expr: str) -> None:
    """BUG FIX regression: 'graph x=2y' is an equation, not a function
    expression. sample_function used to receive 'x=2y' (an Equality) and
    reject it, so no verified graph was emitted and the model emitted its
    own (often wrong) spec. The extractor now solves for y as y = f(x)."""
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "graph"
    assert intent.expr == expected_expr


@pytest.mark.parametrize(
    "text, expected_expr",
    [
        ("y=3x+4", "3x+4"),
        ("$y=3x+4$", "3x+4"),
        ("y=x^2", "x**2"),
    ],
)
def test_extract_graph_intent_bare_y_equals(text: str, expected_expr: str) -> None:
    """A slope-intercept / function-form message with no 'graph'/'plot'
    still extracts as a graph so the verified sample fence reaches the
    rewriter. Otherwise the model emits an empty-points ```graph and the
    user sees 'Could not render that diagram.'"""
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "graph"
    assert intent.expr == expected_expr


def test_extract_bare_y_equals_stays_equation_when_solving() -> None:
    intent = math_tools.extract_math_intent("solve y=3x+4")
    assert intent is not None
    assert intent.kind == "equation"


@pytest.mark.asyncio
async def test_augment_bare_y_equals_injects_graph_fence() -> None:
    settings = Settings(math_tools_enabled=True)
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "$y=3x+4$"}],
        "$y=3x+4$",
        settings,
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "function"
    points = verified.canonical_fence["points"]
    assert len(points) >= 2
    x0, y0 = points[len(points) // 2]
    assert abs(y0 - (3.0 * x0 + 4.0)) < 1e-4


@pytest.mark.parametrize(
    "text, expected_expr",
    [
        ("differentiate x^2 please", "x^2"),
        ("integrate x^2 for me", "x^2"),
        ("simplify x^2 + 2x + x^2 now", "x^2 + 2x + x^2"),
    ],
)
def test_extract_calculus_intent_strips_trailing_prose(text: str, expected_expr: str) -> None:
    """Same bug as the graph case, for the calculus expr-match capture."""
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "calculus"
    assert intent.expr == expected_expr


@pytest.mark.parametrize(
    "text, expected_op",
    [
        ("factor x^2 - 1", "factor"),
        ("expand (x-1)(x+1)", "expand"),
        ("Factor the polynomial x^3 - 1", "factor"),
    ],
)
def test_extract_factor_expand_intent(text: str, expected_op: str) -> None:
    """BUG FIX regression: factor/expand were in _MATH_KEYWORDS (so they
    enabled the math path) but had no intent branch — a silent no-op. They
    now route to a calculus factor/expand operation."""
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "calculus"
    assert intent.operation == expected_op
    assert intent.expr


def test_extract_definite_integral_bounds() -> None:
    """'integrate x^2 from 0 to 1' parses bounds and strips them from expr."""
    intent = math_tools.extract_math_intent("integrate x^2 from 0 to 1")
    assert intent is not None
    assert intent.kind == "calculus"
    assert intent.operation == "integrate"
    assert intent.expr == "x^2"
    assert intent.integral_lower == "0"
    assert intent.integral_upper == "1"


def test_extract_indefinite_integral_has_no_bounds() -> None:
    intent = math_tools.extract_math_intent("integrate x^2")
    assert intent is not None
    assert intent.operation == "integrate"
    assert intent.integral_lower is None
    assert intent.integral_upper is None


@pytest.mark.parametrize(
    "text, expected_cmp",
    [
        ("solve x**2 - 1 > 0", ">"),
        ("solve x \\leq 5", "<="),
        ("solve 2x + 1 < 7", "<"),
    ],
)
def test_extract_inequality_intent(text: str, expected_cmp: str) -> None:
    """Inequalities route to a dedicated intent kind with the canonical
    comparator. Safe from prose false-positives because extract_math_intent
    is only called when a math keyword already matched."""
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "inequality"
    assert intent.comparator == expected_cmp
    assert intent.lhs and intent.rhs


def test_extract_compound_inequality_intent() -> None:
    intent = math_tools.extract_math_intent("solve 1 < x < 5")
    assert intent is not None
    assert intent.kind == "inequality"
    assert intent.lower == "1"
    assert intent.lhs == "x"
    assert intent.rhs == "5"
    assert intent.comparator == "<"
    assert intent.comparator_upper == "<"


def test_extract_abs_inequality_intent() -> None:
    intent = math_tools.extract_math_intent("solve |x-2| < 5")
    assert intent is not None
    assert intent.kind == "inequality"
    assert intent.lhs == "Abs(x-2)"
    assert intent.rhs == "5"
    assert intent.comparator == "<"


@pytest.mark.parametrize(
    "text, expected_expr, expected_var, expected_point",
    [
        ("find the limit of x^2 as x approaches 3", "x**2", "x", "3"),
        ("limit of sin(x)/x as x approaches 0", "sin(x)/x", "x", "0"),
        ("what is the limit of 1/x as x approaches infinity", "1/x", "x", "infinity"),
        ("evaluate the limit of (x^2-1)/(x-1) as x -> 1", "(x**2-1)/(x-1)", "x", "1"),
        ("lim x->0 sin(x)/x", "sin(x)/x", "x", "0"),
        (r"\lim_{x \to 0} \sin(x)/x", "sin(x)/x", "x", "0"),
    ],
)
def test_extract_limit_intent(
    text: str, expected_expr: str, expected_var: str, expected_point: str
) -> None:
    assert math_tools.needs_symbolic_math(text) is True
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "limit"
    assert intent.expr == expected_expr
    assert intent.variable == expected_var
    assert intent.limit_point == expected_point


def test_limit_regex_does_not_misfire_on_unrelated_approaches_prose() -> None:
    """The word "approaches" alone (without "limit"/"lim") must not trigger
    symbolic math — e.g. "the deadline as it approaches Friday" is not math."""
    assert math_tools.needs_symbolic_math("the deadline as it approaches Friday") is False


@pytest.mark.parametrize(
    "text, expected_expr, expected_var, expected_start, expected_end",
    [
        (
            "does the series sum of 1/n^2 from n=1 to infinity converge",
            "1/n**2",
            "n",
            "1",
            "infinity",
        ),
        ("evaluate the sum of 1/2^n from n=0 to infinity", "1/2**n", "n", "0", "infinity"),
        ("sum of n from n=1 to 10", "n", "n", "1", "10"),
        (r"\sum_{n=1}^{\infty} 1/n^2", "1/n**2", "n", "1", "infty"),
    ],
)
def test_extract_series_intent(
    text: str, expected_expr: str, expected_var: str, expected_start: str, expected_end: str
) -> None:
    assert math_tools.needs_symbolic_math(text) is True
    intent = math_tools.extract_math_intent(text)
    assert intent is not None
    assert intent.kind == "series"
    assert intent.expr == expected_expr
    assert intent.variable == expected_var
    assert intent.series_start == expected_start
    assert intent.series_end == expected_end


@pytest.mark.asyncio
async def test_augment_prompt_injects_limit_block() -> None:
    settings = Settings(math_tools_enabled=True)
    text = "find the limit of x^2 as x approaches 3"
    out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert "Result: 9" in verified.text
    assert any("Result: 9" in m["content"] for m in out if m["role"] == "system")
    assert verified.canonical_fence == {"type": "answer", "content": "9"}
    assert "```answer" in verified.text


@pytest.mark.asyncio
async def test_augment_prompt_calculus_attaches_answer_fence() -> None:
    settings = Settings(math_tools_enabled=True)
    text = "differentiate x^2"
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "answer"
    assert "2" in verified.canonical_fence["content"]
    assert "```answer" in verified.text


@pytest.mark.asyncio
async def test_augment_prompt_calculus_includes_derivation_steps() -> None:
    """BUG FIX (MATH-BE-026): differentiation used to ship only the final
    result with no worked derivation, so the model invented its own (often
    wrong) steps. Now SymPy-verified per-term derivation steps (rule-named)
    are injected for the model to copy verbatim."""
    settings = Settings(math_tools_enabled=True)
    text = "differentiate x^3 + 2x"
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    # Sum rule line + per-term power-rule lines + result line.
    assert "Sum rule" in verified.text
    assert "Power rule" in verified.text
    assert "Result:" in verified.text


def test_differentiate_expression_steps_name_rules() -> None:
    """Unit-level check: the differentiation steps name the rule applied to
    each term and carry the SymPy-verified derivative."""
    from app.services import math_service

    out = math_service.differentiate_expression("x^3 + 5", "x")
    assert out.solved
    assert any("Sum rule" in s for s in out.steps)
    assert any("Power rule" in s and "3" in s for s in out.steps)
    assert any("Constant rule" in s for s in out.steps)
    assert out.steps[-1].startswith("Result:")
    # The verified derivative of x^3 + 5 is 3*x^2.
    assert "3" in out.result and "x" in out.result


@pytest.mark.asyncio
async def test_augment_prompt_unsolved_integral_has_no_answer_fence() -> None:
    settings = Settings(math_tools_enabled=True)
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "integrate x**x"}], "integrate x**x", settings
    )
    assert verified is not None
    assert verified.canonical_fence is None
    assert "```answer" not in verified.text


@pytest.mark.asyncio
async def test_augment_prompt_flags_diverging_limit_as_infinite() -> None:
    """BUG FIX target: a limit that diverges (e.g. 1/x as x -> 0) must be
    flagged as infinite, not presented as an ordinary finite value."""
    settings = Settings(math_tools_enabled=True)
    text = "what is the limit of 1/x as x approaches 0"
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert "infinite" in verified.text.lower()


@pytest.mark.asyncio
async def test_augment_prompt_injects_series_block_with_convergence() -> None:
    settings = Settings(math_tools_enabled=True)
    text = r"\sum_{n=1}^{\infty} 1/n^2"
    out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert "Convergent: True" in verified.text
    assert any("Convergent: True" in m["content"] for m in out if m["role"] == "system")


@pytest.mark.asyncio
async def test_augment_prompt_flags_divergent_series() -> None:
    """BUG FIX target: the harmonic series (sum 1/n) diverges — the model
    must be told it diverges/is infinite, not shown a plausible finite
    number it would otherwise be tempted to invent."""
    settings = Settings(math_tools_enabled=True)
    text = "does the series sum of 1/n from n=1 to infinity converge"
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert "Convergent: False" in verified.text
    assert "diverges" in verified.text.lower()


@pytest.mark.asyncio
async def test_augment_prompt_injects_geometry_block() -> None:
    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "rectangle 8 x 5 cm diagonal angle"}]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "rectangle 8 x 5 cm diagonal angle",
        settings,
    )
    assert len(out) == 2
    assert "```geometry" in out[0]["content"]
    assert "diagonal" in out[0]["content"]
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "rectangle"


@pytest.mark.asyncio
async def test_augment_prompt_rectangle_area_query_does_not_force_diagonal_and_angle() -> None:
    """BUG FIX regression: the rectangle geometry block always set
    show_diagonal=True, show_angle=True regardless of what was asked, so a
    plain "rectangle area 4 by 5" query drew an unrequested diagonal plus a
    diagonal-vs-base angle that visually contradicted the rectangle's own
    (always 90°) corner. The diagram should only annotate what was asked."""
    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "What about rectangle area with 4 by 5"}]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "What about rectangle area with 4 by 5",
        settings,
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["show_diagonal"] is False
    assert verified.canonical_fence["show_angle"] is False
    assert verified.canonical_fence["show_area"] is True
    assert verified.canonical_fence["show_perimeter"] is False
    assert verified.canonical_answer == "20"


@pytest.mark.asyncio
async def test_augment_prompt_injects_circle_geometry_block() -> None:
    """BUG FIX regression: circles were never a supported geometry kind
    anywhere in the pipeline — the model's own improvised ```geometry
    {"type":"circle",...} fence had no SymPy-verified values and no schema
    to validate against. Now a direct "circle radius 4" gets the same
    verified-computation treatment as every other shape."""
    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "circle radius 4 area circumference"}]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "circle radius 4 area circumference",
        settings,
    )
    assert len(out) == 2
    assert "```geometry" in out[0]["content"]
    assert '"type":"circle"' in out[0]["content"]
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "circle"
    assert verified.canonical_fence["show_area"] is True
    assert verified.canonical_fence["show_circumference"] is True


@pytest.mark.asyncio
async def test_augment_circle_circumference_answer_not_area() -> None:
    """BUG FIX: 'circumference of circle r=4' used to return the area
    (≈50.27) as the verified final answer because the canonical answer was
    unconditionally the area. Now an explicit circumference request yields
    the circumference (≈25.13)."""
    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "circumference of circle radius 4"}]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "circumference of circle radius 4",
        settings,
    )
    assert verified is not None
    assert verified.canonical_answer is not None
    assert abs(float(verified.canonical_answer) - 25.13) < 0.01


@pytest.mark.asyncio
async def test_augment_circle_area_answer_when_only_area_requested() -> None:
    """'area of circle r=4' (no circumference) still returns the area as the
    verified final answer — the circumference fix must not regress the
    default area path."""
    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "area of circle radius 4"}]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "area of circle radius 4",
        settings,
    )
    assert verified is not None
    assert verified.canonical_answer is not None
    assert abs(float(verified.canonical_answer) - 50.27) < 0.01


@pytest.mark.asyncio
async def test_augment_stats_sample_stdev_uses_sample_divisor() -> None:
    """BUG FIX: 'sample standard deviation of {1,2,3,4,5}' used to return the
    population stdev because the only 'stdev' op mapped to population_stdev.
    Now 'sample …' maps to the (n-1) sample stdev."""
    import statistics as _stats

    settings = Settings(math_tools_enabled=True)
    data = [1, 2, 3, 4, 5]
    content = "sample standard deviation of 1, 2, 3, 4, 5"
    messages = [{"role": "user", "content": content}]
    out, verified = await math_tools.augment_prompt_messages(messages, content, settings)
    assert verified is not None
    assert verified.canonical_answer is not None
    expected = f"{_stats.stdev(data):.4f}"
    assert verified.canonical_answer == expected
    # Sanity: sample stdev must differ from population stdev here.
    assert expected != f"{_stats.pstdev(data):.4f}"


@pytest.mark.asyncio
async def test_augment_stats_population_stdev_still_default() -> None:
    """Bare 'standard deviation of …' (no sample/population qualifier) keeps
    the historical population-stdev default — the sample fix must not change
    the default interpretation."""
    import statistics as _stats

    settings = Settings(math_tools_enabled=True)
    data = [1, 2, 3, 4, 5]
    content = "standard deviation of 1, 2, 3, 4, 5"
    messages = [{"role": "user", "content": content}]
    out, verified = await math_tools.augment_prompt_messages(messages, content, settings)
    assert verified is not None
    assert verified.canonical_answer is not None
    assert verified.canonical_answer == f"{_stats.pstdev(data):.4f}"


@pytest.mark.asyncio
async def test_augment_prompt_injects_single_point_graph_block() -> None:
    """BUG FIX regression: a bare "(2,3)" reply (e.g. answering "what
    point?") had no augmentation at all, so the model was free to invent
    an unrequested line through the point instead of just marking it.
    Now it gets a verified single-point ```graph fence with an explicit
    instruction not to invent a function through it."""
    settings = Settings(math_tools_enabled=True)
    out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "(2,3)"}],
        "(2,3)",
        settings,
    )
    assert len(out) == 2
    assert "```graph" in out[0]["content"]
    assert "Do NOT" in out[0]["content"]
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["points"] == [[2.0, 3.0]]


@pytest.mark.asyncio
async def test_augment_prompt_injects_graph_block() -> None:
    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "Graph y = x^2"}]
    out, verified = await math_tools.augment_prompt_messages(messages, "Graph y = x^2", settings)
    assert len(out) == 2
    assert "```graph" in out[0]["content"]
    assert "points" in out[0]["content"]
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "function"


@pytest.mark.asyncio
async def test_augment_graph_uses_user_named_domain() -> None:
    """BUG FIX: 'graph y=x^2 from 0 to 100' used to sample on the [-10, 10]
    default window. Now the user-named domain drives the verified sample so
    the rendered curve spans the requested range."""
    settings = Settings(math_tools_enabled=True)
    text = "graph y = x^2 from 0 to 100"
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    pts = verified.canonical_fence["points"]
    xs = [p[0] for p in pts]
    assert min(xs) >= 0
    assert max(xs) <= 100


@pytest.mark.parametrize(
    "expr, expected_lo, expected_hi, expected_clean",
    [
        ("y=x^2 from 0 to 100", 0.0, 100.0, "y=x^2"),
        ("x^2 between -2 and 3", -2.0, 3.0, "x^2"),
        ("sin(x) on [-5, 5]", -5.0, 5.0, "sin(x)"),
        ("y=x^2 from -pi to pi", -3.14159265, 3.14159265, "y=x^2"),
        ("y=x^2 from 0 to 2pi", 0.0, 6.2831853, "y=x^2"),
    ],
)
def test_graph_domain_parses_user_window(
    expr: str, expected_lo: float, expected_hi: float, expected_clean: str
) -> None:
    from app.services import math_text_match as mtm

    out = mtm.graph_domain(expr)
    assert out is not None
    lo, hi, cleaned = out
    assert abs(lo - expected_lo) < 1e-4
    assert abs(hi - expected_hi) < 1e-4
    assert cleaned == expected_clean


def test_graph_domain_none_when_no_clause() -> None:
    from app.services import math_text_match as mtm

    assert mtm.graph_domain("y = x^2") is None
    # Reversed bounds are invalid — fall back to default rather than misplot.
    assert mtm.graph_domain("y=x^2 from 100 to 0") is None


@pytest.mark.asyncio
async def test_augment_prompt_injects_unit_circle_relation_graph() -> None:
    settings = Settings(math_tools_enabled=True)
    text = "graph x^2 + y^2 = 1"
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "function"
    pts = verified.canonical_fence["points"]
    assert len(pts) >= 16
    assert pts[0] == pts[-1]  # closed curve
    assert "parametric" in verified.text.lower() or "relation" in verified.text.lower()


@pytest.mark.asyncio
async def test_augment_prompt_injects_ellipse_relation_graph() -> None:
    settings = Settings(math_tools_enabled=True)
    text = "plot x^2/9 + y^2/4 = 1"
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": text}], text, settings
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    xs = [p[0] for p in verified.canonical_fence["points"]]
    ys = [p[1] for p in verified.canonical_fence["points"]]
    assert max(xs) == pytest.approx(3.0, abs=0.05)
    assert max(ys) == pytest.approx(2.0, abs=0.05)


@pytest.mark.asyncio
async def test_augment_prompt_attaches_segments_and_warns_on_discontinuous_graph() -> None:
    """BUG FIX (verified live): tan(x) over the default range drew a
    near-straight line across the pi/2 asymptote. The canonical fence must
    carry the split segments, and the model must be told not to describe it
    as one continuous curve."""
    settings = Settings(math_tools_enabled=True)
    out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "Graph tan(x)"}], "Graph tan(x)", settings
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    assert len(verified.canonical_fence["segments"]) == 7
    assert "discontinuity" in verified.text.lower()
    assert any("discontinuity" in m["content"].lower() for m in out if m["role"] == "system")


@pytest.mark.asyncio
async def test_augment_prompt_omits_segments_for_a_continuous_graph() -> None:
    """The overwhelmingly common case (no discontinuity) must not carry a
    redundant segments field duplicating every point."""
    settings = Settings(math_tools_enabled=True)
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "Graph x^2"}], "Graph x^2", settings
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["segments"] == []
    assert "discontinuity" not in verified.text.lower()


@pytest.mark.asyncio
async def test_augment_prompt_flags_unsolved_integral_instead_of_asserting_it() -> None:
    """BUG FIX: integrate_expression can hand back a result that still
    contains a literal unevaluated Integral(...) instead of raising, and this
    used to be injected as "Result: ... Do NOT recompute" — the exact same
    verified-confidence phrasing used for a real closed-form answer. The
    model must be told SymPy found no closed form instead."""
    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "integrate x**x"}]
    out, verified = await math_tools.augment_prompt_messages(messages, "integrate x**x", settings)
    assert verified is not None
    assert "Do NOT recompute" not in verified.text
    assert "no closed form" in verified.text.lower() or "not claim" in verified.text.lower()
    assert any("no closed form" in m["content"].lower() for m in out if m["role"] == "system")


@pytest.mark.asyncio
async def test_vertical_line_graph_builds_canonical_fence() -> None:
    settings = Settings(math_tools_enabled=True)
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "Graph x = 4"}],
        "Graph x = 4",
        settings,
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "vertical"
    assert verified.canonical_fence["x"] == 4.0


@pytest.mark.asyncio
async def test_graph_inequality_builds_number_line_fence() -> None:
    settings = Settings(math_tools_enabled=True)
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "graph x > 3"}],
        "graph x > 3",
        settings,
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "number_line"
    iv = verified.canonical_fence["intervals"][0]
    assert iv["start"] == 3.0
    assert iv["end"] is None
    assert iv["start_inclusive"] is False
    # The prompt describes the number-line rendering (no longer says "NOT a
    # 1D number line" — that contradicted the emitted type:"number_line").
    assert "number line" in verified.text.lower()


@pytest.mark.asyncio
async def test_bare_inequality_builds_number_line_fence() -> None:
    """BUG FIX regression: a bare inequality with no math keyword ("X>4")
    used to fail needs_symbolic (the gate required a keyword), so the
    inequality extractor never ran and the model emitted "Could not render
    that diagram." with no verified fence. The gate now detects symbolic
    comparators with a variable + number, and the inequality builder emits
    a number_line canonical_fence so validate_math_fences can replace the
    model's malformed graph attempt."""
    settings = Settings(math_tools_enabled=True)
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "X>4"}],
        "X>4",
        settings,
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "number_line"
    iv = verified.canonical_fence["intervals"][0]
    assert iv["start"] == 4.0
    assert iv["end"] is None
    assert iv["start_inclusive"] is False
    assert verified.canonical_answer is not None
    assert "4" in verified.canonical_answer


@pytest.mark.asyncio
async def test_graph_sample_respects_math_graph_max_points_above_200() -> None:
    """BUG FIX regression: a stray `min(..., 200)` silently capped every
    graph at 200 points regardless of math_graph_max_points, so raising
    the setting above 200 had no effect."""
    settings = Settings(math_tools_enabled=True, math_graph_max_points=220)
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "Graph y = x^2"}],
        "Graph y = x^2",
        settings,
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    assert len(verified.canonical_fence["points"]) == 220
    assert "corrected/final graph spec" in verified.text.lower()


@pytest.mark.asyncio
async def test_default_graph_sample_stays_compact_for_chat_bubbles() -> None:
    """Default budget (~96) keeps densified fences SVG-friendly instead of
    dumping hundreds of points into the message (and FallbackMarkdown)."""
    settings = Settings(math_tools_enabled=True)
    _out, verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "Graph y = x^4 - 4x^2"}],
        "Graph y = x^4 - 4x^2",
        settings,
    )
    assert verified is not None
    assert verified.canonical_fence is not None
    assert len(verified.canonical_fence["points"]) == settings.math_graph_max_points
    assert settings.math_graph_max_points <= 120


@pytest.mark.asyncio
async def test_augment_prompt_injects_sympy_block() -> None:
    settings = Settings(math_tools_enabled=True)
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "Solve x^2 + 2 = 6"},
    ]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "Solve x^2 + 2 = 6",
        settings,
    )
    assert len(out) == 3
    assert out[1]["role"] == "system"
    assert "SymPy" in out[1]["content"]
    assert "Solutions" in out[1]["content"]
    # Equation answers get a ```answer canonical fence for post-stream rewrite.
    assert verified is not None
    assert verified.canonical_fence is not None
    assert verified.canonical_fence["type"] == "answer"
    assert "x" in verified.canonical_fence["content"]


@pytest.mark.asyncio
async def test_sympy_solve_runs_off_event_loop(
    monkeypatch: pytest.MonkeyPatch,
    thread_sympy_executor: None,
) -> None:
    """The blocking SymPy call must not run on the event loop thread.

    Uses the in-process thread executor so the spy can record the worker
    thread (a subprocess can't write back to the test's memory). The
    production ProcessPoolSympyExecutor is exercised separately in
    test_sympy_executor.py.
    """
    import threading

    settings = Settings(math_tools_enabled=True)
    caller_thread = threading.current_thread()
    seen_thread: dict[str, threading.Thread] = {}

    original = math_tools._build_verified_block

    def spy(intent, settings):  # type: ignore[no-untyped-def]
        seen_thread["thread"] = threading.current_thread()
        return original(intent, settings)

    monkeypatch.setattr(math_tools, "_build_verified_block", spy)

    out, _verified = await math_tools.augment_prompt_messages(
        [{"role": "user", "content": "Solve x^2 + 2 = 6"}],
        "Solve x^2 + 2 = 6",
        settings,
    )

    assert seen_thread["thread"] is not caller_thread
    assert len(out) == 2


@pytest.mark.asyncio
async def test_augment_prompt_times_out_gracefully(
    monkeypatch: pytest.MonkeyPatch,
    thread_sympy_executor: None,
) -> None:
    """A hung solve should not hang the caller, and must inject an honesty note.

    Uses the in-process thread executor so the local ``slow_build`` closure is
    callable (closures aren't picklable across a subprocess boundary). The
    production ProcessPoolSympyExecutor's hard-kill-on-timeout is exercised
    separately in test_sympy_executor.py.
    """
    settings = Settings(math_tools_enabled=True, math_solve_timeout_seconds=0.05)

    def slow_build(intent, settings):  # type: ignore[no-untyped-def]
        import time

        time.sleep(0.5)
        return "should never be returned"

    monkeypatch.setattr(math_tools, "_build_verified_block", slow_build)

    messages = [{"role": "user", "content": "Solve x^2 + 2 = 6"}]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "Solve x^2 + 2 = 6",
        settings,
    )

    assert verified is None
    assert len(out) == 2
    note = next(m["content"] for m in out if m["role"] == "system")
    assert "could not produce a verified result" in note
    assert "Do NOT claim the answer was SymPy-verified" in note


@pytest.mark.asyncio
async def test_augment_prompt_math_service_error_injects_unverified_note(
    monkeypatch: pytest.MonkeyPatch,
    thread_sympy_executor: None,
) -> None:
    """Parse/solve failures used to drop silently — same verified-looking chat
    UX as a successful SymPy block. Inject honesty instead."""
    settings = Settings(math_tools_enabled=True)

    def boom(intent, settings):  # type: ignore[no-untyped-def]
        raise math_tools.math_service.MathServiceError("unsafe expr")

    monkeypatch.setattr(math_tools, "_build_verified_block", boom)

    messages = [{"role": "user", "content": "Solve x^2 + 2 = 6"}]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "Solve x^2 + 2 = 6",
        settings,
    )

    assert verified is None
    note = next(m["content"] for m in out if m["role"] == "system")
    assert "kind=equation" in note
    assert "Do NOT claim the answer was SymPy-verified" in note


@pytest.mark.asyncio
async def test_augment_prompt_broken_pool_injects_unverified_note(
    monkeypatch: pytest.MonkeyPatch,
    thread_sympy_executor: None,
) -> None:
    """A sibling timeout's pool kill must not fail this turn before streaming."""
    from concurrent.futures.process import BrokenProcessPool

    async def boom(*_args: object, **_kwargs: object) -> None:
        raise BrokenProcessPool("killed by sibling timeout")

    monkeypatch.setattr("app.services.sympy_executor.run_sympy", boom)

    settings = Settings(math_tools_enabled=True)
    messages = [{"role": "user", "content": "Solve x^2 + 2 = 6"}]
    out, verified = await math_tools.augment_prompt_messages(
        messages,
        "Solve x^2 + 2 = 6",
        settings,
    )

    assert verified is None
    note = next(m["content"] for m in out if m["role"] == "system")
    assert "Do NOT claim the answer was SymPy-verified" in note
