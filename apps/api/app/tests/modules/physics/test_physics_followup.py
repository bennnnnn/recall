"""A short line after a physics problem replays that problem, or declines."""

from app.modules.physics.extract import extract_physics_intent
from app.modules.physics.followup import physics_followup_problem
from app.tests.modules.physics.test_physics_binding import _answer

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
