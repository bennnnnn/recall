"""One pattern for "the message defines a function", asked by every maths reader of one.

Four regexes had drifted (audit, 2026-11-25): the function-analysis extractor took "F(x) ="
but not "2f(x) =", the value reader and the tool check took "2f(x) =" (an equation in f(x),
not a definition) but the value reader not "F(x) =", and the graph reader only lower case.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.math.function_names import FUNCTION_DEFINITION
from app.modules.math.tool_check import _UserMath, tool_call_matches_user_text
from app.modules.math.tools.school.function_value import extract_function_value_intent

_MATH = Path(__file__).resolve().parents[3] / "modules" / "math"


@pytest.mark.parametrize(
    ("text", "defined"),
    [
        ("f(x) = x^2 - 3", ("f", "x")),
        ("Let g ( t )=3t + 1", ("g", "t")),
        ("F(x) = 2x", ("F", "x")),
        ("2f(x) = 6", None),
        ("if f(x) == 3", None),
        ("half of(x) = 4", None),
        ("f(2) = 5", None),
    ],
)
def test_a_definition_is_one_letter_of_one_letter(text: str, defined: tuple | None) -> None:
    match = FUNCTION_DEFINITION.search(text)
    assert (None if match is None else (match["name"], match["var"])) == defined


def test_the_value_reader_and_the_tool_check_agree() -> None:
    question = "If f(x) = 2x + 1, find f(3)."
    assert extract_function_value_intent(question) is not None
    assert _UserMath(question).functions == {"f"}
    assert "F" in _UserMath("F(x) = 2x").functions
    # "2f(x) = 6" is an equation in f(x): no reader takes it for a definition...
    assert extract_function_value_intent("2f(x) = 6, find f(3)") is None
    # ...but it applies f, which the tool check's guard asks: a model's "2*f(x)" is never
    # read as 2·f·x and checked against the user's own equation (review, #2591).
    assert _UserMath("If 2f(x) = 4x + 6, find f(x)").functions == {"f"}


def test_a_call_that_reads_an_applied_function_as_a_product_is_never_checked() -> None:
    question = "If 2f(x) = 4x + 6, find f(x)"
    assert not tool_call_matches_user_text(
        {"action": "solve", "lhs": "2*f(x)", "rhs": "4*x+6"}, [question]
    )


@pytest.mark.parametrize(
    ("path", "shared"),
    [
        ("tools/extractors/functions.py", "FUNCTION_DEFINITION"),
        ("tools/school/function_value.py", "FUNCTION_DEFINITION"),
        ("match/graph.py", "FUNCTION_DEFINITION"),
        ("tool_check.py", "FUNCTION_APPLIED"),
    ],
)
def test_every_function_reader_takes_the_shared_pattern(path: str, shared: str) -> None:
    """Each of the four readers imports its pattern from ``function_names`` and writes no
    "f(x) =" pattern of its own (review, #2591: a literal search passed a restored copy)."""
    source = (_MATH / path).read_text(encoding="utf-8")
    assert "from app.modules.math.function_names import" in source and shared in source
    # Every copy that drifted closed its "f(x)" on this: ``\)\s*=``.
    assert r"\)\s*=" not in source, path
