"""A verified result answers the whole question or none of it (2026-10-30, Ethiopian Grade
7-12 chemistry books: six checked cards answered a part, a different count, or an option
the question did not ask for), and a school exercise is never a forecast, a savings plan or
a whole-atom count."""

from __future__ import annotations

import pytest

from app.modules.chat.prompt_builder import SubjectFetch
from app.modules.chat.whole_question import (
    answers_the_question,
    answers_whole_question,
    labelled_choices,
    whole_question_fetch,
)
from app.modules.chemistry.extract import extract_chemistry_intent
from app.modules.money.read import read_money_request
from app.modules.web_search.geo_intent import is_geo_query
from app.modules.web_search.weather import is_weather_request
from app.services.solving import VerifiedSolveBlock


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        # A count the options do not hold.
        (
            "An atom has an atomic number of 31 and a mass number of 70. How many electrons "
            "will it have in its valence shell?\na 5  b 4  c 3  d 2",
            "Electrons = 31",
        ),
        (
            "How many unpaired electrons are there in the Cr3+ ion?\na 6  b 3  c 1  d 0",
            "Electrons = 21",
        ),
        (
            "An element with the valence electron configuration 3s2 3p2 belongs to group:\n"
            "a IIIA  b IVA  c VIA  d VIIA",
            "6",
        ),
        # Several reactions: options or parts, never one equation to balance.
        (
            "The correct balanced chemical equation for the reaction between iron and oxygen "
            "to form iron (III) oxide is\nA 2Fe + O2 → 2FeO\nB 3Fe + 2O2 → Fe3O4\n"
            "C 4Fe + 3O2 → 2Fe2O3\nD Fe + O → FeO",
            "2 Fe + O₂ → 2 FeO",
        ),
        (
            "Balance the following chemical equations\na H2 + Cu2O → Cu + H2O\nb KClO3 → KCl + O2\n"
            "c Fe + O2 → Fe2O3",
            "H₂ + Cu₂O → 2 Cu + H₂O",
        ),
        # An equation is no number option.
        (
            "Consider the balanced equation:\n3Mg(OH)2 + 2H3PO4 → Mg3(PO4)2 + 6H2O\nWhat is the "
            "coefficient of water?\nA 1\nB 2\nC 3\nD 6",
            "3 Mg(OH)₂ + 2 H₃PO₄ → Mg₃(PO₄)₂ + 6 H₂O",
        ),
        # Parts, labelled with or without a bracket, answered by one line.
        (
            "In a certain atom, the last electron has a 3d2 configuration.\na write the "
            "configuration using a noble gas core.\nb what is the atomic number?\nc how many "
            "protons does it have?",
            "3:2",
        ),
        ("Calculate the pH of: a) 0.0036 M HCl b) 0.047 M HNO3 c) 0.0047 M NaOH", "pH = 2.44"),
        (
            "A 2.50 L container is filled with 175 g of argon:\na if the pressure is 10.0 atm, "
            "what is the temperature?\nb if the temperature is 22 K, what is the pressure?",
            "T = 69.6 K",
        ),
    ],
)
def test_a_result_that_answers_part_of_the_question_is_dropped(question: str, answer: str) -> None:
    assert not answers_whole_question(question, answer)
    verified = VerifiedSolveBlock(text="block", subject="chemistry", canonical_answer=answer)
    fetched = SubjectFetch("block", verified, False, None, None)
    assert whole_question_fetch(question, fetched) == SubjectFetch(None, None, False, None, None)


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("What is the pH of 0.01 M HCl?", "pH = 2"),
        (
            "A 12 V battery drives 2 A. What is the resistance? a) 3 Ω b) 6 Ω c) 12 Ω d) 24 Ω",
            "R = 6 Ω",
        ),
        (
            "A ball is thrown at 20 m/s. Find (a) the time to the top (b) the maximum height.",
            "t = 2.04 s\nh = 20.4 m",
        ),
        ("A 5 kg box is pushed by a 20 N force. Find the acceleration.", "a = 4 m/s²"),
        (
            "The atomic masses of the two isotopes of boron, 10B (20%) and 11B (80%), are 10 and "
            "11. Calculate the average atomic mass of boron.",
            "A(B) = 10.8 u",
        ),
    ],
)
def test_a_result_that_answers_the_whole_question_stays(question: str, answer: str) -> None:
    assert answers_whole_question(question, answer)


