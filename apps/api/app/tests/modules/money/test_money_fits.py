"""A reading the rate-period reader adds is used only when it is positively the loan's own.

A second review (2026-11-14) found each new reading taken from words about something else:
"in 3 weeks" as a term (a $300k mortgage at 435,166.20 a month), "three monthly payments
behind" as a 3-month loan, "The bank charges 2% on the unpaid balance each month" as a
yearly 2%, "1.9% a month" on a car loan as 22.8%, "borrowed" with no rate or from an uncle as
a loan, and a stated payment with no term worked over an assumed one. Each now changes
nothing unless the loan's own words say it, and works no numbers when they say it in a
form that cannot be placed. Every expected payment is P·i / (1 - (1 + i)^-n), worked apart
from the catalog.
"""

from __future__ import annotations

import pytest

from app.modules.money.agreement import card_figures
from app.modules.money.compounding import compounding_per_year
from app.modules.money.read import read_money_request
from app.modules.money.solve import work
from app.modules.money.sums import amounts


def _payment(text: str) -> tuple[dict[str, float], float]:
    request = read_money_request(text)
    assert request is not None, text
    worked = work(request, None)
    assert worked is not None and worked.outputs["payment"] is not None, text
    return request.values, round(worked.outputs["payment"], 2)


@pytest.mark.parametrize(
    ("text", "payment"),
    [
        # A length about something else: the term is assumed as before, and says so.
        ("We close on our $300k mortgage at 6% in 3 weeks, what will the payment be?", 1798.65),
        ("I'm 30 weeks pregnant and we need a $300k mortgage at 6%. What's the payment?", 1798.65),
        ("We're taking a 2-week vacation, then buying a car with a $20,000 car loan at 6%", 386.66),
        ("Rates may drop in 2 quarters; what is the payment on a $300k mortgage at 6% now?", 1798.65),
        ("A $300,000 mortgage at 6% with a 2 week grace period", 1798.65),
        # A count about something else, beside the term the user gives.
        ("The bank wants 2 monthly payments up front on a $20,000 car loan at 6% for 5 years", 386.66),
        ("After 24 monthly payments on a $300k mortgage at 6% for 30 years, how much is left?", 1798.65),
    ],
)  # fmt: skip
def test_a_length_or_a_count_about_something_else_changes_nothing(
    text: str, payment: float
) -> None:
    assert _payment(text)[1] == payment


@pytest.mark.parametrize(
    ("text", "term", "payment"),
    [
        # Said as the loan's term: after "for" or "over", the loan repaid in it, an item.
        ("$20,000 loan at 6% over 8 quarters", {"years": 2}, 886.41),
        ("A $5,000 personal loan for 26 weeks at 10%", {"months": 6}, 857.81),
        ("$15,000 car loan at 5%, 52 weeks", {"months": 12}, 1284.11),
        ("car loan $20,000 at 6%, 72 monthly payments, any tips?", {"months": 72}, 331.46),
        ("A $20,000 car loan at 6% with 60 monthly payments", {"months": 60}, 386.66),
    ],
)  # fmt: skip
def test_a_length_or_a_count_said_as_the_term_is_the_term(
    text: str, term: dict[str, float], payment: float
) -> None:
    values, worked = _payment(text)
    assert {name: values[name] for name in term} == term
    assert worked == payment


@pytest.mark.parametrize(
    "text",
    [
        # A count of the loan's payments in its own sentence, not said as the term, no term.
        "I'm three monthly payments behind on my $15,000 car loan at 7%, what do I owe?",
        "I fell 3 monthly payments behind on a $300k mortgage at 6%",
        "I can skip 2 monthly payments on my $20,000 car loan at 6%",
        "Deferring 6 monthly payments on my $30,000 student loan at 5%",
        "Twelve monthly payments into my $20,000 car loan at 6%, how much do I still owe?",
        "A $20,000 car loan at 6%, 6 monthly payments deferred",
        "I can afford 400 monthly payments on a $20,000 car loan at 6%",
        "I made 12 monthly payments on my $20,000 car loan at 6%; what is left?",
        "3 monthly payments left on my $1,500 car loan at 6%",
        # A count with no frequency that is not the term's at the loan's schedule.
        "$10,000 loan at 6% for 3 years, 12 payments",
        # Off the product's term slider, or fewer than two payments.
        "mortgage $300k at 6%, 900 monthly payments",
        "car loan 20k at 6%, 450 monthly payments",
        "Payday loan $500 at 15% for 2 weeks",
        "How much is a $250k mortgage at 6% if I wait 3 months to buy?",
        "$15,000 car loan at 5% over 1 quarter",
        "a $10,000 loan at 6% for 1 year, repaid once a year",
        # Days are no term a product works.
        "loan of $5,000 at 10% for 90 days",
        "loan of $5,000 at 10%, 90 day term",
    ],
)
def test_a_length_or_a_count_that_cannot_be_the_term_works_no_numbers(text: str) -> None:
    assert read_money_request(text) is None


