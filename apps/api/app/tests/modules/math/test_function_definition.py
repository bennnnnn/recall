"""One pattern for "the message defines a function", asked by every maths reader of one.

Four regexes had drifted (audit, 2026-11-25): the function-analysis extractor took "F(x) ="
but not "2f(x) =", the value reader and the tool check took "2f(x) =" (an equation in f(x),
not a definition) but the value reader not "F(x) =", and the graph reader only lower case.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.math.function_names import FUNCTION_DEFINITION
from app.modules.math.tool_check import _UserMath
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
    # "2f(x) = 6" is an equation in f(x): no reader takes it for a definition.
    assert not _UserMath("2f(x) = 6").functions
    assert extract_function_value_intent("2f(x) = 6, find f(3)") is None


def test_no_maths_module_writes_its_own() -> None:
    pattern = r"\s*\(\s*([A-Za-z])\s*\)\s*="
    for path in _MATH.rglob("*.py"):
        if path.name != "function_names.py":
            assert pattern not in path.read_text(encoding="utf-8"), path