def test_options_on_their_own_lines_and_inline_read_alike() -> None:
    assert labelled_choices("Pick one:\na 5  b 4  c 3  d 2") == ["5", "4", "3", "2"]
    assert labelled_choices("Pick one:\nA 1\nB 2\nC 3") == ["1", "2", "3"]
    # A sentence's "a" is no label.
    assert labelled_choices("A ball of mass 2 kg is a sphere. Find its weight.") == []


@pytest.mark.parametrize(
    ("question", "forecast"),
    [
        # Stated quantities make an exercise: it asked for the user's city.
        (
            "A 2.50 L container is filled with 175 g of argon: if the pressure is 10.0 atm, "
            "what is the temperature?",
            False,
        ),
        ("What is the temperature today?", True),
        ("What is the temperature in Paris tomorrow?", True),
    ],
)
def test_an_exercise_is_no_forecast(question: str, forecast: bool) -> None:
    assert is_weather_request(question) is forecast


@pytest.mark.parametrize(
    ("question", "product"),
    [
        # "compound" alone is a chemistry noun.
        (
            "A compound is composed of 53.33% carbon, 11.11% hydrogen and 35.56% oxygen. If "
            "the molecular mass of the compound is 90, what is the molecular formula?",
            None,
        ),
        ("If I save 5000 at 4% compounded monthly for 10 years, how much will I have?", "savings"),
    ],
)
def test_a_compound_is_no_savings_plan(question: str, product: str | None) -> None:
    read = read_money_request(question)
    assert (read.product.key if read else None) == product


@pytest.mark.parametrize(
    ("question", "read"),
    [
        ("How many valence electrons does gallium (Z = 31) have?", False),
        ("How many unpaired electrons are there in the Cr3+ ion?", False),
        ("How many d electrons does Fe2+ have?", False),
        ("How many electrons does a Cr3+ ion have?", True),
    ],
)
def test_some_of_the_electrons_are_no_atoms_count(question: str, read: bool) -> None:
    assert (extract_chemistry_intent(question) is not None) is read


# Ethiopian Grade 7-12 maths and physics books: verified cards that answered something else.
@pytest.mark.parametrize(
    ("question", "answer"),
    [
        # A verdict where no equation is solved.
        (
            "If h:k = 2:5, x:y = 3:4 and (2h + x):(k + 2y) = 1:2, find the ratio (h - x):(k - y).",
            r"\text{no solution}",
        ),
        (
            "Find the vector product a × b if a = 3i – 2j + 5k and b = 7i + 4j – 8k.",
            r"\text{infinitely many solutions},\quad a = 3 i - 2 j + 5 k, b = 7 i + 4 j - 8 k",
        ),
        # A size is never signed.
        (
            "The volume of a right circular cylinder is 1540 cm^3 and its altitude is 10 cm. "
            "What is the length of the radius of the base?",
            r"r = \pm 7",
        ),
        # The question's own expression.
        (
            "Find the cube root of 27a^3 + 54a^2b + 36ab^2 + 8b^3.",
            r"27 a^{3} + 54 a^{2} b + 36 a b^{2} + 8 b^{3}",
        ),
        # A proof has no value.
        ("Prove by induction that 1 + 2 + ... + n = n(n+1)/2.", r"n = 0, \frac{1}{2}, 1"),
        # A value at a point, not the function.
        ("Find the gradient of the curve y = x^2 + 1 at x = 3.", r"\frac{dy}{dx} = 2 x"),
        # An equation where one is asked.
        ("Find the equation of the line through (1, 0) and (3, 1).", "1"),
        # Solutions of the kind asked.
        ("Find the rational zeros of x^3 - 2.", r"x = 1.2599, -0.63 + 1.09 i"),
    ],
)
def test_a_result_that_answers_something_else_is_dropped(question: str, answer: str) -> None:
    assert not answers_the_question(question, answer)


@pytest.mark.parametrize(
    ("question", "answer"),
    [
        ("Solve the system x + y = 2, 2x + 2y = 4.", r"\text{infinitely many solutions}"),
        ("Solve x^2 = 49.", r"x = \pm 7"),
        ("Find the cube root of 27a^3 + 54a^2b + 36ab^2 + 8b^3.", "3a + 2b"),
        ("Find the gradient of the curve y = x^2 + 1 at x = 3.", r"\frac{dy}{dx} = 6"),
        ("Find the equation of the line through (1, 0) and (3, 1).", r"y = \frac{x - 1}{2}"),
        ("Find the derivative of x^2 sin x.", r"2 x \sin x + x^2 \cos x"),
        ("Find the rational zeros of x^3 - x.", "x = -1, 0, 1"),
        ("A ball is thrown up at 20 m/s. What is its velocity after 3 s?", "v = -9.4 m/s"),
    ],
)
def test_a_result_that_answers_the_question_stays(question: str, answer: str) -> None:
    assert answers_the_question(question, answer)


