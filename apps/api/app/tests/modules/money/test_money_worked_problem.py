"""A lesson's money problem is laid out for the student; anyone's own money keeps the short
reply (2026-10-31: two Grade 11-12 questions got two lines over a calculator card)."""

from __future__ import annotations

import pytest

from app.modules.money.block import MONEY_REPLY_RULES, MONEY_WORKED_RULES, money_block
from app.modules.money.read import read_money_request
from app.modules.money.solve import work
from app.modules.money.worked_problem import is_worked_problem


@pytest.mark.parametrize(
    "text",
    [
        "Ato Alula deposited Birr 3,000 in a saving account that pays 6% interest rate per "
        "year, compounded quarterly. What is the amount of interest obtained at the end of "
        "seven years?",
        "Moges wants to buy a house that costs Birr 250,000. He has saved Birr 50,000 which "
        "he will use as a deposit. What will his monthly payment be?",
        "Sara invests $2,000 at 5% compounded annually. How much will she have after 6 years?",
        "A man borrows $12,000 at 9% for 4 years. Find his monthly payment.",
        "The company took a loan of $500,000 at 8% over 10 years. What is the payment?",
        "Calculate the monthly payment on a loan of $20,000 at 6% for 5 years.",
    ],
)
def test_a_lessons_money_problem_is_worked(text: str) -> None:
    assert is_worked_problem(text)


@pytest.mark.parametrize(
    "text",
    [
        "What's the monthly payment on a $300,000 mortgage at 6.5% for 30 years?",
        "I have $5,000 on my credit card at 22% APR and pay $200 a month. How long?",
        "If I save $500 a month at 5% for 10 years how much will I have?",
        "My friend Sara wants a $20,000 car loan at 7%, what would she pay?",
        "Should we refinance our $250k mortgage from 7% to 6%?",
        "How much would you pay on a $10,000 loan at 5% over 3 years?",
        "What deposits do banks pay 5% on?",
        "If rates fall to 5%, what's a $400k mortgage payment?",
    ],
)
def test_anyones_own_money_or_a_bare_question_is_not(text: str) -> None:
    assert not is_worked_problem(text)


def test_the_block_asks_a_worked_problem_for_its_working() -> None:
    request = read_money_request("A loan of $20,000 at 6% for 5 years. Find the monthly payment.")
    assert request is not None
    worked = work(request, None)
    lesson = money_block(request, worked, None, worked_problem=True)
    assert MONEY_WORKED_RULES in lesson and MONEY_REPLY_RULES not in lesson
    assert "**Formula**" in lesson and "never work out an intermediate value" in lesson
    plain = money_block(request, worked, None)
    assert MONEY_REPLY_RULES in plain and MONEY_WORKED_RULES not in plain
