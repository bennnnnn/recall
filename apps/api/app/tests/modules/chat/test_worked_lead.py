"""A worked reply's result comes after its working, never above it: not as a guess
(2026-10-30), and not said early either (2026-11-07)."""

from __future__ import annotations

import pytest

from app.modules.chat.worked_lead import drop_guessed_lead, drop_restated_tail

_WORKED = (
    "**Given**\n$m_1 = 160\\ \\text{kg}$\n\n**Formula**\n$E = \\frac{1}{2}Mv^2$\n\n"
    "**Answer**\n\n```answer\n$E_1 : E_2 = 4 : 5$\n```\n"
)


@pytest.mark.parametrize(
    "lead",
    [
        "The ratio of fuel used on the first day to the second day is **5: 7**\n\n",
        "The car covers **290 m** in total.\n\n",
        "The time of contact is **0.054 s**.\n\n",
    ],
)
def test_a_number_above_the_working_goes(lead: str) -> None:
    assert drop_guessed_lead(lead + _WORKED) == _WORKED


@pytest.mark.parametrize("heading", ["Required", "Find"])
def test_a_number_above_a_working_that_opens_on_what_is_asked_goes(heading: str) -> None:
    # A follow-up may skip Given; what is asked (Find, in an older reply) opens the working.
    worked = f"**{heading}**\n$t$\n\n**Answer**\n\n```answer\n$t = 200\\ \\text{{s}}$\n```\n"
    assert drop_guessed_lead("The bus takes **150 s**.\n\n" + worked) == worked


def test_a_heading_or_a_photo_above_the_working_stays() -> None:
    text = "[Image: /attachments/a1b2/file]\n\n## Stage 1\n\nAtomic structure of Mg\n\n" + _WORKED
    assert drop_guessed_lead(text) == text


def test_only_the_guess_goes_from_a_lead_with_a_heading() -> None:
    text = "## Stage 1\n\nThe car covers **290 m**.\n\n" + _WORKED
    assert drop_guessed_lead(text) == "## Stage 1\n\n" + _WORKED


@pytest.mark.parametrize(
    "text",
    [
        # No card: the lead may be the only place the answer is.
        "The car covers **310 m**.\n\n**Given**\n$u = 0$\n",
        # A long lead is an answer of its own, not a guess.
        " ".join(["word"] * 70) + " 12 m\n\n" + _WORKED,
        # A Given in a code example is not the reply's working.
        "Use 3 workers.\n\n```md\n**Given**\n```\n\n```answer\n3\n```\n",
        # No number above the working.
        "Here is the working.\n\n" + _WORKED,
    ],
)
def test_anything_else_is_left_alone(text: str) -> None:
    assert drop_guessed_lead(text) == text


def test_a_photo_fence_above_the_working_stays() -> None:
    text = "```photo\nEiffel Tower 1889\n```\n\n" + _WORKED
    assert drop_guessed_lead(text) == text


_CAR = (
    "**Given**\n$u = 0$, 100 m, 5 s, 2 m/s²\n\n**Answer**\n\n```answer\n$s = 25\\ \\text{m}$\n```\n"
)


@pytest.mark.parametrize(
    "lead",
    [
        # Review (2026-10-30): a lead the working agrees with is the reader's, not a guess.
        "No, the student is wrong: the car does not reach 100 m in 5 s.",
        "(a) The acceleration is 2 m/s².",
        "Warning: never connect 230 V mains directly.",
        "![diagram](https://x/1.png)",
        "$$v = \\sqrt{2gh}$$",
        "- step 1 of 3",
        "Let's find how far the car goes in 5 s.",
    ],
)
def test_a_lead_that_states_no_result_stays(lead: str) -> None:
    text = f"{lead}\n\n{_CAR}"
    assert drop_guessed_lead(text) == text


@pytest.mark.parametrize(
    "lead",
    [
        "**s = 25 m**",
        "The car covers **25 m** (0.025 km).",
        "The car travels **25 m** before it stops, here is why:",
    ],
)
def test_the_answer_said_above_the_working_goes(lead: str) -> None:
    # Right but early: the card under the working says it, once, as a textbook does.
    assert drop_guessed_lead(f"{lead}\n\n{_CAR}") == _CAR


_SOLVE_X = "**Given**\n$5x - 3 = 12$\n\n**Answer**\n\n```answer\nverified: false\nx = 3\n```\n"


@pytest.mark.parametrize(
    ("lead", "worked"),
    [
        # Review (2026-11-07): a digit the card shares is not the card's result.
        ("Let's solve 5x - 3 = 12 for x.", _SOLVE_X),
        ("The car is 100 m from the wall when it brakes.", _CAR),
    ],
)
def test_a_lead_sharing_a_number_with_the_card_stays(lead: str, worked: str) -> None:
    text = f"{lead}\n\n{worked}"
    assert drop_guessed_lead(text) == text


def test_the_cards_statement_must_stand_whole() -> None:
    # "x = 30" does not say x = 3, nor "125 m" 25 m; both are numbers the working holds.
    worked = "**Given**\n$x = 30$, 125 m\n\n**Answer**\n\n```answer\nverified: true\nx = 3\n```\n"
    for lead in ("Start from **x = 30**.", "The track is **125 m** long."):
        text = f"{lead}\n\n{worked}"
        assert drop_guessed_lead(text) == text


