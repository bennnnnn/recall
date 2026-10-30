"""A school exercise gets a note beside it: the textbook's answer, at its level
(2026-10-30, a Class 8 physical science book, then a Class 9 book in every subject).
Any other question about the world gets the lighter factual note."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.chat.message_notes import message_notes
from app.modules.chat.prompt_constants.school_question import (
    FACTUAL_QUESTION_NOTE,
    SCHOOL_QUESTION_NOTE,
    question_hint,
    school_question_hint,
)


@pytest.mark.parametrize(
    "query",
    [
        "Hoisting a flag is related to [ ] a) push b) pull c) Push and pull both d) pressure",
        "The lowest temperature at which a substance catches fire is called its a) Ignition "
        "temperature b) Maximum temperature c) Room temperature d) Normal temperature",
        "Let the forces F1 and F2 act on the table in opposite directions, F1 > F2, the "
        "Fnet = a) F1-F2 b) F1+F2 c) 0 d) 2F2-F1",
        "Give two examples each for a contact force and a force at a distance.",
        "Explain the physical properties of metals with suitable examples.",
        "Distinguish between a contact force and a force at a distance.",
        "How is the property malleability of metals used in our daily life?",
        "Suppose you have to go out on that day. Would you carry an umbrella? Explain.",
        "Do you agree with the statement “friction is both good and evil”? Explain.",
        "Why do tools meant for cutting always have sharp edges? (AS1)",
        # A Class 9 book (2026-10-30): the shapes every textbook prints, in any subject.
        "If a plant is unable to transport food from leaves to roots which tissue is "
        "malfunctioning?\n(i) Xylem\n(ii) Phloem\n(iii) Epidermis\n(iv) Sclerenchyma",
        "Two similar animal cells are placed in two different solutions. Which statement "
        "provides the correct explanation?\n(i) Salt molecules moved into Cell Y, causing "
        "it to shrink.\n(ii) Water moved into Cell X and more water moved out of Cell Y than "
        "the salt solution entered in it.\n(iii) Water moved into Cell X and moved out of "
        "Cell Y through the cell membrane.\n(iv) Solute movement caused osmosis in both.",
        "Assertion: Cardiac muscle can contract continuously without fatigue.\nReason: "
        "Cardiac muscle cells have a high number of mitochondria.",
        "Fill in the blanks. Power is defined as the ______ at which work is done.",
        "Two students, Renu and Rohit, were having a discussion on the plastids. Who is "
        "correct? Justify your answer.",
        "A farmer wants to produce a large number of genetically identical plants quickly. "
        "Suggest suitable reproduction methods.",
        "A car starts from rest and its velocity reaches 24 m/s in 6 s. Find the average "
        "acceleration and the distance travelled in these 6 s.",
        "Determine the formula unit mass of (i) ammonium nitrate (NH4NO3), (ii) phosphoric "
        "acid (H3PO4), (iii) sodium hydrogencarbonate (NaHCO3).",
        "Identify the pair that incorrectly matches the cell organelle with its function.",
        "Write the formulae for the compounds formed by magnesium and nitrogen.",
        "A vehicle's parking sensor emits ultrasonic waves at 40 kHz. When the beep starts "
        "at 1.2 m from the obstacle, how much time does the wave take to come back?",
    ],
)
def test_a_school_exercise_gets_the_note(query: str) -> None:
    hint = school_question_hint(query)
    assert hint is not None and hint.startswith(SCHOOL_QUESTION_NOTE)


def test_a_multiple_choice_question_is_told_to_name_one_option_first() -> None:
    hint = school_question_hint("Which is a natural fibre? a) Rayon b) Nylon c) Polyester d) Silk")
    assert hint is not None and "name the one correct option" in hint


@pytest.mark.parametrize(
    "query",
    [
        "Why do cats purr?",
        "Explain how a mortgage works",
        "What are the differences between a Roth and a traditional IRA?",
        "Give me two examples of good cover letter openings",
        "I bought a) bread b) milk c) eggs today",
        "Plan: a) gym b) lunch c) call mom",
        "Should we pick a) Postgres b) Mongo c) Dynamo for the new service?",
        "Do you agree with the statement that AI will replace jobs?",
        "Is this a good idea? Why?",
        # Review (2026-10-30): code, checklists and requests that use an exercise's words.
        "Why does def f(x=[]): keep growing between calls?",
        "const items = []; items.push(1) why is this allowed with const?",
        "- [ ] buy milk\n- [ ] call mom\nturn this into a schedule",
        "Define a Python function that reverses a string.",
        "Write a short note to my landlord saying the heater is broken.",
        "Classify the following emails as urgent or not",
        "Give reasons for choosing Postgres over MongoDB for our app",
        "Explain Python decorators with an example",
        "In the experiment we ran last week, conversion went up 3%",
        "Explain.",
        "Should I refinance now or wait? Explain why.",
        "What are the opening hours of a) the Louvre b) the Musee d Orsay c) the Pompidou",
        "How are these stocks doing: a) Tesla b) Nvidia c) Apple",
        "Plan a 5-day itinerary covering a) Rome b) Florence c) Venice",
        "Write three taglines for a coffee brand: a) playful b) premium c) eco",
        "What is the current Fed funds rate? a) 3.5% b) 4.25% c) 5%",
        # Second review (2026-10-30): taste, every option wanted, adult definitions, code.
        "Summarize these options for the team: a) hire b) outsource c) wait",
        "Which of these pizza toppings go well together: a) pineapple b) ham c) anchovies",
        "Which is better for a beginner: a) Python b) JavaScript c) Rust",
        "Help pick a name for the cat: a) Milo b) Luna c) Oliver",
        "Which sounds more professional in an email: a) Hi b) Hello c) Dear",
        "Define gaslighting.",
        "Give two examples of good cover letter openings for a software engineer.",
        'Do you agree with the statement "remote work kills culture"?',
        "What does the error TypeError: undefined is not a function mean in JavaScript? Explain.",
    ],
)
def test_anyone_elses_question_is_no_exercise(query: str) -> None:
    assert school_question_hint(query) is None


@pytest.mark.parametrize(
    "query",
    [
        "Rohan studies from 6 PM to 7:30 PM. The minute hand is 7 cm long. What is its "
        "(i) distance travelled, (ii) displacement, (iii) speed, and (iv) velocity?",
        "Fill in the blanks.\n(i) Work done = ______ × ______\n(ii) 1 joule is done when a "
        "force of ______ newton acts\n(iii) Power is the ______ at which work is done.",
        "If a species has 11 protons, (i) what is its atomic number? (ii) is it neutral, a "
        "cation or an anion? (iii) write its electronic configuration.",
    ],
)
def test_parts_are_not_options(query: str) -> None:
    hint = school_question_hint(query)
    assert hint is not None and "It asks you to choose" not in hint


def _user() -> SimpleNamespace:
    return SimpleNamespace(emoji_use="some", locale="en", custom_instructions=None)


def test_the_note_sits_beside_the_message() -> None:
    notes = message_notes("Distinguish between metals and non-metals.", [], _user())
    assert any(note.startswith(SCHOOL_QUESTION_NOTE) for note in notes)


def test_a_lesson_keeps_its_own_way() -> None:
    notes = message_notes(
        "Teach me friction. Distinguish between static and sliding friction.", [], _user()
    )
    assert not any(note.startswith(SCHOOL_QUESTION_NOTE) for note in notes)


# The rerun (2026-10-30) still opened "Most pans actually do have metal handles" and
# "it doesn't, really": any question about the world gets the textbook answer first too.
@pytest.mark.parametrize(
    "query",
    [
        "Why don't cooking pans have metal handles?",
        "Why does the image in a plane mirror suffer lateral inversion?",
        "Why is phosphorus preserved in water?",
        "Why do cats purr?",
        "Explain how a mortgage works",
        "Mitochondria and chloroplasts are two organelles. Discuss how they are similar.",
        "Electrons move around the nucleus in orbits. Why do they not fly away?",
    ],
)
def test_a_question_about_the_world_gets_the_factual_note(query: str) -> None:
    assert question_hint(query) == FACTUAL_QUESTION_NOTE


@pytest.mark.parametrize(
    "query",
    [
        "Why is my car battery dead?",
        "What is the current price of gold?",
        "What metal is best for a wedding ring?",
        "Why does my code throw a TypeError?",
        "Write a poem about the rain",
        "Translate 'good morning' into French",
        "hi",
        "Which laptop would you recommend for video editing?",
    ],
)
def test_a_personal_current_taste_or_task_message_gets_no_note(query: str) -> None:
    assert question_hint(query) is None


@pytest.mark.parametrize(
    ("content", "nothing"),
    [
        (
            "The lowest temperature at which a substance catches fire is called its "
            "a) Ignition temperature b) Maximum temperature c) Room temperature "
            "d) Normal temperature",
            True,
        ),
        ("Two students, Renu and Rohit, argue about plastids. Who is correct?", True),
        ("Who won the champions league final?", False),
        ("What is the current Fed funds rate? a) 3.5% b) 4.25% c) 5%", False),
    ],
)
def test_a_textbook_question_has_nothing_to_look_up(content: str, nothing: bool) -> None:
    # Its note said not to search, and the reply searched anyway (2026-10-30).
    from app.modules.chat.tool_loop.reply_calls import _nothing_to_look_up

    assert _nothing_to_look_up(content, None) is nothing
