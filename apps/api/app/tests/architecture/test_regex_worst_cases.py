"""No regex takes more than linear time on a message's worst case (ReDoS).

``regexploit`` (2026-11-13) found 15 of the API's 3,260 regexes that backtrack in cubic or
quartic time on a run of spaces after a cue: "average value of" and 2,000 spaces took over
20 s, "answer" and 500 spaces 16 s. Read as compiled (a pattern built from pieces whole), 13
more did ("slope of" and 250 spaces took 2.3 s), and CodeQL found three quadratic ones ("mu"
and 16,000 spaces took 2 s). A message may hold 32,000 characters, and a model's reply as
many. Each is held here to its worst case at 20,000 characters, read as the code reads it; CI
rates every compiled regex with the same tool (``scripts/check_regex_redos.py``).
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable

import pytest

from app.gateways import text_tool_calls
from app.modules.chat import follow_up_repeats, reply_labels
from app.modules.chemistry.extractors import electrochemistry, isotope_average, isotope_question
from app.modules.math import followup, function_calls, reading
from app.modules.math.tools import direct_calculus
from app.modules.math.tools.extractors import calculus_methods
from app.modules.math.tools.school import (
    algebra_facts,
    curve_point_patterns,
    function_value,
    shopping,
    trig,
)
from app.modules.math.tools.school.equation_features import count_conditions, extract
from app.modules.math.tools.school.geometry_measures import rules
from app.modules.physics import motion, net_force
from app.modules.physics.extractors import friction
from app.modules.physics.symbolic import request
from app.modules.turn_reading import answer_subject, visuals
from app.modules.web_search import source_quality
from app.services import latex_markup

# They assert on the wall clock, so CI runs them alone (``test_wall_clock_marks``).
pytestmark = pytest.mark.wall_clock

_N = 20_000
_SECONDS = 0.25
_SPACES = " " * _N
_EXTREME_ANGLE = dict(rules._RULES)["extreme_angle"]

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
    ("tangent", lambda: curve_point_patterns.TANGENT.fullmatch("tangent to" + _SPACES + "!")),
    ("gradient", lambda: curve_point_patterns.GRADIENT_AT.fullmatch("slope of" + _SPACES + "!")),
    ("rises", lambda: curve_point_patterns.MONOTONIC.fullmatch("where is" + _SPACES + "!")),
    ("status page", lambda: source_quality._STATUS_PAGE.fullmatch("404" + _SPACES + "x")),
    ("radian domain", lambda: trig._BOUNDED_RADIAN_DOMAIN.search("on" + _SPACES + "!")),
    ("triangle sides", lambda: _EXTREME_ANGLE.search("triangle side 0," + "0" * _N + "!")),
    ("value at", lambda: function_value._AT_VALUE.fullmatch("find" + _SPACES + "!")),
    ("values after", lambda: function_value._VALUES_AFTER.fullmatch("find" + _SPACES + "!")),
    ("between", lambda: count_conditions._BETWEEN.sub(" ", "between 0 and 5" + _SPACES + "!")),
    ("integral", lambda: direct_calculus._UNICODE_INTEGRAL.fullmatch("∫[0,0]" + _SPACES + "\n")),
    ("claim tail", lambda: followup._CLAIM_TAIL.sub("", _SPACES + "0", count=1)),
    (
        "asks the average",
        lambda: isotope_question._ASKS_THE_AVERAGE.fullmatch(
            "calculate the atomic mass from" + _SPACES + "find"
        ),
    ),
    ("couple", lambda: list(electrochemistry._COUPLE.finditer("A+/A" + _SPACES + "!"))),
    ("friction coefficient", lambda: net_force.friction_coefficients("mu" + _SPACES + "x")),
    ("ends at rest", lambda: motion.read_motion("until" + _SPACES + "x")),
    ("space before a mark", lambda: latex_markup._SPACE_BEFORE_MARK.sub("", "x" + _SPACES + "y")),
    ("congruences", lambda: function_calls.written_functions("a " * (_N // 2))),
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


def _groups(match: re.Match[str] | None) -> object:
    return None if match is None else match.groupdict() or match.groups()


# Each reading as it was before its patterns were rewritten, and look-alikes beside it.
_READINGS: list[tuple[Callable[[], object], object]] = [
    (
        lambda: _groups(curve_point_patterns.TANGENT.fullmatch("tangent to y = x^2 at x = 3")),
        {"kind": "tangent", "expr": "x^2", "x": "3", "px": None, "py": None},
    ),
    (
        lambda: _groups(
            curve_point_patterns.GRADIENT_AT.fullmatch(
                "gradient of the curve y = x^3 - 2x at (1, -1)"
            )
        ),
        {"expr": "x^3 - 2x", "x": None, "px": "1", "py": "-1"},
    ),
    (
        lambda: _groups(
            curve_point_patterns.MONOTONIC.fullmatch(
                "find the intervals where y = x^2 - 4x is decreasing"
            )
        ),
        {"expr": None, "way": None, "expr2": "x^2 - 4x", "way2": "decreasing"},
    ),
    (
        lambda: (
            source_quality._STATUS_PAGE.fullmatch("Attention Required! | Cloudflare") is not None
        ),
        True,
    ),
    (lambda: source_quality._STATUS_PAGE.fullmatch("Forbidden | Netflix") is not None, False),
    (
        lambda: _groups(
            trig._BOUNDED_RADIAN_DOMAIN.search("solve sin x = 0.5 for 0 <= x <= 2 * pi.")
        ),
        ("0", "<=", "x", "<=", "2 * pi"),
    ),
    (
        lambda: _groups(
            _EXTREME_ANGLE.search("a triangle has sides 3, 4 and 5, find its largest angle")
        ),
        ("3", "4", "5", "largest"),
    ),
    # A run of digits is one number: "3, 45 cm" was read as the sides 3, 4 and 5.
    (lambda: _EXTREME_ANGLE.search("a triangle has sides 3, 45 cm: find its largest angle"), None),
    (
        lambda: _groups(function_value._AT_VALUE.fullmatch("find x^2 + 1 when x = 3")),
        {"expr": "x^2 + 1", "var": "x", "value": "3"},
    ),
    (
        lambda: [m.groups() for m in count_conditions._BETWEEN.finditer("for x between 0 and 5 .")],
        [("0", "5 ")],
    ),
    (
        lambda: _groups(direct_calculus._UNICODE_INTEGRAL.fullmatch("∫[0, 1] x^2 dx")),
        ("0", "1", "x^2", "x"),
    ),
    (lambda: followup._CLAIM_TAIL.sub("", "x = 6 , correct ?", count=1), "x = 6"),
    (
        lambda: (
            isotope_question._ASKS_THE_AVERAGE.fullmatch(
                "calculate the average atomic mass of boron from the data and compare it with the "
                "value in the periodic table"
            )
            is not None
        ),
        True,
    ),
    (
        lambda: isotope_question._ASKS_THE_AVERAGE.fullmatch(
            "calculate the atomic mass from the data and find the mass number"
        ),
        None,
    ),
    (
        lambda: [m["volts"] for m in electrochemistry._COUPLE.finditer("E°(Cu2+/Cu) = 0.34 V")],
        ["0.34"],
    ),
    (
        lambda: net_force.friction_coefficients("μk = 0.3 on a ramp, mu_s is 0.5"),
        ((5, 0.3), (28, 0.5)),
    ),
    (lambda: motion.read_motion("it brakes until  stationary").ends_at_rest, True),
    (lambda: latex_markup._SPACE_BEFORE_MARK.sub("", "a , b ( c ) d  ."), "a, b (c) d."),
    (lambda: function_calls.written_functions("x ≡ 2 mod 5, y ≡ 3 mod 7")["congruence"], 2),
    (lambda: function_calls.written_functions("17 ≡ 2 mod 5")["congruence"], 0),
]


@pytest.mark.parametrize(("read", "expected"), _READINGS)
def test_a_rewritten_pattern_reads_what_it_read(
    read: Callable[[], object], expected: object
) -> None:
    assert read() == expected
