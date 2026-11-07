"""A short line after a physics problem replays that problem, or declines."""

import pytest

from app.modules.physics.extract import extract_physics_intent
from app.modules.physics.followup import PHYSICS_FOLLOWUP_HINT, _restated, physics_followup_problem
from app.tests.modules.physics.test_physics_binding import _answer


def test_followup_hint_never_compares_with_the_earlier_answer() -> None:
    # "And after 10 s?" opened with "The previous result of 30 m/s corresponds to
    # a time of 10 s, not 5 s".
    assert "never compare it with or comment on the earlier answer" in PHYSICS_FOLLOWUP_HINT
    assert "changed given under Given" in PHYSICS_FOLLOWUP_HINT


_DROP = "A ball is dropped from 80 m. Find its speed just before it hits the ground."
_FORCE = "A block of mass 5 kg accelerates at 2 m/s^2. Find the force."
_LAUNCH = "A projectile is launched at 20 m/s at 30 degrees. Find the maximum height."


def _recent(problem: str) -> list[tuple[str, str]]:
    return [("user", problem), ("assistant", "Here is the working.")]


def test_an_explanation_replays_the_previous_problem() -> None:
    for line in (
        "why",
        "how",
        "why is it 40 m/s",
        "I didn't get it",
        "help me understand it",
        "that's confusing",
    ):
        assert physics_followup_problem(line, _recent(_DROP)) == _DROP


def test_another_quantity_keeps_the_givens_and_changes_the_ask() -> None:
    rewritten = physics_followup_problem("what about the range", _recent(_LAUNCH))
    assert rewritten is not None
    intent = extract_physics_intent(rewritten)
    assert intent is not None and intent.physics_op == "range"
    assert "20 m/s" in rewritten


def test_one_changed_given_is_replaced_and_resolved() -> None:
    rewritten = physics_followup_problem("but if it was 2 kg", _recent(_FORCE))
    assert rewritten is not None
    assert "5 kg" not in rewritten
    assert "2 kg" in rewritten
    assert _answer(rewritten) == "4 N"


def test_a_named_replacement_uses_that_quantity() -> None:
    rewritten = physics_followup_problem("if the mass is 2 kg", _recent(_FORCE))
    assert rewritten is not None and _answer(rewritten) == "4 N"


def test_two_possible_replacements_decline() -> None:
    prior = "Masses of 3 kg and 6 kg collide. Find the reduced mass."
    assert physics_followup_problem("if the mass is 2 kg", _recent(prior)) is None


def test_a_new_problem_is_not_a_followup() -> None:
    fresh = "A 2 kg block is dropped from 10 m. Find the speed."
    assert physics_followup_problem(fresh, _recent(_DROP)) is None
    assert physics_followup_problem("what about the kinetic energy", _recent(_FORCE)) is None
    assert (
        physics_followup_problem("if the mass is 2 kg and the height is 10 m", _recent(_FORCE))
        is None
    )


def test_a_followup_after_a_non_physics_turn_declines() -> None:
    recent = [("user", "Solve 2x + 3 = 11"), ("assistant", "x = 4")]
    assert physics_followup_problem("why is it 4", recent) is None


_CAR = "A car accelerates from rest at 3 m/s^2 for 5 s. What is its final velocity?"
_BALL = "A 2 kg ball is dropped from 20 m. How fast is it moving when it hits the ground?"


@pytest.mark.parametrize(
    ("prior", "line", "answer"),
    [
        # Another quantity of the same setup, asked as a question.
        (_CAR, "how far does it go?", "37.5 m"),
        (_BALL, "how long does it take?", "2.02 s"),
        # The same result in another unit.
        (_CAR, "in km/h please", "54 km/h"),
        (_CAR, "what is that in mph", "33.6 mph"),
        (_BALL, "in km/h", "71.3 km/h"),
        # One given replaced by a new value, named or not.
        (_CAR, "and after 10 s?", "30 m/s"),
        (_CAR, "what about after 10 s", "30 m/s"),
        (_BALL, "what if it's dropped from 80 m?", "39.6 m/s"),
        (_BALL, "and from 80 m?", "39.6 m/s"),
        # One given scaled.
        (_CAR, "what if the acceleration doubles?", "30 m/s"),
        (_BALL, "what if the mass doubles?", "19.8 m/s"),
        (_BALL, "what if the height is halved", "14 m/s"),
    ],
)
def test_physics_followup_reverifies_the_previous_problem(
    prior: str, line: str, answer: str
) -> None:
    rewritten = physics_followup_problem(line, _recent(prior))
    assert rewritten is not None
    assert _answer(rewritten) == answer


