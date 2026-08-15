"""Direct table-driven tests for the linear math matchers in math_text_match.

These matchers are the front door of intent detection — the place where
extractor precedence bugs (sector-before-circle, triangle-sides-before-
triangle, square-root exclusion) actually live. Each has a BUG FIX comment
in the implementation; these tests pin the precedence rules so a regression
is caught at the matcher layer rather than only indirectly through
math_tools intent extraction.
"""

from __future__ import annotations

import pytest

from app.services import math_text_match as mtm


class TestNeedsSymbolic:
    @pytest.mark.parametrize(
        "text",
        [
            "solve x^2 + 2 = 6",
            "what is the derivative of x^2",
            "graph y = x^2",
            "draw a rectangle 8 by 5",
            "draw a circle radius 4",
            "find the mean of 1, 2, 3, 4",
            "volume of a cube with side 5",
            "5!",
            "is 17 prime?",
            "determinant of [[1,2],[3,4]]",
            "plot (2, 3)",
        ],
    )
    def test_needs_symbolic_math_triggers(self, text):
        assert mtm.needs_symbolic(text)

    @pytest.mark.parametrize(
        "text",
        [
            "hello there",
            "what do you mean by that",
            "the tech sector is growing",  # "sector" alone is not geometry
            "what is a trapezoid",  # bare shape name, no measures/draw cue
            "what is a cylinder",
            "see you later",
        ],
    )
    def test_needs_symbolic_math_does_not_trigger(self, text):
        assert not mtm.needs_symbolic(text)

    def test_camera_prompt_triggers_only_with_image(self):
        prompt = "Solve the math problem in this image step by step."
        assert mtm.needs_symbolic(prompt, has_image_attachment=True)
        assert not mtm.needs_symbolic(prompt, has_image_attachment=False)


class TestDrawShapeGate:
    """Bare shape words must NOT trigger verified geometry — only an explicit
    draw/show/sketch cue (or printed measures) does. Regression guard for the
    "what is a circle?" inventing-dimensions bug."""

    @pytest.mark.parametrize(
        "shape, text",
        [
            ("rectangle", "draw a rectangle"),
            ("square", "show a square"),
            ("circle", "sketch a circle"),
            ("triangle", "visualize a triangle"),
            ("trapezoid", "draw a trapezoid"),
        ],
    )
    def test_draw_shape_matches(self, shape, text):
        assert mtm.has_draw_shape(text.lower(), shape)

    @pytest.mark.parametrize(
        "shape, text",
        [
            ("circle", "what is a circle"),
            ("trapezoid", "define a trapezoid"),
            ("square", "a square is a rectangle"),
        ],
    )
    def test_bare_shape_word_does_not_match_draw(self, shape, text):
        assert not mtm.has_draw_shape(text.lower(), shape)


class TestGeometryDeferredForAlgebra:
    """`solve x^2+y^2=25 for the circle of radius 5` must defer geometry to
    the algebra path — unless the user also asked to draw it."""

    @pytest.mark.parametrize(
        "text",
        [
            "solve x^2+y^2=25 for the circle of radius 5",
            "factor the unit circle expression",
            "integrate over the circle",
        ],
    )
    def test_algebra_defers_geometry(self, text):
        assert mtm.geometry_deferred_for_algebra(text.lower())

    @pytest.mark.parametrize(
        "text",
        [
            "draw a circle radius 5",
            "show the circle of radius 5",
            "sketch the circle",
        ],
    )
    def test_draw_cue_keeps_geometry(self, text):
        assert not mtm.geometry_deferred_for_algebra(text.lower())


class TestFirstDimPair:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("8 by 5 cm", (8.0, 5.0, "cm")),
            ("8x5", (8.0, 5.0, "cm")),
            ("8 × 5 cm", (8.0, 5.0, "cm")),
            ("8 * 5 units", (8.0, 5.0, "units")),
            ("rectangle 4 by 3", (4.0, 3.0, "cm")),
        ],
    )
    def test_first_dim_pair(self, text, expected):
        assert mtm.first_dim_pair(text) == expected

    def test_first_dim_pair_none_when_no_pair(self):
        assert mtm.first_dim_pair("just some text") is None


