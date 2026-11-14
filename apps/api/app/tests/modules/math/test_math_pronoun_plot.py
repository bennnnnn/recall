"""A pronoun is never a function to plot.

Reported from the app: a chat about anatomy, "show me", and the reply ended
with *Couldn't verify this with SymPy.* — the math pipeline had claimed the
turn. `graph_expr("show me")` returned "me", because two-letter pronouns scan
as implicit multiplication (m*e, i*t, u*s) and so pass looks_like_math_expr.
Longer ones ("this", "him") already failed has_unknown_english_run, which is
why only the short ones leaked.

The math note is stamped whenever a math block was injected and SymPy then
produced nothing, so any non-math turn the extractor claims gets that label.
"""

from __future__ import annotations

import json

import pytest

from app.core.config import Settings
from app.modules.math.match import graph_expr
from app.modules.math.tools import extract_math_intent, needs_symbolic_math
from app.modules.math.tools.direct import maybe_direct_math_reply
from app.modules.math.tools.extract import resolve_graph_followup
from app.modules.math.tools.graph_followup import drawing_of
from app.modules.math.tools.prompt import NOTHING_TO_GRAPH, build_math_augmentation


@pytest.mark.parametrize(
    "text",
    [
        "show me",
        "show me it",
        "graph me",
        "draw me",
        "plot us",
        "plot them",
        "graph it",
        "show me this",
    ],
)
def test_pronoun_asks_never_reach_the_math_pipeline(text: str) -> None:
    """Otherwise the turn is claimed and stamped "Couldn't verify with SymPy"."""
    assert graph_expr(text) is None
    intent = extract_math_intent(text)
    assert intent is None or intent.kind != "graph"


@pytest.mark.parametrize(
    "text, expected_expr",
    [
        ("graph y = x^2", "x^2"),
        ("plot sin(x)", "sin(x)"),
        ("draw y=x^2", "x^2"),
        ("show y = 2x+1", "2x+1"),
        ("chart y=x^3", "x^3"),
        # A single variable and a real two-letter product must keep working:
        # the guard is an explicit pronoun table, not a length rule.
        ("graph x", "x"),
        ("plot ab", "ab"),
    ],
)
def test_real_plot_requests_still_extract(text: str, expected_expr: str) -> None:
    assert graph_expr(text) == expected_expr
    intent = extract_math_intent(text)
    assert intent is not None
    assert intent.kind in {"graph", "graph_pair"}
    assert needs_symbolic_math(text) is True


def test_graph_it_followup_still_resolves_from_the_prior_equation() -> None:
    """The pronoun guard must not disturb the follow-up path, which runs first."""
    content, skip_math = resolve_graph_followup("graph it", ["solve x^2 - 5x + 6 = 0"])

    assert content == "graph x^2 - 5x + 6=0"
    assert skip_math is False


def test_graph_it_with_no_plottable_prior_skips_math_instead_of_stamping() -> None:
    content, skip_math = resolve_graph_followup("graph it", ["what is a vagina"])

    assert content == "graph it"
    assert skip_math is True


@pytest.mark.parametrize(
    ("prior", "expected"),
    [
        ("find the derivative of y = 3x + 2 and y = 2x + 3", "graph 3x + 2 and 2x + 3"),
        ("what is the slope of y = 3x + 2 and y = 2x + 3", "graph 3x + 2 and 2x + 3"),
        ("which grows faster, y = 3x + 2 or y = 2x + 3?", "graph 3x + 2 and 2x + 3"),
        ("solve x + y = 5 and x - y = 1", "graph 5-x and x-1"),
        ("differentiate x^2", "graph x^2"),
    ],
)
def test_graph_it_reuses_the_functions_a_calculus_or_system_question_names(
    prior: str, expected: str
) -> None:
    """Reported from the app: "Graph it" after the slopes of two lines got an ASCII sketch."""
    assert resolve_graph_followup("Graph it", [prior]) == (expected, False)


@pytest.mark.parametrize(
    ("prior", "expected"),
    [
        # The keyboard's x² key sends ``$x^{2}$``; the reply asks what to do with it.
        ("$x^{2}$", ("graph x^2", False)),
        ("$\\sin(x)$", ("graph sin(x)", False)),
        ("x^3 - 2x", ("graph x^3 - 2x", False)),
        ("$\\sqrt{x}$", ("graph sqrt(x)", False)),
        # Not a curve in x: a number, words, another letter, two variables.
        ("$2$", ("Plot", True)),
        ("I have 2 apples", ("Plot", True)),
        ("$y$", ("Plot", True)),
        ("$x^{2}+y^{2}$", ("Plot", True)),
        ("what is x", ("Plot", True)),
    ],
)
def test_plot_after_a_bare_expression_draws_that_expression(
    prior: str, expected: tuple[str, bool]
) -> None:
    """Reported from the app: "Plot" after ``$x^{2}$`` drew a chart that failed to parse."""
    assert resolve_graph_followup("Plot", [prior]) == expected


def test_a_curve_solved_for_y_keeps_its_natural_log() -> None:
    """``log`` is base 10, so ``e^y = x`` must plot as ``ln(x)``, not ``log(x)``."""
    intent = extract_math_intent("graph e^y = x")

    assert intent is not None
    assert intent.expr == "ln(x)"


@pytest.mark.asyncio
async def test_graph_it_with_nothing_to_plot_asks_instead_of_drawing() -> None:
    block, verified = await build_math_augmentation(
        "graph it", Settings(), needs_math=True, prior_user_messages=["what is a vagina"]
    )

    assert verified is None
    assert block is NOTHING_TO_GRAPH
    assert NOTHING_TO_GRAPH in block
    assert "ASCII" in block


@pytest.mark.parametrize(
    ("text", "drawn"),
    [
        ("sin(x)", "graph sin(x)"),
        ("f(x)=1/(x-2)", "graph 1/(x-2)"),
        # A shape the geometry solver builds is drawn as itself, its figure the reply.
        ("Triangle are with sides 5, 4, 3", "Triangle are with sides 5, 4, 3"),
        ("area of a circle with radius 4", "area of a circle with radius 4"),
        # Nothing maths draws: a question of its own, data, a solid with no figure.
        ("What's the capital of France?", None),
        ("Sales: Jan 120, Feb 150, Mar 90", None),
        ("volume of a cube with side 3", None),
    ],
)
def test_what_an_earlier_message_draws_as(text: str, drawn: str | None) -> None:
    """The message a model read as the "it" of "draw it" (``chat.referent_read``)."""
    assert drawing_of(text) == drawn


@pytest.mark.asyncio
async def test_draw_it_after_a_shape_is_its_figure_alone(thread_sympy_executor: None) -> None:
    _note, verified = await build_math_augmentation(
        "Triangle are with sides 5, 4, 3", Settings(), needs_math=True
    )

    reply = maybe_direct_math_reply(verified, "Draw it")
    assert reply is not None and reply.startswith("```geometry\n") and reply.count("```") == 2
    figure = json.loads(reply.removeprefix("```geometry\n").removesuffix("\n```\n"))
    assert (figure["type"], figure["a"], figure["b"], figure["c"]) == ("triangle_sides", 5, 4, 3)
    assert maybe_direct_math_reply(verified, "a picture of it") == reply
    # "Show me that" after a solve asks for its working, as main gave it (review, 2026-11-10).
    for shown in ("Show me that", "show it", "show this"):
        assert maybe_direct_math_reply(verified, shown) != reply