_CLIFF = "A stone is dropped from a 80 m cliff. How long to hit the water?"
_KE = "A 2 kg ball moves at 3 m/s. Find its kinetic energy."
_OHM = "A 12 V battery drives a 4 ohm resistor. Find the current."
_PUSH = "A 10 N force acts on a 2 kg box. Find its acceleration."


@pytest.mark.parametrize(
    ("prior", "line", "answer"),
    [
        # The quantity an adjective stands for: "twice as high" is the height.
        (_CLIFF, "now what if the cliff was twice as high?", "5.71 s"),
        (_CLIFF, "what if it was 3 times higher", "6.99 s"),
        (_KE, "what if it was twice as fast", "36 J"),
        (_KE, "half as heavy", "4.5 J"),
        # The quantity named with the factor.
        (_KE, "with twice the mass", "18 J"),
        (_KE, "if the speed was increased by a factor of 3", "81 J"),
        (_OHM, "what if the voltage were doubled", "6 A"),
        (_OHM, "what if I halve the resistance", "6 A"),
        (_PUSH, "and with 3 times the force", "15 m/s²"),
    ],
)
def test_a_scaling_said_any_common_way_reverifies_the_problem(
    prior: str, line: str, answer: str
) -> None:
    rewritten = physics_followup_problem(line, _recent(prior))
    assert rewritten is not None
    assert _answer(rewritten) == answer


_DROP_MASS = "A 2 kg ball is dropped from 10 m. Find its speed just before it hits the ground."
_SPEEDING = "A car moving at 10 m/s accelerates at 2 m/s^2 over 50 m. Find its final speed."
_THROWN = "A ball is thrown horizontally at 10 m/s from a 20 m cliff. How long is it in the air?"
_TABLE = "A ball rolls off a 1.2 m high table at 3 m/s. How far from the table does it land?"
_TRAIN = "A train slows down to 10 m/s from 30 m/s over 200 m. Find its deceleration."
_FROM_TO = "A car accelerates from 10 m/s to 30 m/s in 5 s. Find its acceleration."
_DRIVER = "A 70 kg driver sits in a car braking at 5 m/s^2. Find the force on the driver."
_ELEVATOR = (
    "A 60 kg person stands in an elevator accelerating upward at 2 m/s^2. "
    "Find the normal force on the person."
)
_RAMP = "A 5 kg box rests on a ramp inclined at 30 degrees. Find the normal force on the box."
_SWUNG = (
    "A 0.5 kg ball tied to a 2 m string is swung in a horizontal circle at 4 m/s. Find the tension."
)
_SKIER = (
    "A 60 kg skier starts from rest at the top of a 20 m high slope. Find her speed at the bottom."
)
_BATTERY = "A 12 V battery is connected to a 4 ohm resistor. Find the current."
_GAS_C = "Find the pressure of 2 mol of an ideal gas in a 10 L container at 27 °C."
_GAS_K = "Find the pressure of 2 mol of an ideal gas in a 0.01 m^3 container at 300 K."
_GOING = "A car is going 30 m/s after accelerating at 4 m/s^2 for 5 s. What was its starting speed?"
_TO_SPEED = (
    "A car starts from rest and accelerates at 3 m/s^2 until it reaches 30 m/s. "
    "How long does it take?"
)


@pytest.mark.parametrize(
    ("prior", "line", "answer"),
    [
        # The noun the line names is the quantity; "higher" only says which way.
        (_DROP_MASS, "what if the mass was 3 times higher", "14 m/s"),
        (_DROP_MASS, "what if the mass was twice as high", "14 m/s"),
        (_DROP_MASS, "what if it was twice as high", "19.8 m/s"),
        (_THROWN, "what if the speed was twice as high", "2.02 s"),
        (_TABLE, "what if the speed was 3 times higher", "4.45 m"),
        # Initial and final name the value that says so.
        (_TRAIN, "what if the initial speed doubled", "-8.75 m/s²"),
        (_TRAIN, "what if the final speed doubled", "-1.25 m/s²"),
        (_FROM_TO, "what if the initial speed was 5 m/s", "5 m/s²"),
        # An object that owns the given, beside its value.
        (_DRIVER, "what if the driver was twice as heavy", "700 N"),
        (_SKIER, "what if the slope was twice as high", "28 m/s"),
        (_BATTERY, "what if the battery had twice the voltage", "6 A"),
        # Kelvin scales; a gas at 27 °C keeps its other givens.
        (_GAS_K, "what if the temperature doubled", "9.98 × 10⁵ Pa"),
        (_GAS_C, "what if the volume was halved", "9.85 atm"),
        (_TO_SPEED, "what if the final speed doubled", "20 s"),
    ],
)
def test_a_scaling_names_the_quantity_the_student_wrote(prior: str, line: str, answer: str) -> None:
    rewritten = physics_followup_problem(line, _recent(prior))
    assert rewritten is not None
    assert _answer(rewritten) == answer