@pytest.mark.parametrize(
    ("question", "local"),
    [
        (
            "A tree 18 meters high is broken off 5 meters from the ground. How far from the foot "
            "of the tree will the top strike the ground?",
            False,
        ),
        ("Determine the point(s) on f(x) = x^2 + 1 that are closest to the point (0, 2).", False),
        ("How far is the nearest pharmacy?", True),
        ("Coffee shops near me open now", True),
    ],
)
def test_a_worked_problem_never_asks_where_the_user_is(question: str, local: bool) -> None:
    assert is_geo_query(question) is local


# Review: each was a correct card dropped, or a wrong one kept.
@pytest.mark.parametrize(
    ("question", "answer", "kept"),
    [
        # A size word in a given is no size asked.
        (
            "A 2 kg mass moving at 6 m/s comes to rest in 3 s. Find its acceleration.",
            r"-2\,\mathrm{m/s^2}",
            True,
        ),
        # An option read as its value, within 2%.
        (
            "Which is the energy? a) 2 × 10^5 J b) 4 × 10^5 J c) 6 J d) 8 J",
            r"2 \times 10^{5}\,\mathrm{J}",
            True,
        ),
        (
            "Area of a circle of radius 5 cm? a) 78.54 cm² b) 31.4 cm² c) 25 cm² d) 10 cm²",
            r"78.54\,\mathrm{cm}^{2}",
            True,
        ),
        ("Solve 2x = 1. a) 1/2 b) 2 c) 1 d) 0", r"x = \frac{1}{2}", True),
        (
            "Molar mass of H2SO4? a) 98 g/mol b) 49 g/mol c) 100 g/mol d) 64 g/mol",
            r"98.07\,\mathrm{g/mol}",
            True,
        ),
        # Roman-numeral parts answered piece by piece.
        (
            "A car accelerates at 2 m/s^2 from 0 for 5 s. Find (i) the final velocity (ii) the distance.",
            r"v = 10\,\mathrm{m/s};\quad s = 25\,\mathrm{m}",
            True,
        ),
        # A reaction is an equation.
        (
            "Balance the chemical equation of the combustion of methane: CH4 + O2 → CO2 + H2O",
            "CH₄ + 2 O₂ → CO₂ + 2 H₂O",
            True,
        ),
        # e is a constant.
        ("Find the slope of the tangent to y = e^x at x = 1.", "e", True),
        # A value with the variable still in it, inside a fraction.
        (
            "Find the x-coordinate where y = 2x - 6 crosses the x-axis.",
            r"x = \frac{y}{2} + 3",
            False,
        ),
        # A confirmation repeats the asker's number.
        (
            "A ball is dropped from 20 m. I got 19.8 m/s for its impact speed. Am I right?",
            r"19.8\,\mathrm{m/s}",
            True,
        ),
    ],
)
def test_review_cases(question: str, answer: str, kept: bool) -> None:
    assert answers_the_question(question, answer) is kept


@pytest.mark.parametrize(
    "question",
    [
        "How far is the nearest hospital? I can walk 2 km in 30 minutes",
        "weather near (40.7, -74.0)",
    ],
)
def test_time_and_map_coordinates_stay_location_questions(question: str) -> None:
    assert is_geo_query(question)


@pytest.mark.parametrize(
    ("question", "answer", "kept"),
    [
        # Values asked, an expression given: a factorisation is no list of zeros.
        (
            "Find all the rational zeros of f(x) = x^5 + 8x^4 + 20x^3 + 9x^2 - 27x - 27",
            r"\left(x + 3\right)^{2} \left(x^{3} + 2 x^{2} - x - 3\right)",
            False,
        ),
        ("Find the roots of x^2 - 5x + 6 = 0.", "x = 2, x = 3", True),
        ("Solve the system x + y = 3, x - y = 1.", "x = 2, y = 1", True),
        ("Solve |x - 2| < 3.", "-1 < x < 5", True),
        ("Solve for x in terms of y: 2x + y = 4.", r"x = \frac{4 - y}{2}", True),
        ("Find the cube root of 27a^3 + 54a^2b + 36ab^2 + 8b^3.", "3a + 2b", True),
    ],
)
def test_values_asked_are_values(question: str, answer: str, kept: bool) -> None:
    assert answers_the_question(question, answer) is kept
