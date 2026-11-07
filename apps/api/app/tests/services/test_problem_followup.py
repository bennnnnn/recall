"""The follow-up shapes physics and chemistry share read only what they can name."""

import pytest

from app.modules.physics.givens import PHYSICS_UNITS
from app.services.law_binding.fit import read_givens
from app.services.law_binding.units import unit_dimension
from app.services.problem_followup import (
    GivenRewriter,
    asked_unit,
    changes_relatively,
    continues,
    new_value,
    remove_given,
    same_quantities,
    scaled_value,
    with_sentences,
)
from app.services.scaled_followup import Scaling, plays_role, scaled_given, scaled_name


@pytest.mark.parametrize(
    ("line", "unit"),
    [
        ("in km/h", "km/h"),
        ("in km/h please", "km/h"),
        ("what is that in mph", "mph"),
        ("convert it to feet", "feet"),
        ("give the answer in kN", "kN"),
        ("why", None),
        ("in 10 s", None),
    ],
)
def test_asked_unit_reads_the_unit_alone(line: str, unit: str | None) -> None:
    assert asked_unit(line) == unit


@pytest.mark.parametrize(
    ("line", "found"),
    [
        ("what if the mass doubles", ("mass", None, 2.0)),
        ("what if the height is halved", ("height", None, 0.5)),
        ("and if the speed triples", ("speed", None, 3.0)),
        # The quantity an unambiguous adjective stands for.
        ("now what if the cliff was twice as high", ("cliff", "height", 2.0)),
        ("if it were three times as fast", (None, "speed", 3.0)),
        ("half as heavy", (None, "mass", 0.5)),
        ("what if it was 3 times higher", (None, "height", 3.0)),
        ("what if it was 3x higher", (None, "height", 3.0)),
        ("twice as far", (None, "distance", 2.0)),
        ("what if it was thrown twice as fast", (None, "speed", 2.0)),
        ("what if the tower were four times as tall", ("tower", "height", 4.0)),
        ("make it twice as high", (None, "height", 2.0)),
        # The quantity named after the factor.
        ("with twice the mass", ("mass", None, 2.0)),
        ("double the height", ("height", None, 2.0)),
        ("half the speed", ("speed", None, 0.5)),
        ("and with 3 times the force", ("force", None, 3.0)),
        ("what if it had twice the mass", ("mass", None, 2.0)),
        ("what about twice the mass", ("mass", None, 2.0)),
        ("what if I double the mass", ("mass", None, 2.0)),
        ("what if we halve the speed", ("speed", None, 0.5)),
        ("what if I cut the mass in half", ("mass", None, 0.5)),
        ("double the mass of the ball", ("mass of the ball", None, 2.0)),
        # The quantity named before the scaling.
        ("what if the mass were doubled", ("mass", None, 2.0)),
        ("what if the voltage is doubled", ("voltage", None, 2.0)),
        ("what if the resistance were halved instead", ("resistance", None, 0.5)),
        ("if the speed was increased by a factor of 3", ("speed", None, 3.0)),
        ("what if the speed was multiplied by a factor of 3", ("speed", None, 3.0)),
        ("what if the mass is multiplied by 3", ("mass", None, 3.0)),
        ("if the voltage were divided by 2", ("voltage", None, 0.5)),
        ("What If The Mass Doubles", ("mass", None, 2.0)),
        # A new value, not a scaling.
        ("what if the mass was 4 kg", None),
        # No quantity: a pronoun, or the factor alone.
        ("double it", None),
        ("twice", None),
        ("what if it was doubled", None),
        # An adjective that names no one quantity, or none at all.
        ("make it twice as long", None),
        ("what if it was twice as big", None),
        ("is it twice as much fun", None),
        # The noun the line names is the quantity; the adjective only says which way.
        ("what if the mass was 3 times higher", ("mass", "height", 3.0)),
        ("what if the speed was twice as high", ("speed", "height", 2.0)),
        ("if the ball were going twice as fast", ("ball", "speed", 2.0)),
        # "of" keeps what it belongs to, for the rewriter to find in the problem.
        ("what if it rolled at double the speed of sound", ("speed of sound", None, 2.0)),
        ("twice the mass of the earth", ("mass of the earth", None, 2.0)),
        ("with twice the initial speed", ("initial speed", None, 2.0)),
        # A verb that is not "is" or the motion a speed belongs to says something else.
        ("what if it accelerated twice as fast", None),
        ("what if it fell twice as fast", None),
        ("what if it braked twice as fast", None),
        ("what if it slowed down twice as fast", None),
        ("what if it decelerated twice as fast", None),
        ("what if it spun twice as fast", None),
        ("what if it went twice as far", None),
        ("what if it landed twice as far", None),
        ("what if it was thrown twice as high", None),
        # Two scalings, a negation, or no change at all.
        ("what if the mass doubles and the speed triples", None),
        ("twice as high and twice as fast", None),
        ("what if the mass was not doubled", None),
        ("what if it was 1 times as fast", None),
        ("what if it was 500 times higher", None),
    ],
)
def test_scaled_given_reads_the_named_quantity_and_factor(
    line: str, found: tuple[str | None, str | None, float] | None
) -> None:
    expected = None if found is None else Scaling(found[2], found[0], found[1])
    assert scaled_given(line) == expected