@pytest.mark.parametrize(
    ("prior", "line"),
    [
        # Where it went is the answer, not a given.
        (_TABLE, "what if it went twice as far"),
        (_TABLE, "what if it landed twice as far"),
        (_TABLE, "twice as far"),
        # A speed of something the problem never had.
        (_TABLE, "what if it rolled at double the speed of sound"),
        (_KE, "half the speed of light"),
        (_KE, "twice the mass of the earth"),
        # A verb that is not the speed's: acceleration, falling, braking, spinning.
        (_TO_SPEED, "what if it accelerated twice as fast"),
        (_TO_SPEED, "what if it fell twice as fast"),
        (_TO_SPEED, "what if it braked twice as fast"),
        (_TO_SPEED, "what if it slowed down twice as fast"),
        (_TO_SPEED, "what if it decelerated twice as fast"),
        (_TO_SPEED, "what if it spun twice as fast"),
        # It starts from rest: the 30 m/s it reaches is no initial speed.
        (_TO_SPEED, "what if the initial speed doubled"),
        (_TO_SPEED, "with twice the initial speed"),
        # The object named does not own the given: the driver's 70 kg is not the car's.
        (_DRIVER, "what if the car was twice as heavy"),
        (_DRIVER, "what if the car had twice the mass"),
        (_DRIVER, "what if the mass of the car doubled"),
        (_ELEVATOR, "what if the elevator was twice as heavy"),
        (_ELEVATOR, "what if the elevator had twice the mass"),
        (_ELEVATOR, "what if the mass of the elevator doubled"),
        (_RAMP, "what if the ramp was twice as heavy"),
        (_RAMP, "what if the ramp had twice the mass"),
        (_SWUNG, "what if the string was twice as heavy"),
        (_SWUNG, "what if the string had twice the mass"),
        (_DROP_MASS, "what if the ball was twice as high"),
        # A body the problem never had, or "we".
        (_DROP_MASS, "what if the earth had twice the mass"),
        (_DROP_MASS, "what if the planet had twice the mass"),
        (_DROP_MASS, "what if the moon had twice the mass"),
        (_DROP_MASS, "what if the mass of the earth doubled"),
        (_DROP_MASS, "what if we had twice the mass"),
        # A string's 2 m is no height and no distance.
        (_SWUNG, "what if the height doubled"),
        (_SWUNG, "what if the distance doubled"),
        # 27 °C doubled is not 54 °C.
        (_GAS_C, "what if the temperature doubled"),
        (_GAS_C, "with twice the temperature"),
        (_GAS_C, "at twice the temperature"),
        # A named given of the kind the problem asks for may be the answer's.
        (_TABLE, "what if the distance doubled"),
        (_TABLE, "what if the range doubled"),
        (_TABLE, "with twice the distance"),
        (_TABLE, "what if the horizontal distance doubled"),
        (_TABLE, "what if the table was twice as high"),
        # "moving at", "rolls off at" say no end of a change.
        (_TABLE, "what if the initial speed doubled"),
        (_KE, "what if the initial speed doubled"),
        (_SPEEDING, "what if the speed was twice as high"),
        (_SPEEDING, "what if the initial speed doubled"),
        (_GOING, "what if the initial speed doubled"),
        (_GOING, "what if the initial speed was 20 m/s"),
        (_GOING, "what if it was going twice as fast"),
        (_GOING, "what if the final speed doubled"),
        (_CLIFF, "double it"),
        (_CLIFF, "make it twice as long"),
        (_KE, "what if the mass doubles and the speed triples"),
        (_KE, "is it twice as much fun"),
        # No length is given to scale: the distance is what it asks.
        (_KE, "twice as far"),
    ],
)
def test_a_scaling_look_alike_is_not_reverified(prior: str, line: str) -> None:
    assert physics_followup_problem(line, _recent(prior)) is None


@pytest.mark.parametrize(
    "line", ["show steps", "show me the working", "explain it", "step by step"]
)
def test_physics_followup_asks_for_working_replay_the_problem(line: str) -> None:
    assert physics_followup_problem(line, _recent(_CAR)) == _CAR