class TestFirstDimTriple:
    def test_three_edges(self):
        assert mtm.first_dim_triple("3 by 4 by 5 cm") == (3.0, 4.0, 5.0, "cm")
        assert mtm.first_dim_triple("3x4x5") == (3.0, 4.0, 5.0, "cm")

    def test_pair_is_not_a_triple(self):
        assert mtm.first_dim_triple("8 by 5 cm") is None


class TestParseSolid:
    def test_cube_volume(self):
        parsed = mtm.parse_solid("volume of a cube with side 5 cm")
        assert parsed is not None
        assert parsed.shape == "cube"
        assert parsed.side == 5.0
        assert parsed.wants_volume is True

    def test_prism_triple(self):
        parsed = mtm.parse_solid("volume of a rectangular prism 3 by 4 by 5")
        assert parsed is not None
        assert parsed.shape == "rectangular_prism"
        assert (parsed.width, parsed.depth, parsed.height) == (3.0, 4.0, 5.0)

    def test_bare_shape_without_measures(self):
        assert mtm.parse_solid("what is a cylinder") is None
        assert mtm.parse_solid("cube root of 8") is None


class TestNumberAfter:
    def test_number_after_label(self):
        assert mtm.number_after("circle radius 5", "radius") == 5.0
        assert mtm.number_after("radius 5", "radius") == 5.0

    def test_number_after_missing_label(self):
        assert mtm.number_after("circle diameter", "radius") is None


class TestGraphExpr:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("graph x^2", "x^2"),
            ("plot y = x^2", "x^2"),
            ("graph y=x^2", "x^2"),
        ],
    )
    def test_graph_expr(self, text, expected):
        assert mtm.graph_expr(text) == expected

    def test_graph_expr_none_without_trigger(self):
        assert mtm.graph_expr("x^2") is None


class TestGraphExprPair:
    """`graph y=x^2 and y=2x` must split into two candidates — checked
    BEFORE the single-expression graph_expr so it isn't garbled into one
    unparseable expr. But `plot sin(x) and explain it` must NOT treat
    "explain it" as a second function."""

    def test_pair_splits_two_functions(self):
        assert mtm.graph_expr_pair("graph y=x^2 and y=2x") == ("x^2", "2x")

    def test_pair_rejects_prose_second_clause(self):
        # "explain it" is in the prose denylist → falls through to single expr.
        assert mtm.graph_expr_pair("plot sin(x) and explain it") is None

    def test_pair_none_without_and(self):
        assert mtm.graph_expr_pair("graph x^2") is None


class TestVerticalLine:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("graph x=4", 4.0),
            ("plot x = 7", 7.0),
            ("draw vertical x=3", 3.0),
        ],
    )
    def test_vertical_line_x(self, text, expected):
        assert mtm.vertical_line_x(text) == expected

    def test_vertical_line_none_without_cue(self):
        # Bare "x=4" with no graph/plot/draw/show cue is not a vertical-line ask.
        assert mtm.vertical_line_x("x=4") is None


class TestTriangleSidesSignal:
    """`triangle with sides 3, 4, 5` must be detected as SSS — and requires
    both "triangle" AND a "sides" cue, so a bare "triangle" doesn't match."""

    def test_triangle_sides_signal(self):
        assert mtm.triangle_sides_signal("triangle with sides 3, 4, 5") == (3.0, 4.0, 5.0)

    def test_triangle_sides_signal_requires_sides_cue(self):
        assert mtm.triangle_sides_signal("triangle 3 4 5") is None

    def test_triangle_sides_signal_requires_triangle_word(self):
        assert mtm.triangle_sides_signal("sides 3, 4, 5") is None


class TestStatsSignal:
    def test_stats_signal_mean(self):
        op, numbers = mtm.stats_signal("mean of 1, 2, 3, 4")
        assert op == "mean"
        assert numbers == [1.0, 2.0, 3.0, 4.0]

    def test_stats_signal_standard_deviation(self):
        op, _ = mtm.stats_signal("standard deviation of 10, 20, 30")
        assert op == "stdev"

    def test_stats_signal_requires_two_plus_numbers(self):
        # "what do you mean by X" — no data list → no match.
        assert mtm.stats_signal("what do you mean by that") is None