@pytest.mark.parametrize(
    ("line", "found"),
    [
        ("and after 10 s", ("10", "s")),
        ("what if it's dropped from 80 m", ("80", "m")),
        ("and 0.001 M", ("0.001", "M")),
        # A clock time is not a quantity.
        ("and at 5 pm", None),
        ("what about tomorrow at 9 am", None),
        # Two values, or no unit, is not one replaced given.
        ("what if it was 5 apples and 3 pears", None),
        ("and 10", None),
    ],
)
def test_new_value_reads_one_value_with_its_unit(line: str, found: tuple[str, str] | None) -> None:
    assert new_value(line) == found


@pytest.mark.parametrize(
    ("value", "factor", "written"), [(2.0, 2.0, "4"), (20.0, 0.5, "10"), (0.01, 2.0, "0.02")]
)
def test_scaled_value_writes_the_number_a_student_would(
    value: float, factor: float, written: str
) -> None:
    assert scaled_value(value, factor) == written


def _dimension(expression: str | None) -> str | None:
    reading = unit_dimension(expression or "")
    return None if reading is None else reading[0]


_NAMES = {"mass": "kilogram", "time": "second"}
_REWRITER = GivenRewriter(
    PHYSICS_UNITS,
    unit_dimension=lambda unit: _dimension(PHYSICS_UNITS.expression(unit)),
    phrase_dimension=lambda phrase: _dimension(_NAMES.get(phrase)),
    verifies=lambda text: "kg" in text,
)
_PRIOR = "A force of 10 N acts on a 2 kg mass. Find its acceleration."


@pytest.mark.parametrize(
    ("name", "value", "unit", "rewritten"),
    [
        ("the mass", "4", "kg", "A force of 10 N acts on a 4 kg mass. Find its acceleration."),
        (None, "3", "kg", "A force of 10 N acts on a 3 kg mass. Find its acceleration."),
        # The named quantity and the unit disagree, the unit names nothing,
        # no unit at all, or the problem has no given of that kind.
        ("the time", "4", "kg", None),
        (None, "4", "parsecs per fortnight", None),
        (None, "4", None, None),
        (None, "4", "s", None),
        # The rewrite does not change the text.
        (None, "2", "kg", None),
        # The rewrite does not verify.
        (None, "4", "g", None),
    ],
)
def test_given_rewriter_replaces_the_one_given_of_that_kind(
    name: str | None, value: str, unit: str | None, rewritten: str | None
) -> None:
    assert _REWRITER.changed(_PRIOR, name, value, unit) == rewritten


def test_given_rewriter_scales_the_one_named_given() -> None:
    assert _REWRITER.scaled(_PRIOR, Scaling(2.0, "the mass", None)) == (
        "A force of 10 N acts on a 4 kg mass. Find its acceleration."
    )
    assert _REWRITER.scaled(_PRIOR, Scaling(2.0, "time", None)) is None
    assert _REWRITER.scaled(_PRIOR, Scaling(2.0, "speed", None)) is None


@pytest.mark.parametrize(
    ("line", "kept"),
    [
        ("ok and if it was going 100 km/h with the same braking, how far then", ["braking"]),
        ("same braking force but heavier", ["braking force"]),
        ("with the same acceleration and the same time", ["acceleration", "time"]),
        ("the same thing happens", []),
    ],
)
def test_same_quantities_read_the_longest_name(line: str, kept: list[str]) -> None:
    names = {"braking": "", "braking force": "", "acceleration": "", "time": ""}
    assert same_quantities(line, names) == kept