@pytest.mark.parametrize(
    ("prior", "line"),
    [
        # No velocity was given: "from rest" is not a value to replace.
        (_CAR, "what if it starts at 2 m/s instead?"),
        # A clock time is not a length, though the ball has one length given.
        (_BALL, "and at 5 pm?"),
        # A unit of another kind, or not a unit at all.
        (_CAR, "in kg"),
        (_CAR, "in decimals please"),
        # "it" names no given to scale.
        (_BALL, "what if it doubles?"),
        # Not a follow-up shape: the model explains.
        (_BALL, "why doesn't mass matter?"),
    ],
)
def test_physics_followup_declines_what_it_cannot_reverify(prior: str, line: str) -> None:
    assert physics_followup_problem(line, _recent(prior)) is None


_CAR_FROM_ZERO = "a car goes from 0 to 20 m/s in 5 seconds. whats the acceleration"


def test_how_far_in_that_time_asks_the_same_car() -> None:
    rewritten = physics_followup_problem("how far did it go in that time", _recent(_CAR_FROM_ZERO))
    assert rewritten is not None
    assert _answer(rewritten) == "50 m"


_CAR = "car going 72 km/h slams the brakes and stops in 4 s. whats the deceleration and how far does it go"


def test_the_same_braking_keeps_the_deceleration_not_the_time() -> None:
    # Live (2026-11-05): kept 4 s and answered 55.56 m; the same braking is 5 m/s², 77.2 m.
    line = "ok and if it was going 100 km/h with the same braking, how far then"
    problem = physics_followup_problem(line, _recent(_CAR))
    assert problem is not None
    assert "4 s" not in problem and "100 km/h" in problem
    assert _solved(problem) == ["77.2 m"]


def test_a_kept_quantity_is_not_asked_again() -> None:
    problem = physics_followup_problem("same braking but from 90 km/h", _recent(_CAR))
    assert problem is not None
    assert _solved(problem) == ["62.5 m"]


def test_a_changed_value_with_two_readings_declines() -> None:
    # Keeping the 4 s gives 55.6 m and keeping the deceleration 77.2 m: not one answer.
    assert (
        physics_followup_problem("and if it was going 100 km/h, how far then", _recent(_CAR))
        is None
    )


def test_a_change_with_nothing_derived_to_hold_still_replays() -> None:
    prior = "A 2 kg ball moves at 3 m/s. What is its kinetic energy?"
    problem = physics_followup_problem("what if the mass was 4 kg", _recent(prior))
    assert problem is not None and _solved(problem) == ["18 J"]


def test_a_remark_holding_a_value_is_not_a_followup() -> None:
    prior = "A 2 kg ball falls from 20 m. How fast is it going when it hits the ground?"
    assert physics_followup_problem("my car weighs 1500 kg lol", _recent(prior)) is None


def test_what_about_a_new_amount_replays_the_problem_before_it() -> None:
    prior = "How much heat is needed to raise 50 g of water by 10 °C? (c=4.18)"
    problem = physics_followup_problem("what about 100 g of water", _recent(prior))
    assert problem is not None and "100 g" in problem and "?." not in problem


_RESISTOR = "12V battery connected to a 4 ohm resistor. current?"


@pytest.mark.parametrize(
    "line",
    [
        # Live sweep (hf-019): restated as the same 4 Ω and answered 3 A; in series it is 1.5 A.
        "now add another 4 ohm in series",
        "and with a 6 ohm in parallel",
        "now 3 resistors of 4 ohm",
    ],
)
def test_an_added_part_is_not_a_replaced_given(line: str) -> None:
    assert physics_followup_problem(line, _recent(_RESISTOR)) is None


def test_a_new_part_instead_replaces_the_given() -> None:
    problem = physics_followup_problem("with a 6 ohm resistor instead", _recent(_RESISTOR))
    assert problem is not None and _solved(problem) == ["2 A"]


def _solved(problem: str) -> list[str]:
    from app.core.config import get_settings
    from app.modules.physics.prompt import solve_physics_request

    outcome, block = solve_physics_request(problem, get_settings(), True)
    assert outcome == "verified" and block is not None
    return [part.answer for part in block.physics_parts] or [block.canonical_answer or ""]


def test_two_new_values_of_one_kind_decline() -> None:
    # "from 10 m/s to 20 m/s" has no single earlier speed each replaces: replacing one
    # after the other kept only the last and verified a wrong start speed.
    prior = "A car starts at 5 m/s and accelerates at 2 m/s² for 4 s. How far does it go?"
    assert _restated(prior, "what if it went from 10 m/s to 20 m/s instead") is None


def test_two_new_values_of_different_kinds_both_take_their_place() -> None:
    prior = "A car starts at 5 m/s and accelerates at 2 m/s² for 4 s. How far does it go?"
    restated = _restated(prior, "what if it started at 10 m/s and went for 6 s instead")
    assert restated is not None
    assert "10 m/s" in restated and "6 s" in restated
    assert "5 m/s" not in restated and "4 s" not in restated
