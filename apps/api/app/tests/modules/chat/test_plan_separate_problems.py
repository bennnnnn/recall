"""Several problems in one message, each with its own setup and question (``plan_turn``).

"A car goes 100 m in 5 s; find its speed. A train goes 300 m in 10 s; find its speed." was
one request: the train's statement joined the car's question, "find its speed" pointed
back, and the whole line read as no subject's. The model wrote both answers unverified,
the part letters swapped. Each problem is now its own request, read with its own setup.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.core.readings import begin_turn
from app.modules.chat.turn_prep.intents import plan_turn
from app.modules.chat.turn_prep.problems import about_all, opens_problem, problem_clauses
from app.modules.chat.turn_prep.reading import read_turn_message
from app.modules.turn_reading.plan import solved_parts
from app.modules.turn_reading.turn import current_turn_reading


def _parts(text: str) -> list[tuple[str, str]]:
    return [(part.text, part.kind) for part in plan_turn(text).parts]


_CAR = "A car goes 100 m in 5 s. Find its speed."
_TRAIN = "A train goes 300 m in 10 s. Find its speed."


@pytest.mark.parametrize(
    ("text", "parts"),
    [
        (
            "A car goes 100 m in 5 s; find its speed. A train goes 300 m in 10 s; find its speed.",
            [_CAR, _TRAIN],
        ),
        (
            "A car travels 100 m in 5 s. Find its speed. A train travels 300 m in 10 s. Find "
            "its speed.",
            ["A car travels 100 m in 5 s. Find its speed.", _TRAIN.replace("goes", "travels")],
        ),
        # A question joined to its setup by a comma.
        (
            "A car goes 100 m in 5 s, find its speed. A train goes 300 m in 10 s, find its speed.",
            [_CAR, _TRAIN],
        ),
        # Lettered bodies, and a sentence that ends on a capital unit ("10 N.", "3 A.").
        (
            "Car A covers 150 m in 10 s. What is its speed? Car B covers 400 m in 20 s. What "
            "is its speed?",
            [
                "Car A covers 150 m in 10 s. What is its speed?",
                "Car B covers 400 m in 20 s. What is its speed?",
            ],
        ),
        (
            "A resistor of 4 Ω carries 3 A. Find the voltage across it. A 6 Ω resistor is "
            "connected to 12 V. Find the current.",
            [
                "A resistor of 4 Ω carries 3 A. Find the voltage across it.",
                "A 6 Ω resistor is connected to 12 V. Find the current.",
            ],
        ),
        (
            "A cyclist rides 600 m in 2 minutes; find her speed. A runner covers 400 m in 80 s; "
            "find his speed. A bus travels 9 km in 15 minutes; find its speed.",
            [
                "A cyclist rides 600 m in 2 minutes. Find her speed.",
                "A runner covers 400 m in 80 s. Find his speed.",
                "A bus travels 9 km in 15 minutes. Find its speed.",
            ],
        ),
        # The first problem's quantities in its question.
        (
            "Find the speed of a car that goes 100 m in 5 s. A train goes 300 m in 10 s; find "
            "its speed.",
            ["Find the speed of a car that goes 100 m in 5 s", _TRAIN],
        ),
    ],
)
def test_each_problem_is_a_request_with_its_own_setup(text: str, parts: list[str]) -> None:
    assert _parts(text) == [(part, "solve") for part in parts]


def test_a_problem_of_several_questions_carries_its_setup_and_the_next_its_own() -> None:
    assert _parts(
        "A ball is dropped from 20 m. What's its speed after 1 s? How long to reach the "
        "ground? A stone is dropped from 45 m. How long does it take to land?"
    ) == [
        ("A ball is dropped from 20 m. What's its speed after 1 s?", "solve"),
        ("A ball is dropped from 20 m. How long to reach the ground?", "solve"),
        ("A stone is dropped from 45 m. How long does it take to land?", "solve"),
    ]


def test_what_comes_before_the_first_problem_stays_the_context() -> None:
    plan = plan_turn(
        "I'm revising for a test. A car goes 100 m in 5 s; find its speed. A train goes 300 m "
        "in 10 s; find its speed."
    )

    assert plan.context == "I'm revising for a test"
    assert plan.texts() == (_CAR, _TRAIN)


@pytest.mark.parametrize(
    "text",
    [
        # A comparison is one question about both bodies: never two problems.
        "Which is faster, a car going 100 m in 5 s or a train going 300 m in 10 s?",
        "A car goes 100 m in 5 s. A train goes 300 m in 10 s. Which is faster?",
        "A car goes 100 m in 5 s; find its speed. A train goes 300 m in 10 s. Which one is faster?",
        "A car goes 100 m in 5 s; find its speed. A train goes 300 m in 10 s; compare their "
        "speeds.",
        # One problem told in steps: a body already named, or pointed back to.
        "A car accelerates from rest at 2 m/s² for 5 s. Find its speed. The driver then brakes "
        "at 4 m/s². How far does it travel while braking?",
        "A car goes 100 m in 5 s; find its speed. It then goes 300 m in 10 s; find its speed.",
        # A statement no question follows.
        "A car goes 100 m in 5 s; find its speed. A train goes 300 m in 10 s.",
        # Not a problem a subject solves: planned as before.
        "Recommend a laptop under $1000. A friend has a $500 budget; what should she buy?",
    ],
)
def test_one_question_about_several_bodies_or_steps_is_one_request(text: str) -> None:
    assert not plan_turn(text).multi


@pytest.mark.parametrize(
    "text",
    [
        # A question about the bodies together, or about what changed.
        "A 2 kg ball moves at 3 m/s. Find its momentum. A 4 kg ball moves at 1 m/s. Find the "
        "total momentum.",
        "A box of mass 5 kg rests on a 30° incline. Find the normal force. A 2 kg box is placed "
        "on top of the first box. Find the new normal force.",
        "A train leaves at 60 km/h. How far does it go in 2 h? A car leaves 1 h later at 90 "
        "km/h. How long until it catches up?",
        # A step in the first problem's time, or a change to its setup.
        "A car starts from rest and accelerates at 3 m/s² for 4 s. What is its speed? A moment "
        "later the driver brakes at 6 m/s². How far does it go before stopping?",
        "A 4 Ω resistor carries 2 A. Find the voltage. A 6 Ω resistor is added in series. Find "
        "the current.",
        # A thing the message already named.
        "A spring has k = 200 N/m. How much force stretches it 0.1 m? A 2 kg mass is hung from "
        "the spring. How far does it stretch?",
        "10 g of NaOH is dissolved in water. Find the moles. A 2 L flask then holds the "
        "solution. Find the molarity.",
        # "A and B" are symbols, not a body.
        "A and B are events with P(A)=0.3. Find P(not A). A and B are independent with "
        "P(B)=0.5. Find P(A and B).",
    ],
)
def test_a_second_body_that_goes_on_with_the_first_problem_opens_none(text: str) -> None:
    assert problem_clauses(text) is None


def test_a_problem_beside_a_request_of_another_kind_is_planned_as_before() -> None:
    assert problem_clauses("A car goes 100 m in 5 s; find its speed. Also, what's new?") is None


@pytest.mark.parametrize(
    ("text", "opens"),
    [
        ("A train goes 300 m in 10 s", True),
        ("An object falls from 45 m", True),
        ("Another car goes 50 m in 2 s", True),
        ("A 2 kg block is pushed with a force of 10 N", True),
        ("Car B covers 400 m in 20 s", True),
        ("A train goes fast", False),  # no quantity
        ("The driver then brakes at 4 m/s²", False),  # a body already named
        ("It then goes 300 m in 10 s", False),
        ("A = 5 m²", False),  # a symbol, not a body
        ("If A is 5 m long", False),  # a function word before the letter
    ],
)
def test_a_problem_opens_with_a_body_of_its_own_and_its_quantities(text: str, opens: bool) -> None:
    assert opens_problem(text) is opens


@pytest.mark.parametrize(
    ("text", "about"),
    [("Which is faster?", True), ("Compare their speeds.", True), ("Find its speed.", False)],
)
def test_a_question_that_weighs_the_bodies_is_about_all_of_them(text: str, about: bool) -> None:
    assert about_all(text) is about


async def test_separate_problems_no_subject_reads_whole_take_their_parts_subject() -> None:
    message = "A car goes 100 m in 5 s; find its speed. A train goes 300 m in 10 s; find its speed."
    begin_turn()
    await read_turn_message(message, [], Settings())
    reading = current_turn_reading()

    assert reading is not None
    assert len(solved_parts(reading.plan)) == 2
    assert (reading.subject, reading.subject_reason) == ("physics", "parts")


async def test_a_message_its_subject_reads_whole_keeps_that_reading() -> None:
    message = (
        "A ball is dropped from 20 m. How long does it take to reach the ground? A stone is "
        "dropped from 45 m. How long does it take to reach the ground?"
    )
    begin_turn()
    await read_turn_message(message, [], Settings())
    reading = current_turn_reading()

    assert reading is not None
    assert reading.plan.multi
    assert (reading.subject, reading.subject_reason) == ("physics", "physics")