@pytest.mark.parametrize(
    "heading",
    [
        "## Q7",
        "**Ex 4**",
        "## Set B2",
        "**Stage 1**",
        # Review (2026-11-07): a number followed by words still names a part.
        "## Chapter 4 Kinematics",
        "**Step 1 of 3**",
        "## Question 12 Part b",
    ],
)
def test_a_short_heading_with_a_number_stays(heading: str) -> None:
    # Review (2026-11-07): a heading names a part; its number is no stated result.
    text = f"{heading}\n\n{_CAR}"
    assert drop_guessed_lead(text) == text


def test_a_models_bold_answer_over_its_steps_goes() -> None:
    # Live, 2026-11-07: "**x = 3**" over Given, Required, Solution and a card of x = 3.
    worked = (
        "**Given**\n$5 x - 3 = 12$\n\n**Required**\n$x = ?$\n\n**Solution**\n\n"
        "**1. Add 3 to both sides** (addition property of equality)\n$5 x - 3 + 3 = 12 + 3$\n"
        "$5 x = 15$\n\n**2. Divide both sides by 5**\n$x = 3$\n\n**Answer**\n\n"
        "```answer\nverified: false\nx = 3\n```\n"
    )
    assert drop_guessed_lead("**x = 3**\n\n" + worked) == worked


def test_a_ratio_is_compared_as_a_pair() -> None:
    worked = "**Working**\n$E_1 = 80v^2$, $E_2 = 100v^2$\n\n```answer\n$E_1 : E_2 = 4 : 5$\n```\n"
    assert drop_guessed_lead("**The ratio is 1 : 5.**\n\n" + worked) == worked


# The worked layout's cards as finalize lands them (``check_working``).
_DISPLACEMENT = (
    "**Required**  \n$s$ (displacement)\n\n**Answer**\n\n"
    "```answer\nverified: false\ns = 2400\\,\\mathrm{m}\\ \\text{east}\n```"
)
_DISPLACEMENT_ASKED = (
    "A car moves at a speed of 20m/s for 120 seconds due East. What is the displacement?"
)
_CAR_AND_TRAIN = (
    "**Required**  \n(a) $v$ (speed of the car)  \n(b) $v$ (speed of the train)\n\n"
    "**Solution**\n\n**(a) speed of the car**\n\n**Answer (a)**\n\n"
    "```answer\nverified: false\n20\\,\\mathrm{m/s}\n```\n\n---\n\n"
    "**(b) speed of the train**\n\n**Answer (b)**\n\n"
    "```answer\nverified: false\n30\\,\\mathrm{m/s}\n```"
)
_CAR_AND_TRAIN_ASKED = (
    "A car goes 100 m in 5 s; find its speed. A train goes 300 m in 10 s; find its speed."
)


@pytest.mark.parametrize(
    ("worked", "asked", "tail"),
    [
        (_DISPLACEMENT, _DISPLACEMENT_ASKED, "The displacement of the car is **2400 m** due East."),
        (_DISPLACEMENT, _DISPLACEMENT_ASKED, "So the displacement is $s = 2400\\,\\mathrm{m}$."),
        (
            _CAR_AND_TRAIN,
            _CAR_AND_TRAIN_ASKED,
            "The car's speed is **20 m/s**, and the train's speed is **30 m/s**.",
        ),
        (
            _CAR_AND_TRAIN,
            _CAR_AND_TRAIN_ASKED,
            "The speed of the car is 20 m/s.\n\nThe speed of the train is 30 m/s.",
        ),
    ],
)
def test_a_tail_restating_the_cards_goes(worked: str, asked: str, tail: str) -> None:
    assert drop_restated_tail(f"{worked}\n\n{tail}\n", asked) == f"{worked}\n"


@pytest.mark.parametrize(
    ("worked", "asked", "tail"),
    [
        # A caveat, a number of its own, a comparison, a direction the card lacks.
        (_DISPLACEMENT, _DISPLACEMENT_ASKED, "This assumes the car keeps a constant speed."),
        (_CAR_AND_TRAIN, _CAR_AND_TRAIN_ASKED, "The train is faster by 10 m/s."),
        (_CAR_AND_TRAIN, _CAR_AND_TRAIN_ASKED, "At 30 m/s the train is faster than the car."),
        (
            _DISPLACEMENT.replace("\\ \\text{east}", ""),
            "A car moves at 20 m/s for 120 s. What is its displacement?",
            "The displacement is 2400 m east.",
        ),
        # Not a sentence: a list, a heading.
        (_CAR_AND_TRAIN, _CAR_AND_TRAIN_ASKED, "- car: 20 m/s\n- train: 30 m/s"),
    ],
)
def test_a_tail_saying_something_new_stays(worked: str, asked: str, tail: str) -> None:
    text = f"{worked}\n\n{tail}\n"
    assert drop_restated_tail(text, asked) == text


def test_a_picture_after_a_restatement_stays() -> None:
    graph = '```graph\n{"type": "function", "expr": "20*t"}\n```'
    text = f"{_DISPLACEMENT}\n\nThe displacement is 2400 m east.\n\n{graph}\n"
    assert drop_restated_tail(text, _DISPLACEMENT_ASKED) == f"{_DISPLACEMENT}\n\n{graph}\n"


def test_a_reply_without_a_card_is_unchanged() -> None:
    text = "**Answer**\n\n$s = 2400$\n\nThe displacement is 2400 m.\n"
    assert drop_restated_tail(text, _DISPLACEMENT_ASKED) == text
