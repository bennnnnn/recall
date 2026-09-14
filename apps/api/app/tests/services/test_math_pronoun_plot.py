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

import pytest

from app.services.math.match import graph_expr
from app.services.math.tools import extract_math_intent, needs_symbolic_math
from app.services.math.tools.extract import resolve_graph_followup


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