class TestCombinatoricsSignal:
    @pytest.mark.parametrize(
        "text, expected_op",
        [
            ("5!", "factorial"),
            ("factorial of 6", "factorial"),
            ("5 choose 2", "combinations"),
            ("C(5,2)", "combinations"),
            ("5C2", "combinations"),
            ("P(5,2)", "permutations"),
            ("5P2", "permutations"),
        ],
    )
    def test_combinatorics_signal(self, text, expected_op):
        op, n, k = mtm.combinatorics_signal(text)
        assert op == expected_op

    def test_combinatorics_factorial_k_is_none(self):
        op, n, k = mtm.combinatorics_signal("5!")
        assert op == "factorial"
        assert k is None


class TestNumberTheorySignal:
    @pytest.mark.parametrize(
        "text, expected_op, expected_a, expected_b",
        [
            ("gcd of 12 and 18", "gcd", 12, 18),
            ("lcm of 4 and 6", "lcm", 4, 6),
            ("prime factorization of 60", "factorize", 60, None),
            ("is 17 prime", "is_prime", 17, None),
            ("10 mod 3", "mod", 10, 3),
        ],
    )
    def test_number_theory_signal(self, text, expected_op, expected_a, expected_b):
        op, a, b = mtm.number_theory_signal(text)
        assert op == expected_op
        assert a == expected_a
        assert b == expected_b


class TestMatrixSignal:
    def test_matrix_signal_determinant(self):
        op, rows = mtm.matrix_signal("determinant of [[1,2],[3,4]]")
        assert op == "determinant"
        assert rows == [[1.0, 2.0], [3.0, 4.0]]

    def test_matrix_signal_inverse(self):
        op, rows = mtm.matrix_signal("inverse of [[2,0],[1,3]]")
        assert op == "inverse"

    def test_matrix_signal_requires_bracket_notation(self):
        assert mtm.matrix_signal("determinant of 1 2 3 4") is None

    def test_matrix_signal_rejects_non_square(self):
        assert mtm.matrix_signal("determinant of [[1,2,3],[4,5,6]]") is None


class TestParseLimit:
    def test_compact_limit(self):
        hit = mtm.parse_limit("lim x->0 sin(x)/x")
        assert hit is not None
        assert hit.var == "x"
        assert hit.point == "0"
        assert "sin(x)/x" in hit.expr

    def test_latex_limit(self):
        hit = mtm.parse_limit("\\lim_{x \\to 0} sin(x)/x")
        assert hit is not None
        assert hit.var == "x"
        assert hit.point == "0"

    def test_prose_limit_as_approaches(self):
        hit = mtm.parse_limit("find the limit of sin(x)/x as x approaches 0")
        assert hit is not None
        assert hit.var == "x"
        assert hit.point == "0"

    def test_infinity_limit(self):
        hit = mtm.parse_limit("lim x->infinity 1/x")
        assert hit is not None
        assert hit.point in ("infinity", "oo")

    def test_parse_limit_none(self):
        assert mtm.parse_limit("hello there") is None


class TestParseSeries:
    def test_prose_series(self):
        hit = mtm.parse_series("sum of x from n=1 to 10")
        assert hit is not None
        assert hit.var == "n"
        assert hit.start == "1"
        assert hit.end == "10"

    def test_latex_series(self):
        hit = mtm.parse_series("\\sum_{n=1}^{\\infty} 1/n**2")
        assert hit is not None
        assert hit.var == "n"
        assert hit.start == "1"
        assert hit.end in ("\\infty", "infinity")

    def test_parse_series_requires_keyword(self):
        assert mtm.parse_series("1 + 2 + 3") is None


class TestHasEquation:
    @pytest.mark.parametrize(
        "text",
        [
            "x + 2 = 5",
            "2*x + 3 = 7",
            "y = x^2",
        ],
    )
    def test_has_equation(self, text):
        assert mtm.has_equation(text)

    @pytest.mark.parametrize(
        "text",
        [
            "no equals here",
            "= 5",
            "x =",
            "== comparison",
        ],
    )
    def test_no_equation(self, text):
        assert not mtm.has_equation(text)
