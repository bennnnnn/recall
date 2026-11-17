"""Area between curves, arc length, volume of revolution, and even/odd.

This replaces the blanket refusal added in #1344, which was itself a response to
"area between y=x and y=x^2 from 0 to 1" being answered with the *intersection
points* of its two curves. The refusal stopped the wrong answer; this answers
the question.

Two things here are worth more than the formulas.

**Signed cancellation.** The area between sin(x) and 0 over a full period is 4,
not 0. Integrating the signed difference would let the half below the axis
cancel the half above it, and the answer would be exactly zero — a number that
looks like a result. The integral is split at every crossing instead.

**Partial bound matches.** "from 0 to 2*pi" originally matched just the `2`,
silently answering on [0, 2]. That is the same failure the whole refusal existed
to prevent, reintroduced through the bounds rather than the curves, so the bound
pattern is ordered longest-first and closed with a lookahead.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.modules.math.match.scan import prepare
from app.modules.math.tools import _build_verified_block, extract_math_intent
from app.modules.math.tools.extractors.calculus_applications import _area_between


def _settings() -> Settings:
    return Settings(math_tools_enabled=True)


def _verified_answer(text: str) -> str | None:
    intent = extract_math_intent(text)
    if intent is None:
        return None
    block = _build_verified_block(intent, _settings())
    return None if block is None else block.canonical_answer


def _intent(text: str):
    intent = extract_math_intent(text)
    assert intent is not None, f"no intent for {text!r}"
    return intent


# (question, expected school_op, expected answer)
VERIFIED: list[tuple[str, str, str]] = [
    # --- area between curves -------------------------------------------
    ("area between y=x and y=x^2 from 0 to 1", "area_between_curves", "\\frac{1}{6}"),
    (
        "find the area between the curves y=x and y=x^2 from 0 to 1",
        "area_between_curves",
        "\\frac{1}{6}",
    ),
    ("area between y=cos(x) and y=0 from 0 to pi/2", "area_between_curves", "1"),
    ("area between y=x and y=0 on [0, 2]", "area_between_curves", "2"),
    # --- arc length -----------------------------------------------------
    (
        "arc length of y=x^(3/2) from 0 to 1",
        "arc_length",
        "\\frac{13 \\sqrt{13}}{27} - \\frac{8}{27}",
    ),
    # --- volume of revolution -------------------------------------------
    (
        "volume of revolution of y=x from 0 to 1 about the x-axis",
        "volume_revolution_x",
        "\\frac{\\pi}{3}",
    ),
    (
        "volume of revolution of y=x^2 from 0 to 1 about the x-axis",
        "volume_revolution_x",
        "\\frac{\\pi}{5}",
    ),
    # --- even / odd ------------------------------------------------------
    ("is f(x)=x^3 even or odd", "function_symmetry", "odd"),
    ("is f(x)=x^2 even or odd", "function_symmetry", "even"),
    ("is f(x)=x^2+x even or odd", "function_symmetry", "neither"),
    ("is f(x)=cos(x) even or odd", "function_symmetry", "even"),
]


@pytest.mark.parametrize("text,op,answer", VERIFIED, ids=[row[0][:44] for row in VERIFIED])
def test_calculus_applications_answer(text: str, op: str, answer: str) -> None:
    assert _intent(text).school_op == op
    assert _verified_answer(text) == answer


# ---------------------------------------------------------------------------
# The two defects found while building this, pinned by value.
# ---------------------------------------------------------------------------


def test_a_region_below_the_axis_does_not_cancel_one_above_it() -> None:
    """sin(x) against 0 over a full period is 4, and signed integration gives 0.

    Zero is the dangerous answer here: it is not an error, it is a number, and
    a verified block would ship it.
    """
    assert (
        _verified_answer("find the area between the curves y=sin(x) and y=0 from 0 to 2*pi") == "4"
    )
    # Half the period is 2, so the full period cannot be 0 *or* 2.
    assert _verified_answer("area between y=sin(x) and y=0 from 0 to pi") == "2"


def test_a_bound_is_matched_whole_or_not_at_all() -> None:
    """ "from 0 to 2*pi" once matched just the 2, answering on [0, 2]."""
    intent = _intent("area between y=sin(x) and y=0 from 0 to 2*pi")
    assert intent.integral_upper == "2*pi"

    for text, upper in [
        ("area between y=x and y=0 from 0 to pi/2", "pi/2"),
        ("area between y=x and y=0 from 0 to 1/2", "1/2"),
        ("area between y=x and y=0 from 0 to 2*pi", "2*pi"),
    ]:
        assert _intent(text).integral_upper == upper


@pytest.mark.parametrize(
    "text,shown,typed",
    [
        ("area under sin(x) from 0 to 2*pi", r"2 \pi", "2*pi"),
        ("area between y=cos(x) and y=0 from 0 to pi/2", r"\frac{\pi}{2}", "pi/2"),
        ("arc length of y = 2x from 0 to pi", r"\pi", "pi"),
        ("volume of y = sqrt(x) from 0 to pi revolved about the x-axis", r"\pi", "pi"),
        ("volume of y = x from 0 to pi revolved about the y-axis", r"\pi", "pi"),
    ],
)
def test_the_working_prints_its_bounds_in_tex(text: str, shown: str, typed: str) -> None:
    """``0 \\le x \\le 2*pi`` and ``\\int_{0}^{2*pi}``: the bound as typed, not as maths."""
    intent = _intent(text)
    block = _build_verified_block(intent, _settings())
    assert block is not None and block.direct_reply is not None
    working = block.direct_reply
    assert rf"0 \le x \le {shown}$" in working
    assert rf"\int_{{0}}^{{{shown}}}" in working
    # Every place a bound is printed: the interval, integral limits, [F]_a^b.
    for written in (rf"\le {typed}$", f"^{{{typed}}}", f"[0, {typed}]"):
        assert written not in working


# The textbook's own wording (Grade 12 unit 5, live round 2026-11-16): "the area of the
# region bounded by the graph of …", a minus typed as U+2212, the lines that close the region,
# bounds such as 7π/4, 1/e and e², and a sentence after the question.
TEXTBOOK_REGIONS: list[tuple[str, str]] = [
    (
        "Find the area of the region enclosed by the graph of f(x) = 12 − 3x² and the x-axis "
        "from x = −4 to x = 3. Draw the graph and shade the region.",
        "71",
    ),
    (
        "Find the area of the region bounded by the graph of f(x) = x² − 3x + 2 and the x-axis "
        "between x = 0 and x = 3.",
        "\\frac{11}{6}",
    ),
    (
        "Find the area of the region bounded by the graph of f(x) = x/(x + 1), the x-axis and "
        "the lines x = −1/2 and x = 3. Show it on a graph.",
        "\\frac{5}{2} - \\ln 2",
    ),
    (
        "Find the area of the region enclosed by f(x) = sin x and the x-axis from x = π/4 to "
        "x = 7π/4. Sketch the region.",
        "\\sqrt{2} + 2",
    ),
    (
        "Find the area of the region enclosed by f(x) = ln x and the x-axis from x = 1/e to "
        "x = e². Show it on a graph.",
        "- \\frac{2}{e} + 2 + e^{2}",
    ),
    (
        "Find the area of the region enclosed by f(x) = 4 − x² and g(x) = 3x. Show the curves "
        "and shade the region.",
        "\\frac{125}{6}",
    ),
    (
        "Find the area of the region enclosed by the graphs of f(x) = x² and g(x) = √x.",
        "\\frac{1}{3}",
    ),
    ("Find the area of the region bounded by y = x² and y = 4.", "\\frac{32}{3}"),
]


@pytest.mark.parametrize(
    "text,answer", TEXTBOOK_REGIONS, ids=[r[0][24:64] for r in TEXTBOOK_REGIONS]
)
def test_textbook_regions_are_read_with_their_stated_interval(text: str, answer: str) -> None:
    """The asked interval is the one integrated: [-4, 3] gives 71, never the 32 between
    the roots that the reply answered when no reader claimed the question."""
    assert _intent(text).school_op == "area_between_curves"
    assert _verified_answer(text) == answer


@pytest.mark.parametrize(
    "text",
    [
        # A stated interval the bounds cannot read is never replaced by the meeting points.
        "Find the area of the region bounded by y = x² and y = 4 from x = 1/e² to x = 1.",
        "Find the area of the region bounded by y = x² and y = 4 on [a, 2].",
        # A partial bound is no bound: 7π of 7π/4, e of e^x.
        "area between y = sin x and y = 0 from x = 0 to x = 7π/x",
    ],
)
def test_a_stated_interval_is_read_whole_or_the_question_is_left(text: str) -> None:
    assert _verified_answer(text) is None


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        # An interval in another sentence is a picture's, never the area's (review,
        # 2026-11-16: 109/3, 28/3, 44/3 and 4 were checked for these).
        (
            "Find the area of the region enclosed by f(x) = 4 − x² and g(x) = 3x. Draw the "
            "graph from x = −5 to x = 3.",
            "\\frac{125}{6}",
        ),
        ("Find the area between y = x^2 and y = 2x. Plot both on [-1, 4].", "\\frac{4}{3}"),
        (
            "Find the area between y = x^2 and y = 2x. Draw the graph for x from x = -1 to x = 4.",
            "\\frac{4}{3}",
        ),
        (
            "Find the area of the region bounded by y = x^2 and y = 2x. Sketch the graphs for "
            "-2 ≤ x ≤ 4.",
            "\\frac{4}{3}",
        ),
        (
            "Find the area bounded by y = x^2 and y = 2x. Graph them between x = -1 and x = 3.",
            "\\frac{4}{3}",
        ),
        # The area's own sentence keeps its interval, the closing lines included.
        ("Find the area between y = x^2 and y = 2x from x = -1 to x = 3.", "4"),
    ],
)
def test_only_the_areas_own_sentence_states_its_interval(text: str, answer: str) -> None:
    assert _verified_answer(text) == answer


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        # Gemini on #2481: an interval stated before the area, or without "x =", is the
        # area's; 32/3 from the meeting points was checked for 11/3.
        ("From 0 to 1, find the area of the region bounded by y = x^2 and y = 4.", "\\frac{11}{3}"),
        ("On the interval [0, 1], find the area bounded by y = x^2 and y = 4.", "\\frac{11}{3}"),
        ("Find the area bounded by y = x^2 and y = 4 between 0 and 1.", "\\frac{11}{3}"),
        ("From 0 to 2, find the area under y = x^2.", "\\frac{8}{3}"),
        # One the bounds cannot read is never replaced by the meeting points.
        ("Find the area bounded by y = x^2 and y = 4 in the interval (0, 1).", None),
        ("From a to 1, find the area bounded by y = x^2 and y = 4.", None),
    ],
)
def test_any_interval_the_sentence_states_wins(text: str, answer: str | None) -> None:
    assert _verified_answer(text) == answer


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        # Claude on #2481: "between" naming the two curves is no interval. Read from the
        # sentence start, the stated-interval check took "between 2" for one and left
        # these unanswered.
        ("Find the area between 2x and x^2", "\\frac{4}{3}"),
        ("Find the area between (x+1)^2 and 4", "\\frac{32}{3}"),
        ("Find the area between y = -x and y = x^2 - 2", "\\frac{9}{2}"),
    ],
)
def test_between_naming_the_curves_states_no_interval(text: str, answer: str) -> None:
    assert _verified_answer(text) == answer


@pytest.mark.parametrize(
    "text",
    [
        "Find the area between 2x and x^2",
        "Find the area between e^x and x+1",
        "Find the area between (x+1)^2 and 4",
        "Find the area between -x and x^2",
    ],
)
def test_curves_after_between_are_not_a_stated_interval(text: str) -> None:
    cleaned = prepare(text)
    region = _area_between(cleaned) if cleaned else None
    assert region is not None and not region.stated


@pytest.mark.parametrize(
    "text",
    [
        # Gemini on #2481: a stated interval whose bounds the reader does not read is never
        # replaced by where the curves meet (32/3 was checked for these).
        "Between x = √2 and x = 2, find the area bounded by y = x^2 and y = 4.",
        "Between x = sqrt(2) and x = 2, find the area bounded by y = x^2 and y = 4.",
        "Find the area bounded by y = x^2 and y = 4 between ln 2 and 1.",
        "Find the area bounded by y = x^2 and y = 4 between x = \\pi/4 and x = 1.",
        # Gemini on #2481: a bound ends where its expression ends, never at "1" of
        # "1 / e²", "1 + √2" or "1+e" (11/3 on [0, 1] was checked).
        "Find the area bounded by y = x^2 and y = 4 from x = 0 to x = 1 / e².",
        "Find the area bounded by y = x^2 and y = 4 from x = 0 to x = 1 + √2.",
        "Find the area bounded by y = x^2 and y = 4 for 1+e <= x <= 5.",
        "Find the area bounded by y = x^2 and y = 4 for 1 + e <= x <= 5.",
        # Two curves are never read as one: "and y = 4" was dropped, 1/3 for 11/3.
        "Find the area under y = x^2 and y = 4 from 0 to 1.",
        # A vertical line among the edges bounds the region too.
        "Find the area bounded by y = x^2, y = 4 and the line x = 1.",
    ],
)
def test_an_unread_stated_interval_is_never_the_meeting_points(text: str) -> None:
    assert _verified_answer(text) is None


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        # Gemini on #2481: edges listed with commas, the textbook's wording.
        (
            "Find the area bounded by y = x^2 + 1, y = x, and the lines x = 0 and x = 2.",
            "\\frac{8}{3}",
        ),
        ("Find the area between 4 and x^2.", "\\frac{32}{3}"),
        ("Find the area bounded by y = x^2 and y = 4 for 0 <= x <= 1.", "\\frac{11}{3}"),
    ],
)
def test_edges_listed_with_commas_are_read(text: str, answer: str) -> None:
    assert _verified_answer(text) == answer


def test_the_area_answer_is_not_the_intersection_points() -> None:
    """The original defect, still pinned now that the question is answered."""
    answer = _verified_answer("area between y=x and y=x^2 from 0 to 1")
    assert answer == "\\frac{1}{6}"
    assert answer != "x = 0, y = 0; x = 1, y = 1"


# ---------------------------------------------------------------------------
# Refusals. Everything the codebase still cannot close.
# ---------------------------------------------------------------------------

REFUSED = [
    # No closed form for the arc length integral.
    "arc length of sin(x) from 0 to 1",
    # The axis decides the formula — disks about x, shells about y — so an
    # unnamed axis is not assumed.
    "volume of revolution of y=x from 0 to 1",
    # No interval to integrate over, and no single enclosed region.
    "area between y=sin(x) and y=cos(x)",
    "arc length of y=x^2",
    "area under y=x^2",
    # Still unimplemented shapes, still refused rather than answered sideways.
    "volume of the region bounded by y=x and y=0",
    # A shell volume straddling its own axis is not a volume.
    "volume of revolution of y=1 from -1 to 1 about the y-axis",
]


@pytest.mark.parametrize("text", REFUSED)
def test_unclosable_regions_are_refused(text: str) -> None:
    assert _verified_answer(text) is None


NOT_THESE = [
    # A genuine simultaneous system, on the very curves the area question uses.
    ("solve y = x and y = x^2", "x = 0, y = 0; x = 1, y = 1"),
    ("solve 2x + y = 5 and x - y = 1", "x = 2, y = 1"),
    # Geometry areas and volumes name no region between curves.
    ("what is the area of a rectangle 3 by 4", "12"),
    ("what is the area of a circle with radius 5", "78.54"),
    # The definite integral path is untouched.
    ("integrate x^2 from 0 to 1", "\\frac{1}{3}"),
]


@pytest.mark.parametrize("text,answer", NOT_THESE, ids=[row[0][:40] for row in NOT_THESE])
def test_neighbouring_kinds_are_untouched(text: str, answer: str) -> None:
    assert _verified_answer(text) == answer


PROSE = [
    "what is the area between the two teams in the league",
    "the volume of support has been rotating between 3 people",
    "we need more coverage between 2 and 4 pm",
    "is the release even or odd numbered",
]


@pytest.mark.parametrize("text", PROSE)
def test_prose_does_not_reach_the_verified_path(text: str) -> None:
    assert _verified_answer(text) is None


@pytest.mark.wall_clock
def test_a_long_run_of_digits_is_read_in_linear_time() -> None:
    """The chain of bounds was tried from every digit of a run: quadratic (review of #2481)."""
    import time

    from app.modules.math.tools.extractors import calculus_applications as reader

    text = "area under y = x for " + "1" * 30_000 + "x to x = 2"
    started = time.perf_counter()
    reader._bounds(text)
    assert time.perf_counter() - started < 0.5
