"""The 60 hard physics questions of the 2026-11-21 live round: its wrong verified cards and
its false precision, by class.

- A stated result of a motion is never a starting condition, and values that contradict
  each other get no card (P59: "thrown straight up at 10 m/s reaches a maximum height of
  20 m" read 20 m as a launch height and verified t = v₀/g).
- A reader claims only a question whose asks it answers (P57: a helium-4 binding-energy
  question carded "Protons = 2, Neutrons = 2"); chemistry's ``test_hard_round`` holds that.
- The working ends on the value the solve reached, unrounded, so the card rounds once (P8:
  "v = 17.8" carded 17.80 for 17.76).
- The turn's read counts the asks a verified result falls short of (P30, P37): the physics
  adapter marks such a block partial (``chat.asks_turn`` waits for the read).
"""

from __future__ import annotations

import re

import pytest

from app.core.config import Settings
from app.modules.chat.card_numbers import card_numbers
from app.modules.physics.direct import maybe_direct_physics_reply
from app.modules.physics.extract import extract_physics_intent
from app.modules.physics.prompt import solve_or_say_why, solve_physics_request
from app.modules.physics.reply_policy import PHYSICS_PARTIAL_POLICY
from app.modules.physics.stated_peak import (
    stated_peak_conflict,
    without_redundant_peaks,
    without_stated_peaks,
)
from app.modules.physics.subject import PHYSICS_SUBJECT
from app.modules.physics.working_steps import carried_to_answer
from app.services.law_binding.reduction import reduce_substitution
from app.services.rounding_rule import RULE
from app.services.solving import VerifiedPhysicsBlock

_SETTINGS = Settings(_env_file=None, math_tools_enabled=True)  # type: ignore[call-arg]

P8 = (
    "A road curve of radius 120 m is banked at 15°. At what speed can a car take the curve "
    "with no friction needed?"
)
P30 = (
    "An ambulance siren emits 700 Hz. The ambulance moves at 30 m/s and the speed of sound "
    "is 343 m/s. What frequency does a stationary listener hear as it approaches, and as it "
    "moves away?"
)
P37 = (
    "Light of wavelength 550 nm falls on a diffraction grating with 600 lines per mm. Find "
    "the angle of the first-order maximum and the highest order that can be seen."
)
P59 = (
    "A ball thrown straight up at 10 m/s reaches a maximum height of 20 m. How long does it "
    "take to reach the top?"
)


def _verified(question: str) -> VerifiedPhysicsBlock:
    outcome, block = solve_physics_request(question, _SETTINGS, None)
    assert outcome == "verified" and block is not None, outcome
    return block


def _cards(text: str) -> list[str]:
    return re.findall(r"```answer\n(.*?)```", text, re.S)


# --- A stated top: a result of the motion, never where it starts --------------------------


@pytest.mark.parametrize(
    ("question", "conflict"),
    [
        # P59: 10 m/s rises 5.10 m, so the 20 m it states contradicts it.
        (P59, True),
        (
            "A ball thrown straight up at 10 m/s reaches a maximum height of 20 m. How long is it in the air?",
            True,
        ),
        # The values agree (20²/2g = 20.4 m): the question is answered.
        (
            "A ball is thrown straight up at 20 m/s and reaches a maximum height of 20.4 m. How long does it take to reach the top?",
            False,
        ),
        # g read as 10 m/s²: 20 m for 20 m/s is within the rounding the check allows.
        (
            "A stone is thrown straight up at 20 m/s and reaches a maximum height of 20 m. How long does it take to reach the top?",
            False,
        ),
        # A projectile's top: 20 m/s at 35° rises 6.71 m.
        (
            "A ball is kicked at 20 m/s at 35 degrees and reaches a maximum height of 16 m. Find its range.",
            True,
        ),
        (
            "A ball is kicked at 20 m/s at 35 degrees and reaches a maximum height of 6.7 m. Find its range.",
            False,
        ),
        # A height on the way up is no top, and a launch height is a launch height.
        ("A ball is thrown up at 25 m/s. How long does it take to reach a height of 20 m?", False),
        (
            "A ball is thrown straight up at 10 m/s from a height of 20 m. How long does it take to reach the top?",
            False,
        ),
    ],
)
def test_a_stated_top_is_checked_against_the_launch(question: str, conflict: bool) -> None:
    reason = stated_peak_conflict(question)
    assert (reason is not None) is conflict, reason
    if conflict:
        assert reason is not None and "contradict" in reason


def test_p59_has_no_answer_as_written_and_no_card() -> None:
    outcome, block, no_answer = solve_or_say_why(P59, _SETTINGS, None)
    assert block is None and no_answer is not None and no_answer.stated
    assert "5.1 m" in no_answer.note and "20 m" in no_answer.note
    assert "no answer" in no_answer.note
    assert outcome == "failed"


def test_a_consistent_top_is_read_out_and_the_launch_answers() -> None:
    question = (
        "A ball is thrown straight up at 20 m/s and reaches a maximum height of 20.4 m. "
        "How long does it take to reach the top?"
    )
    intent = extract_physics_intent(question)
    assert intent is not None and intent.physics_op == "time_to_peak"
    assert "h0" not in (intent.physics_params or {})
    block = _verified(question)
    assert "2.04" in (block.canonical_answer or "")


