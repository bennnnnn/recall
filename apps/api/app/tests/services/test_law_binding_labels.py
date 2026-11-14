"""A value named as a quantity fills only an input that is it, and a law takes only values
its quantities can have (``law_binding.labels``, ``law_binding.domains``).

Read by dimension alone, "an amplitude of 0.1 m and a period of 2 s" filled v = d/t's d and
t, and "a -5 Ω resistor" gave -2 A, each verified (audit 2026-11-13).
"""

from __future__ import annotations

import pytest

from app.services.law_binding.domains import outside_domain, outside_kind
from app.services.law_binding.fit import Question, Subject, fit, given_labels, read_givens
from app.services.law_binding.labels import CHANGE, QUALIFIED, holds, value_label
from app.services.law_binding.spec import Binding, FormulaSpec, VariableSpec, var
from app.services.law_binding.units import UnitTable, dimension_of

_UNITS = UnitTable({"m": "meter", "s": "second", "Ω": "ohm", "kg": "kilogram"}, {})
_SUBJECT = Subject(units=_UNITS, fallback=lambda *_: None, unit_of=lambda _: "")
_RATE = FormulaSpec(
    id="rate",
    kind="kinematics",
    law_name="Speed",
    result_symbol="v",
    variables=(var("d", "d", "meter"), var("t", "t", "second")),
    binding=Binding(asks=("speed",), result=("meter / second",), inputs=(frozenset({"d", "t"}),)),
)


@pytest.mark.parametrize(
    ("before", "after", "label"),
    [
        ("a mass oscillates with an amplitude of ", " ", "amplitude"),
        ("a spring has amplitude ", " and", "amplitude"),
        ("the amplitude a = ", "", "amplitude"),
        (" and a period of ", ". what", "period"),
        (" and takes ", " per cycle", "period"),
        ("light of wavelength ", " falls", "wavelength"),
        ("reaches an average speed of ", " over", "average speed"),
        # A qualified amplitude is another quantity: peak-to-peak is 2A.
        ("with a peak-to-peak amplitude of ", " and", QUALIFIED),
        ("with a double amplitude of ", " and", QUALIFIED),
        ("has its amplitude ", ".", "amplitude"),
        ("for a short period of ", ".", None),
        # Durations and plain values name nothing.
        ("a car covers 100 m over a period of ", ".", None),
        ("in a time period of ", ".", None),
        ("a runner moves ", " in", None),
        ("heated by a ", " heater", None),
        ("a spring is stretched by ", ".", None),
    ],
)
def test_value_label_names_the_quantity_the_words_give(
    before: str, after: str, label: str | None
) -> None:
    assert value_label(before, after) == label


@pytest.mark.parametrize(
    ("variable", "label", "held"),
    [
        (var("period", "T", "second"), "period", True),
        (var("t", "t", "second"), "period", False),
        (var("x", "A", "meter", words=("amplitude",)), "amplitude", True),
        (var("d", "d", "meter"), "amplitude", False),
        (var("delta_temp", r"\Delta T", "kelvin"), CHANGE, True),
        (var("delta_t", "dT", "kelvin"), CHANGE, True),
        (var("v", "v", "meter / second"), CHANGE, False),
        (var("d", "d", "meter"), None, True),
    ],
)
def test_only_the_named_quantity_holds_a_named_value(
    variable: VariableSpec, label: str | None, held: bool
) -> None:
    assert holds(variable, label) is held


def _fit(text: str) -> dict[str, float] | None:
    lower = text.lower()
    question = Question(
        text=text,
        lower=lower,
        givens=read_givens(text, _UNITS),
        asked=frozenset({dimension_of("meter / second") or ""}),
        asked_in=None,
        asked_from=lower.rfind("speed"),
    )
    filled = fit(_RATE, 1, question, _SUBJECT)
    return None if filled is None else filled.params


@pytest.mark.parametrize(
    ("text", "params"),
    [
        ("A runner moves 0.1 m in 2 s. What is her speed?", {"d": 0.1, "t": 2.0}),
        ("A spring oscillates with an amplitude of 0.1 m and a period of 2 s. Its speed?", None),
        ("A pendulum 1 m long has a period of 2 s. What is the bob's speed?", None),
    ],
)
def test_a_named_value_leaves_a_law_without_that_quantity_unfilled(
    text: str, params: dict[str, float] | None
) -> None:
    assert _fit(text) == params


@pytest.mark.parametrize(
    ("text", "labels"),
    [
        # A verb, then "by" or "through", beside a value of its kind stated before it.
        ("at 20 m/s it reduces its speed by 5 m/s in 2 s", (None, CHANGE, None)),
        ("a gas at 300 k is heated through 100 k", (None, CHANGE)),
        ("a gas at 300 k goes up by 100 k", (None, CHANGE)),
        # Nothing of its kind before it: the law's own value.
        ("its extension increases by 2 cm under a 4 n load", (None, None)),
        ("a 10 kg crate is pulled by 50 n", (None, None)),
        # No verb: dimensions, not a change.
        ("a rectangle 8 cm by 5 cm", (None, None)),
    ],
)
def test_a_change_is_a_value_said_by_a_verb_beside_one_of_its_kind(
    text: str, labels: tuple[str | None, ...]
) -> None:
    units = UnitTable(
        {"m/s": "meter / second", "s": "second", "k": "kelvin", "cm": "centimeter",
         "kg": "kilogram", "n": "newton"},
        {},
    )  # fmt: skip
    assert given_labels(text, read_givens(text, units)) == labels


def test_each_given_carries_its_label_in_order() -> None:
    text = "an amplitude of 0.1 m, a period of 2 s and 5 kg"
    assert given_labels(text, read_givens(text, _UNITS)) == ("amplitude", "period", None)


_PARTS = FormulaSpec(
    id="parts",
    kind="any",
    law_name="Parts",
    result_symbol="y",
    variables=(
        var("m", "m", "kilogram"),
        var("R", "R", "ohm"),
        var("T", "T", "kelvin"),
        var("delta_temp", r"\Delta T", "kelvin"),
        var("v", "v", "meter / second"),
        var("x", "x", "meter"),
        var("period", "T", "second"),
        # A spring's extension holds an amplitude by its words, and keeps its sign.
        var("ext", "x", "meter", words=("amplitude",)),
    ),
)


@pytest.mark.parametrize(
    ("values", "outside"),
    [
        ({"m": 5.0, "R": 4.0, "T": 300.0, "v": -20.0, "x": -0.1, "ext": -0.1}, None),
        ({"R": -5.0}, "R"),
        ({"m": 0.0}, "m"),
        ({"T": -26.85}, "T"),
        ({"period": -2.0}, "period"),
        ({"v": 4e8}, "v"),
        ({"v": -4e8}, "v"),
        # Light's school speed, a hair over c, and a change of temperature are fine.
        ({"v": 3e8, "delta_temp": -40.0}, None),
    ],
)
def test_a_value_no_such_quantity_takes_is_outside_the_law(
    values: dict[str, float], outside: str | None
) -> None:
    assert outside_domain(_PARTS, values) == outside


@pytest.mark.parametrize(
    ("unit", "value", "outside"),
    [
        ("kilogram", -5.0, True),
        ("ohm", -3.0, True),
        ("kilogram", 5.0, False),
        ("meter / second", 4e8, True),
        ("meter / second", -20.0, False),
        ("joule", -100.0, False),
    ],
)
def test_a_result_is_held_to_its_kinds_range(unit: str, value: float, outside: bool) -> None:
    assert outside_kind(dimension_of(unit), value) is outside
