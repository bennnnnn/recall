"""A law solved for any one of its quantities (``law_binding.inverse``).

A toy subject drives the engine, so nothing here depends on physics' tables: SymPy
rearranges each law's own arithmetic, one solution or none, and the law as the binder
fills it keeps its identity while its result becomes one of its inputs.
"""

from __future__ import annotations

import math

import pytest

from app.services.law_binding.expression import Notation, evaluate
from app.services.law_binding.fit import read_question
from app.services.law_binding.inverse import (
    answered_by_its_own_law,
    can_solve_for,
    form_params,
    rearranged,
    solved_for,
    solved_input,
    stated_result,
    stated_strength,
)
from app.services.law_binding.spec import (
    Binding,
    FormulaVariant,
    formula,
    result_variable,
    var,
    variable_for,
)
from app.services.law_binding.units import UnitTable

_UNITS = UnitTable(
    {"J": "joule", "N": "newton", "m": "meter", "W": "watt", "s": "second", "kg": "kilogram"},
    {"mm": "millimeter"},
)
_NOTATION = Notation(constants={}, number=str)
_WORK = formula(
    "work",
    "energy",
    "Work formula",
    "W",
    base_latex="W = Fs",
    expression="F*d",
    variables=(var("F", "F", "newton"), var("d", "s", "meter")),
    binding=Binding(asks=("work done", "work"), result=("joule",), inputs=(frozenset({"F", "d"}),)),
)
_POWER = formula(
    "power",
    "energy",
    "Power formula",
    "P",
    base_latex="P = Fv",
    expression="F*v",
    variants=(
        FormulaVariant(present=frozenset({"W"}), latex=r"P = \frac{W}{t}", expression="W/t"),
    ),
    variables=(
        var("F", "F", "newton"),
        var("W", "W", "joule"),
        var("t", "t", "second"),
        var("v", "v", "meter / second"),
    ),
    binding=Binding(
        asks=("power",), result=("watt",), inputs=(frozenset({"W", "t"}), frozenset({"F", "v"}))
    ),
)


@pytest.mark.parametrize(
    ("expression", "unknown", "values", "expected"),
    [
        ("F*d", "d", {"R": 400.0, "F": 80.0}, 5.0),
        ("F*d", "F", {"R": 400.0, "d": 5.0}, 80.0),
        ("m/volume", "m", {"R": 2500.0, "volume": 4e-5}, 0.1),
        ("m/volume", "volume", {"R": 600.0, "m": 3.0}, 0.005),
        # A square takes its positive root: v = sqrt(2E/m), never its negative twin.
        ("1/2*m*v**2", "v", {"R": 100.0, "m": 2.0}, 10.0),
        ("m*g*h", "h", {"R": 40.0, "m": 2.0, "g": 9.81}, 40.0 / (2 * 9.81)),
        (
            "harmonic*v_wave/(mode_factor*L)",
            "v_wave",
            {"R": 150.0, "harmonic": 3.0, "mode_factor": 2.0, "L": 1.2},
            120.0,
        ),
        ("F*d*cos(angle)", "d", {"R": 50.0, "F": 10.0, "angle": math.pi / 3}, 10.0),
    ],
)
def test_rearranged_gives_the_input_back(
    expression: str, unknown: str, values: dict[str, float], expected: float
) -> None:
    inverse = rearranged(expression, "R", unknown)
    assert inverse is not None
    assert math.isclose(evaluate(inverse, values, _NOTATION), expected, rel_tol=1e-9)


@pytest.mark.parametrize(
    ("expression", "unknown"),
    [
        # Two launch angles reach one range: no one arithmetic.
        ("v**2*sin(2*angle)/g", "angle"),
        ("a*x**2 - b*x", "x"),
        # The input is in no term of the law.
        ("F*d", "m"),
        # A condition chooses between two forms; neither is the law to rearrange.
        ("a if a > 0 else b", "a"),
    ],
)
def test_rearranged_declines_without_one_solution(expression: str, unknown: str) -> None:
    assert rearranged(expression, "R", unknown) is None