@pytest.mark.parametrize(
    ("text", "kept"),
    [
        # With a launch speed the top is a check, and goes.
        (P59, "A ball thrown straight up at 10 m/s. How long does it take to reach the top?"),
        # Without one it may be the given ("how fast was it thrown?"): kept for the readers.
        (
            "A ball thrown straight up reaches a maximum height of 20 m. How fast was it thrown?",
            "A ball thrown straight up reaches a maximum height of 20 m. How fast was it thrown?",
        ),
    ],
)
def test_a_top_beside_its_launch_is_read_out(text: str, kept: str) -> None:
    assert without_redundant_peaks(text) == kept


def test_a_stated_top_is_hidden_from_the_launch_height_reader() -> None:
    hidden = without_stated_peaks("It reaches a maximum height of 20 m from a 5 m ledge.")
    assert "20 m" not in hidden and "5 m" in hidden
    assert len(hidden) == len("It reaches a maximum height of 20 m from a 5 m ledge.")


# --- The working ends unrounded; the card rounds once -------------------------------------


@pytest.mark.parametrize(
    ("row", "value"),
    [
        # A root's closing brace after a degree sign is the root's (P8).
        (r"\sqrt{120 \times 9.81 \times \tan 15^\circ}", 17.7603),
        (r"\sqrt{\tan 15^{\circ}}", 0.5176),
        (r"\sqrt{2 \times 10^{5}}", 447.2136),
        (r"\sqrt{2 \times 10^5}", 447.2136),
    ],
)
def test_a_root_after_an_angle_or_a_power_is_read(row: str, value: float) -> None:
    from app.modules.physics.display import latex_working

    reduction = reduce_substitution("v", row, latex_working, None)
    assert reduction is not None and reduction.value == pytest.approx(value, rel=1e-4)


def test_p8_working_ends_unrounded_and_the_card_rounds_once() -> None:
    block = _verified(P8)
    reply = maybe_direct_physics_reply(block, P8)
    assert reply is not None
    assert "17.7603" in reply
    # The direct reply's card is marked verified when the turn saves it.
    assert [card.strip() for card in _cards(card_numbers(reply, RULE))] == [
        "v = 17.76\\,\\mathrm{m/s}"
    ]


def test_a_row_past_reading_closes_on_the_unrounded_value() -> None:
    """A row no reader reads still ends on the value the solve reached, never the card's."""
    rows = [r"v = \operatorname{law}(120, 9.81)"]
    assert carried_to_answer(rows, r"17.8\,\mathrm{m/s}", None, (17.7603,))[-1] == (
        r"v = 17.7603\,\mathrm{m/s}"
    )
    # With no value given, the rounded answer as before.
    assert carried_to_answer(rows, r"17.8\,\mathrm{m/s}")[-1] == r"v = 17.8\,\mathrm{m/s}"


@pytest.mark.parametrize(
    ("working", "card", "shown"),
    [
        # P1: a card of three values, each the rounding of a line the working reached.
        (
            "$t = 2.33874\\,\\mathrm{s}$\n$H = 6.70724\\,\\mathrm{m}$\n$R = 38.3157\\,\\mathrm{m}$",
            r"2.34\,\mathrm{s};\quad 6.71\,\mathrm{m};\quad 38.3\,\mathrm{m}",
            r"2.34\,\mathrm{s};\quad 6.71\,\mathrm{m};\quad 38.32\,\mathrm{m}",
        ),
        # P2: two values.
        (
            "$t = 4.03855\\,\\mathrm{s}$\n$R = 60.5783\\,\\mathrm{m}$",
            r"4.04\,\mathrm{s};\quad 60.6\,\mathrm{m}",
            r"4.04\,\mathrm{s};\quad 60.58\,\mathrm{m}",
        ),
        # A value no line reached keeps the rule's own reading of it.
        (
            "$t = 4.03855\\,\\mathrm{s}$",
            r"4.04\,\mathrm{s};\quad 60.6\,\mathrm{m}",
            r"4.04\,\mathrm{s};\quad 60.60\,\mathrm{m}",
        ),
    ],
)
def test_a_card_of_several_values_rounds_each_from_the_working(
    working: str, card: str, shown: str
) -> None:
    text = f"{working}\n\n**Answer**\n\n```answer\nverified: true\n{card}\n```\n"
    assert _cards(card_numbers(text, RULE)) == [f"verified: true\n{shown}\n"]


# --- A verified result the read says answers part of the question -------------------------


@pytest.mark.parametrize(("question", "asked"), [(P30, 2), (P37, 2)])
def test_a_result_answering_fewer_asks_than_read_is_partial(question: str, asked: int) -> None:
    block = _verified(question)
    assert not block.partial  # the word rules counted one ask
    found = PHYSICS_SUBJECT.answers_part(block, asked)
    assert found is not None
    partial, rule = found
    assert isinstance(partial, VerifiedPhysicsBlock) and partial.partial
    assert rule == PHYSICS_PARTIAL_POLICY


def test_a_result_answering_every_ask_is_whole() -> None:
    assert PHYSICS_SUBJECT.answers_part(_verified(P8), 1) is None