@pytest.mark.parametrize(
    ("text", "after"),
    [
        ("A car stops in 4 s. How far does it go?", "A car stops. How far does it go?"),
        ("A 2 kg ball moves at 3 m/s. Find its energy.", "A ball moves at 3 m/s. Find its energy."),
    ],
)
def test_remove_given_takes_its_value_unit_and_introducer(text: str, after: str) -> None:
    given = next(g for g in read_givens(text, PHYSICS_UNITS) if g.unit in {"s", "kg"})
    assert remove_given(text, given) == after


def test_with_sentences_states_before_the_ask_and_may_replace_it() -> None:
    prior = "A car going 72 km/h stops in 4 s. What is the deceleration and how far does it go"
    assert with_sentences(prior, ask="how far then", stated=("The acceleration is -5 m/s².",)) == (
        "A car going 72 km/h stops in 4 s. The acceleration is -5 m/s². how far then"
    )
    assert with_sentences(prior, ask=None, stated=()) == prior


def test_with_sentences_keeps_a_question_mark_inside() -> None:
    prior = "How much heat raises 50 g of water by 10 °C? (c=4.18)"
    assert with_sentences(prior, ask=None, stated=()) == (
        "How much heat raises 50 g of water by 10 °C? (c=4.18)."
    )


@pytest.mark.parametrize(
    ("line", "takes_up"),
    [
        ("ok and if it was going 100 km/h", True),
        ("what about 100 g of water", True),
        ("same braking but from 90 km/h", True),
        ("from 45 m instead", True),
        ("my car weighs 1500 kg lol", False),
        ("i drink 500 g of water a day", False),
        ("so my bike is 12 kg", False),
    ],
)
def test_continues_reads_a_line_that_takes_up_the_problem(line: str, takes_up: bool) -> None:
    assert continues(line) is takes_up


@pytest.mark.parametrize(
    ("line", "relative"),
    [
        ("now add another 4 ohm in series", True),
        ("what if it was 10 km/h faster", True),
        ("and 2 kg heavier", True),
        ("and 20 g more water", True),
        ("what about 100 g of water", False),
        ("with a 6 ohm resistor instead", False),
    ],
)
def test_changes_relatively_reads_an_addition_or_a_difference(line: str, relative: bool) -> None:
    assert changes_relatively(line) is relative


_IS_QUANTITY = {"mass", "speed", "height"}.__contains__


@pytest.mark.parametrize(
    ("scaling", "name"),
    [
        # A named quantity wins over the adjective.
        (Scaling(3.0, "mass", "height"), ("mass", False)),
        # An object of the problem takes its adjective's quantity; one it never had, nothing.
        (Scaling(2.0, "cliff", "height"), ("height", False)),
        (Scaling(2.0, "tower", "height"), None),
        (Scaling(2.0, None, "height"), ("height", True)),
        # "of" names the problem's quantity only when the problem has that object.
        (Scaling(2.0, "mass of the stone", None), ("mass", False)),
        (Scaling(2.0, "speed of sound", None), None),
        (Scaling(2.0, "mass of the earth", None), None),
    ],
)
def test_scaled_name_prefers_the_named_quantity(
    scaling: Scaling, name: tuple[str, bool] | None
) -> None:
    prior = "A 2 kg stone is dropped from a 80 m cliff. How long to hit the water?"
    assert scaled_name(prior, scaling, _IS_QUANTITY) == name


@pytest.mark.parametrize(
    ("prior", "name", "plays"),
    [
        (
            "A car starts from rest and accelerates at 3 m/s^2 until it reaches 30 m/s.",
            "initial speed",
            False,
        ),
        (
            "A car starts from rest and accelerates at 3 m/s^2 until it reaches 30 m/s.",
            "final speed",
            True,
        ),
        ("A car moving at 10 m/s accelerates at 2 m/s^2 over 50 m.", "initial speed", True),
        ("A car moving at 10 m/s accelerates at 2 m/s^2 over 50 m.", "speed", True),
        ("A car goes from 0 to 20 m/s in 5 s.", "final velocity", True),
    ],
)
def test_plays_role_matches_initial_and_final_to_their_values(
    prior: str, name: str, plays: bool
) -> None:
    # The last speed: "from 0 to 20 m/s" reads the 0 as a speed too.
    given = [g for g in read_givens(prior, PHYSICS_UNITS) if g.unit == "m/s"][-1]
    assert plays_role(prior, given, name) is plays