def test_a_law_given_its_result_is_solved_for_the_input_left_out() -> None:
    stated = result_variable(_WORK)
    assert stated is not None
    assert (stated.name, stated.symbol, stated.words) == ("work", "W", ("work done", "work"))
    assert variable_for(_WORK, "work") == stated
    assert solved_input(_WORK, {"work": 400.0, "F": 80.0}) == variable_for(_WORK, "d")
    # Its own result asked: no input is solved for.
    assert solved_input(_WORK, {"F": 80.0, "d": 5.0}) is None


def test_the_law_as_filled_for_an_input_keeps_its_identity() -> None:
    solved = solved_for(_WORK, "d")
    assert solved is not None
    assert (solved.id, solved.law_name, solved.base_latex) == ("work", "Work formula", "W = Fs")
    assert solved.result_symbol == "s"
    assert solved.binding is not None
    assert solved.binding.inputs == (frozenset({"F", "work"}),)
    assert solved.binding.result == ("meter",)
    # The stated result takes only a value its words name.
    assert variable_for(solved, "work") is not None
    assert all(v.needs_words for v in solved.variables if v.name == "work")


def test_a_form_chosen_by_its_givens_is_rearranged_with_the_input_present() -> None:
    # P = Fv has no W; P = W/t, the form a stated work and time choose, has.
    assert can_solve_for(_POWER, "W")
    assert can_solve_for(_POWER, "t")
    assert form_params(_POWER, {"power": 600.0, "t": 10.0}) == {"power": 600.0, "t": 10.0, "W": 1.0}


def test_a_result_at_one_end_is_named_only_by_that_ends_words() -> None:
    boyle = formula(
        "boyle_pressure",
        "thermal",
        "Boyle's law",
        "P_2",
        expression="pres1*vol1/vol2",
        variables=(var("pres1", "P_1", "pascal"), var("vol1", "V_1", "meter ** 3")),
        binding=Binding(
            asks=("new pressure", "final pressure", "pressure"),
            result=("pascal",),
            inputs=(frozenset({"pres1", "vol1"}),),
        ),
    )
    stated = stated_result(boyle)
    assert stated is not None
    # "Its initial pressure was 100 kPa" states P₁; the bare noun names no end.
    assert stated.words == ("new pressure", "final pressure")
    # A result at no end keeps every word it is asked with.
    assert stated_result(_WORK) == result_variable(_WORK)


@pytest.mark.parametrize(
    ("text", "strength"),
    [
        ("An engine does 400 J of work with a force of 80 N. How far?", len("work")),
        ("The work done on the cart is 400 J by a force of 80 N. How far?", len("work done")),
        ("A force of 80 N and work = 400 J. How far?", len("work")),
        # The law's word elsewhere in the sentence labels no value.
        ("A cart that does work is pushed 400 J by a force of 80 N. How far?", 0),
        ("A force of 80 N acts. How far does it move?", 0),
    ],
)
def test_a_result_is_stated_when_its_words_label_its_value(text: str, strength: int) -> None:
    question = read_question(text, text.split(". ")[-1], _UNITS, max_givens=8)
    stated = result_variable(_WORK)
    assert question is not None and stated is not None
    assert stated_strength(stated, question, _UNITS) == strength


def test_a_direction_another_law_owns_is_left_to_it() -> None:
    mass_from_force = formula(
        "mass_from_force",
        "force",
        "Newton's second law",
        "m",
        expression="F/accel",
        variables=(var("F", "F", "newton"), var("accel", "a", "meter / second ** 2")),
        binding=Binding(asks=("mass",), result=("kilogram",), inputs=(frozenset({"F", "accel"}),)),
    )
    net_force = formula(
        "net_force",
        "force",
        "Newton's second law",
        "F",
        solve_for=(("F", "F"), ("m", "m"), ("a", "a")),
        variables=(
            var("F", "F", "newton"),
            var("a", "a", "meter / second ** 2"),
            var("m", "m", "kilogram"),
        ),
    )
    force = variable_for(mass_from_force, "F")
    assert force is not None
    # F = ma is net_force's, with its own checks ("a spring", "centripetal").
    assert answered_by_its_own_law(mass_from_force, force, (mass_from_force, net_force))
    assert not answered_by_its_own_law(mass_from_force, force, (mass_from_force, _WORK))
