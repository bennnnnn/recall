"""No regex takes more than linear time on a message's worst case (ReDoS).

``regexploit`` (2026-11-13) found 15 of the API's 3,260 regexes that backtrack in cubic or
quartic time on a run of spaces after a cue: "average value of" and 2,000 spaces took over
20 s, "answer" and 500 spaces 16 s. A message may hold 32,000 characters, and a model's reply
as many. Each is held here to its worst case at 20,000 characters, read as the code reads it;
CI scans every changed file's regexes with the same tool (``.github/workflows/api-ci.yml``).
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable

import pytest

from app.gateways import text_tool_calls
from app.modules.chat import follow_up_repeats, reply_labels
from app.modules.chemistry.extractors import isotope_average
from app.modules.math import reading
from app.modules.math.tools.extractors import calculus_methods
from app.modules.math.tools.school import algebra_facts, shopping
from app.modules.math.tools.school.equation_features import extract
from app.modules.physics.extractors import friction
from app.modules.physics.symbolic import request
from app.modules.turn_reading import answer_subject, visuals

_N = 20_000
_SECONDS = 0.25
_SPACES = " " * _N

_CASES: list[tuple[str, Callable[[], object]]] = [
    ("tool call key", lambda: text_tool_calls._ARGUMENT.findall("<arg_key>" + _SPACES)),
    ("answer heading", lambda: reply_labels._HEADING.match("answer" + _SPACES + "0")),
    ("value set", lambda: follow_up_repeats._SETS_A_VALUE.match(_SPACES)),
    ("value set, a unit", lambda: follow_up_repeats._SETS_A_VALUE.match("v = 5" + _SPACES + "+")),
    ("respectively", lambda: isotope_average._RESPECTIVELY.match(_SPACES)),
    ("root index", lambda: reading._SQRT_INDEX.sub("", "\\sqrt[" + _SPACES)),
    ("asks about", lambda: answer_subject.asked_about_subject("who's a" + _SPACES + '"')),
    ("where is", lambda: visuals.where_is_place("where" + _SPACES)),
    ("where is, a place", lambda: visuals.where_is_place("where is x" + _SPACES + '"')),
    ("average on", lambda: calculus_methods._AVERAGE_ON.search("average value of" + _SPACES)),
    (
        "average request",
        lambda: calculus_methods._AVERAGE_REQUEST.fullmatch("average value of" + _SPACES),
    ),
    ("shopping", lambda: shopping._CHANGE.fullmatch("I buy" + _SPACES)),
    ("complete the square", lambda: algebra_facts._COMPLETE_SQUARE.fullmatch(_SPACES)),
    ("remainder", lambda: algebra_facts._REMAINDER.fullmatch("the remainder when" + _SPACES)),
    ("parameter", lambda: extract._PARAMETER.fullmatch("find a if" + _SPACES)),
    ("integral limits", lambda: request._LIMITS.fullmatch("0 from" + _SPACES)),
    ("friction", lambda: [rx.search("mu" + _SPACES) for rx in friction._FRICTION_CUE_RES]),
]


@pytest.mark.parametrize(("name", "run"), _CASES, ids=[name for name, _ in _CASES])
def test_a_worst_case_message_reads_in_linear_time(name: str, run: Callable[[], object]) -> None:
    started = time.perf_counter()
    run()
    seconds = time.perf_counter() - started
    assert seconds < _SECONDS, f"{name}: {seconds:.2f}s on {_N} characters"


def test_the_rewritten_patterns_still_read_what_they_read() -> None:
    """Each group is the same words it was: a run of space is read once, never dropped."""
    assert text_tool_calls._ARGUMENT.findall(
        "<arg_key> city name </arg_key>\n<arg_value>Paris</arg_value>"
    ) == [("city name", "Paris")]
    assert reply_labels._HEADING.match("**Answer:**  ")
    assert reply_labels._HEADING.match("## Answer")
    setting = follow_up_repeats._SETS_A_VALUE.match("v_0 = 30\\text{ m/s}")
    assert setting is not None and setting.group(1) == "v_0"
    assert follow_up_repeats._SETS_A_VALUE.match("y = 3x + 1") is None
    assert reading._SQRT_INDEX.sub(lambda m: f"[{m.group(1)}|{m.group(2)}]", "\\sqrt[ 3 ]{x}") == (
        "[3|x]"
    )
    assert answer_subject.asked_about_subject("what is a capybara?") == "capybara"
    assert visuals.where_is_place("where is kenya located?") == "kenya"
    assert visuals.where_is_place("what country is Timbuktu in") == "Timbuktu"
    on = calculus_methods._AVERAGE_ON.search("average value of x^2 on [ 0 , 3 ]")
    assert on is not None and (on["expr"], on["lo"], on["hi"]) == ("x^2", "0", "3")
    square = algebra_facts._COMPLETE_SQUARE.fullmatch("x^2 + 6x + 5 by completing the square")
    assert square is not None and square["expr2"] == "x^2 + 6x + 5"
    square = algebra_facts._COMPLETE_SQUARE.fullmatch("x^2 + 6x + 5, by completing the square")
    assert square is not None and square["expr2"] == "x^2 + 6x + 5"
    parameter = extract._PARAMETER.fullmatch(
        "find k so that x^2 + kx + 9 = 0 has exactly one solution"
    )
    assert parameter is not None and parameter["equation"] == "x^2 + kx + 9 = 0"
    assert re.search(friction._FRICTION_GIVEN, "mu = 0.3", re.IGNORECASE)
    limits = request._LIMITS.fullmatch("x dx from 0 to 2")
    assert limits is not None and limits.groups() == ("x dx", "0", "2")
