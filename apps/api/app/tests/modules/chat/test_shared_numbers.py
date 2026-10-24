"""A message that only shares numbers is answered about them, never with a greeting.

"Monthly rainfall in Addis Ababa: Jan 15, …, Dec 5 mm" got "Hey bini! How's it going?"
four times in four from the free plan's model (2026-10-24); told what the message was, it
once named November the driest month. The note says so, with the highest and lowest read
from the message.
"""

from __future__ import annotations

import time

import pytest

from app.modules.chat.prompt_constants.shared_numbers import (
    SHARED_NUMBERS_HINT,
    shared_numbers,
    shared_numbers_hint,
)

_RAIN = (
    "Monthly rainfall in Addis Ababa: Jan 15, Feb 30, Mar 60, Apr 85, May 80, Jun 135, "
    "Jul 280, Aug 290, Sep 190, Oct 30, Nov 6, Dec 5 mm"
)


@pytest.mark.parametrize(
    ("text", "highest", "lowest"),
    [
        # The unit on the last item is the series' unit.
        (_RAIN, "Aug (290 mm)", "Dec (5 mm)"),
        (
            "Here are my exam marks: math 85, physics 78, chemistry 92, biology 88",
            "chemistry (92)",
            "physics (78)",
        ),
        # A thousands comma is not a new item; money keeps its sign.
        (
            "My expenses: rent $1,500, groceries $400, car $300, phone $60",
            "rent ($1,500)",
            "phone ($60)",
        ),
        # "10k" is compared as 10,000; ties name every label.
        ("Q1 10k, Q2 15k, Q3 20k and Q4 20k", "Q3 and Q4 (20k)", "Q1 (10k)"),
        # One line per item, under a title line.
        ("sales this year\nQ1 100\nQ2 150\nQ3 120", "Q2 (150)", "Q1 (100)"),
        ("growth: 2023 5%, 2024 7%, 2025 6%", "2024 (7%)", "2023 (5%)"),
        (
            "weight log: week 1 80 kg, week 2 79.5 kg, week 3 78.8 kg",
            "week 1 (80 kg)",
            "week 3 (78.8 kg)",
        ),
    ],
)
def test_a_list_of_numbers_gets_its_highest_and_lowest(
    text: str, highest: str, lowest: str
) -> None:
    hint = shared_numbers_hint(text)
    assert hint is not None
    assert hint.startswith(SHARED_NUMBERS_HINT)
    assert f"Its highest is {highest} and its lowest is {lowest}" in hint


@pytest.mark.parametrize(
    "text",
    [
        # Asks something: a question, a request, a chart, a reminder, a sum.
        "Mon 5h, Tue 7h, Wed 6h, Thu 8h of sleep. How am I doing",
        "rent 1200, food 300, fun 200, can you chart it",
        "make a bar chart: rent 1200, food 300, fun 200",
        "remind me to pay rent 1200, water 40 and power 60",
        "what's 15 + 30 + 60",
        "Total 1200, rent 800, food 400",
        # Numbers in a sentence, not a list of values.
        "My phone number is 555 123 4567",
        "my flight is at 10:30 on Jan 5, gate 23",
        "I'm 25, my brother is 30 and my sister is 22",
        "I ran 5km today",
        # Dates, not amounts to compare.
        "born 1990, married 2015, moved 2020",
        # Too few, no labels, or units that cannot be compared.
        "rent 1200, food 300",
        "3, 5, 7, 9, 11",
        "loan 20000, rate 5%, 3 years",
        "milk 2 liters, eggs 12, bread 1 loaf",
        "hi",
        "",
    ],
)
def test_what_asks_or_is_no_list_gets_no_note(text: str) -> None:
    assert shared_numbers(text) is None
    assert shared_numbers_hint(text) is None


@pytest.mark.parametrize(
    "text",
    ["a 1, " * 400, "x" * 1990 + " 1, b 2, c 3", "a" * 40 + " " * 3000 + "1, b 2, c 3", "1," * 900],
)
def test_reading_a_long_message_stays_quick(text: str) -> None:
    started = time.perf_counter()
    shared_numbers(text)
    assert time.perf_counter() - started < 0.2