@pytest.mark.parametrize(
    "text",
    [
        # A period in the percent's sentence that belongs to nothing else.
        "A man borrows Birr 100,000 and agrees to repay the loan in 48 equal monthly payments. The bank charges 2% on the unpaid balance each month. How much is each payment?",
        "A loan of $10,000 is repaid in 24 equal monthly payments; 2% interest is charged per month. Find the payment.",
        "A loan of $10,000 is repaid in 24 equal monthly payments; interest of 1.5% is charged each month. Find the payment.",
        "A loan of $10,000 at 2%, charged monthly, repaid in 24 equal monthly payments. Find the payment.",
        "A loan of $10,000 at 2% interest, calculated monthly, for 2 years. What is the monthly payment?",
        "Birr 50,000 loan; the bank's rate is 1.5%, applied monthly to the balance; 36 monthly payments",
        "A loan of $10,000 with 2% added to the balance every month, repaid over 2 years",
        "Student loan $30,000 at 5% for 10 years, interest accrues daily",
        # A describing word in brackets is as open as without them.
        "A $10,000 loan at 2% [monthly] for 2 years",
        # A percent that is another thing's share.
        "I pay 1% a month in fees on my $10,000 loan",
        "My salary is $60,000 a year at 3% raise; my car loan is $20,000",
        # A rate by the month on a loan quoted by the year only.
        "How much is a $25,000 car loan at 1.9% a month?",
        "What's the payment on a $300k mortgage at 1% a month for 30 years?",
        "Student loan $30,000 at 0.0137% a day for 10 years",
    ],
)  # fmt: skip
def test_a_rate_whose_period_cannot_be_placed_works_no_numbers(text: str) -> None:
    assert read_money_request(text) is None


@pytest.mark.parametrize(
    ("text", "rate", "payment"),
    [
        ("A $10,000 loan at 2% (per month) for 2 years", 24, 528.71),
        ("A $10,000 loan at 2%/month for 2 years", 24, 528.71),
        ("personal loan of $10,000 at 1% a month for 2 years", 12, 470.73),
        ("A loan of $12,000 at 1.25% pm for 24 months", 15, 581.84),
        # The rate's own words, and a describing word of another noun beside them.
        ("I pay annual property tax of $5,000 on my $300k mortgage at 6% for 30 years. What is my payment?", 6, 1798.65),
        ("How much a month is a $300k mortgage at 6% for 30 years?", 6, 1798.65),
        ("What would a $20,000 car loan at 6% for 5 years cost per month?", 6, 386.66),
    ],
)  # fmt: skip
def test_a_rate_and_its_own_period_are_read(text: str, rate: float, payment: float) -> None:
    values, worked = _payment(text)
    assert (values["rate"], worked) == (rate, payment)


def test_a_cards_rate_by_the_month_is_its_apr() -> None:
    request = read_money_request(
        "I have $3,000 on my credit card at 2% a month and pay $150 a month"
    )
    assert request is not None and request.values["apr"] == 24
    worked = work(request, None)
    assert worked is not None and round(worked.outputs["months"] or 0, 2) == 25.80


@pytest.mark.parametrize(
    "text",
    [
        # "borrowed" with no rate, interest-free, or from someone who is no lender.
        "My brother borrowed $500 and makes payments of $50 a month. When will he be done?",
        "He borrowed $50,000 from his uncle with no interest, payments of $1,000 a month",
        "I borrowed $5,000 interest-free from my employer, payments come out of my paycheck",
        "She borrowed $3,000 from her mom at 2% and pays it back in 12 monthly payments",
        "My grandma borrowed $3,000 at 0% and pays $100 payments",
        # A stated payment with no term or no rate: what is missing is the question.
        "I borrowed $1,000 at 10% and my payment is $100 a month. How long?",
        "I took a $1,000 loan at 10% and my payment is $100 a month. How long?",
        "My car loan is $20,000 with 48 monthly payments of $500. What is my interest rate?",
        "Tom borrowed $2,000 at 8% per annum and made 24 payments. How much interest?",
        # Payments of another kind than the loan's level ones.
        "A $20,000 car loan at 6%, 48 monthly payments, plus 2 balloon payments",
        "A $20,000 car loan at 6% with 1 balloon payment",
        "A $20,000 car loan at 6% with 60 monthly payments and 12 late payments",
    ],
)  # fmt: skip
def test_a_loan_the_card_cannot_work_as_said_works_no_numbers(text: str) -> None:
    assert read_money_request(text) is None


@pytest.mark.parametrize(
    ("text", "product"),
    [
        ("Ato Kebede borrowed Birr 10,000 at 1.5% per month and repays it in 18 equal monthly payments.", "loan"),
        ("The company borrowed $1,000,000 at 5% with annual payments over 10 years", "loan"),
        ("A man borrowed Birr 20,000 from a bank at 12% and repays it in 24 monthly payments", "loan"),
    ],
)  # fmt: skip
def test_borrowed_at_a_rate_from_a_lender_and_repaid_is_a_loan(text: str, product: str) -> None:
    request = read_money_request(text)
    assert request is not None and request.product.key == product


@pytest.mark.parametrize(
    ("text", "per_year"),
    [
        ("savings at 6% compounded twice a year", 2),
        ("savings at 6% compounded four times a year", 4),
        ("savings at 6% compounded every three months", 4),
        ("savings at 6% compounded once a year", 1),
        ("savings at 6% compounded every 2 months", 0),
    ],
)
def test_compounding_reads_the_shared_vocabulary(text: str, per_year: int) -> None:
    assert compounding_per_year(text) == per_year


@pytest.mark.parametrize(
    "text",
    ["I save $500 twice a year", "I put in $50 every two weeks", "I save $100 twice a month"],
)
def test_a_sum_paid_by_another_period_than_monthly_is_no_monthly_sum(text: str) -> None:
    found = amounts(text)
    assert found is not None and found[0].other_period and not found[0].monthly


def test_a_quarterly_loans_reply_is_held_to_its_quarterly_payment() -> None:
    text = "A loan of $10,000 at 6% for 3 years, payable quarterly"
    request = read_money_request(text)
    assert request is not None
    worked = work(request, None)
    assert worked is not None
    wrong = card_figures("Your quarterly payment is $950.00.", request, worked)
    assert wrong is not None and "**$916.80** a quarter" in wrong.line
    assert card_figures("Your quarterly payment is $916.80.", request, worked) is None
    assert card_figures("That is $916.80 a quarter.", request, worked) is None
