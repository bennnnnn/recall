"""A loan is worked only when it is the level loan the card works, and the numbers are its own.

A third review (2026-11-14) found a count of payments read as the term whatever followed it
("with 24 monthly payments missed" over 24 months), another payee's payments setting the
loan's ("we pay our insurance in 4 quarterly payments"), a first payment timed otherwise
("the first one made today", "beginning at the end of the third year") or a balloon worked as
an ordinary loan, and rate periods the vocabulary lacked read as yearly ("2% per mth"). Also
on main: flat rates amortised, "six percent" and "interest rate: 6" replaced by today's
average, "a 3-year warranty" and "we plan to stay 7 years" read as the term, and two loans
named with one's numbers worked as the other's. Each now works no numbers, or the right ones.
Every expected payment is P·i / (1 - (1 + i)^-n), worked apart from the catalog.
"""

from __future__ import annotations

import pytest

from app.modules.money.read import read_money_request
from app.modules.money.solve import work


def _worked(text: str) -> tuple[dict[str, float], dict[str, float | None]]:
    request = read_money_request(text)
    assert request is not None, text
    worked = work(request, None)
    assert worked is not None, text
    return request.values, worked.outputs


@pytest.mark.parametrize(
    "text",
    [
        # A count followed by words that make it no term, or another loan's.
        "A $20,000 car loan at 6% with 24 monthly payments missed",
        "A $20,000 car loan at 6% with 24 monthly payments already made. What do I still owe?",
        "A $20,000 car loan at 6% with 12 monthly payments remaining",
        "My $30,000 student loan at 5% with 60 monthly payments deferred",
        "A $25,000 car loan at 7% with 36 monthly payments overdue",
        "A $300k mortgage at 6% with 120 monthly payments behind me",
        "A $10,000 loan at 8% over 24 monthly payments I already paid",
        "A $20,000 car loan at 6% with 36 monthly payments left",
        "A $20,000 car loan at 6% over 24 monthly payments that I missed",
        "A $40,000 student loan at 5% with 120 monthly payments forgiven",
        "A $20,000 car loan at 6% in 36 monthly payments on my old car",
        "A $20,000 car loan at 6%; I've got 3 years left",
        "A $20,000 car loan at 6% with 2 years left",
        # Another payee's payments in the loan's sentence.
        "A $20,000 car loan at 6%, and we pay our insurance in 4 quarterly payments",
        "A $20,000 car loan at 6%, and my phone is paid off in 24 monthly payments",
        "I have a $20,000 car loan at 6% and pay my tuition in 2 semi-annual payments",
        "A $25,000 car loan at 7%, and my sister repays her loan in 36 monthly payments",
        "A $20,000 car loan at 6% for 5 years, and we pay our insurance with quarterly payments",
    ],
)
def test_a_count_that_is_not_the_loans_term_works_no_numbers(text: str) -> None:
    assert read_money_request(text) is None


@pytest.mark.parametrize(
    "text",
    [
        # The first payment timed otherwise than a period after the loan is made.
        "A loan of $10,000 at 8% is repaid in 3 equal annual payments, the first made 3 years "
        "from now.",
        "A loan of Birr 50,000 at 10% per annum is to be repaid in 5 equal annual payments "
        "beginning at the end of the third year.",
        "A loan of $10,000 at 8% per annum is repaid in 5 equal annual payments, the first one "
        "made today.",
        "A loan of $10,000 at 8% per annum is repaid in 5 equal annual payments starting today.",
        "A loan of Birr 40,000 at 12% p.a. is repaid in 4 equal annual instalments, the first due "
        "at the end of 2 years.",
        "A loan of $15,000 at 9% is repaid in 6 semi-annual payments beginning 18 months from now.",
        "A loan of $10,000 at 8% is to be repaid in 5 equal annual payments in advance.",
        "A loan of $5,000 at 6% p.a. is repaid in 4 equal annual payments made at the beginning "
        "of each year.",
        "A $5,000 loan at 6% repaid in 4 equal annual instalments with a grace period of 2 years",
        "A $5,000 loan at 6% repaid in 4 annual payments after a 2 year deferment",
        "A $5,000 loan at 6% repaid in 4 annual payments, the first on signing",
        "A $12,000 car loan at 6% with 48 monthly payments starting 6 months from now",
        "Student loan of $30,000 at 5% repaid in 10 annual payments beginning after graduation",
        "Car loan $20,000 at 6% over 60 months, first payment due in 45 days",
        "Student loan of $27,000 at 4.99%, 6-month grace period, then 10 years",
        "$40k student loan at 5% for 10 years, but interest accrues during my 4 years of school",
        "My student loan of $30,000 at 5% starts repayment in 26 weeks",
        # A part of the loan left to its end, or another sum put into it.
        "A loan of $30,000 at 6% p.a. with 4 equal annual payments and a final balloon of $5,000",
        "A $30,000 loan at 6% p.a. with a $5,000 lump sum at the end and 4 equal annual payments",
        "A $30,000 car loan at 6% for 48 months with a $10,000 residual value",
        "A $30,000 car loan at 6% for 48 months, $10,000 due at the end",
        "A $30,000 car loan at 6% for 48 months with a guaranteed future value of $12,000",
        "Car loan $18,500 at 4.9% for 66 months, plus a $1,200 extended warranty rolled in",
    ],
)
def test_a_loan_of_another_shape_works_no_numbers(text: str) -> None:
    assert read_money_request(text) is None


@pytest.mark.parametrize(
    "text",
    [
        # A period the vocabulary does not read is no yearly rate.
        "Loan of $5,000 at 2% per six months for 2 years",
        "Loan of $2,000 at 1.5% per 30 days for 1 year",
        "Loan of $2,000 at 1.5% per two weeks for 1 year",
        "Loan of $5,000 at 3% per semester for 2 years",
        "Loan of $5,000 at 0.05% per diem for 1 year",
        "Loan of $5,000 at 1.5% per mensem for 2 years",
        "Loan of $5,000 at 1.5% month for 2 years",
        # A rate not charged on the balance.
        "Car loan ₹8,00,000 at 9% flat rate for 5 years. What is the EMI?",
        "A loan of $3,000 at 2% per month flat for 2 years",
        "A loan of 10,000 at a flat 9% for 2 years",
        "A $20,000 car loan at 6% add-on interest for 4 years",
        # A rate in words or with no percent: never today's average in its place.
        "A $20,000 car loan at six percent for 5 years",
        "$20,000 car loan, interest rate: 6, term 5 years",
        # A loan's effective rate is none the card charges.
        "A loan of $10,000 at an effective annual rate of 12.68% repaid monthly for 2 years",
        "Car loan $20,000 at 6% EAR for 5 years",
    ],
)
def test_a_rate_the_card_does_not_charge_works_no_numbers(text: str) -> None:
    assert read_money_request(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "My car loan is $15,000 at 5% and my student loan is $30,000",
        "A $25,000 car loan at 6% for 5 years; I also have a mortgage",
        "My savings account pays 0.5% per month. What's the payment on a $5,000 personal loan "
        "for 2 years?",
        "I'm borrowing $20,000 for a car and $5,000 for a motorbike at 7% for 4 years",
        "How much should I invest now at 5% to have $20,000 in 10 years?",
        "Mortgage: 300 000 €, 3,2 %, 25 Jahre",
    ],
)
def test_numbers_that_are_not_certainly_this_requests_work_none(text: str) -> None:
    assert read_money_request(text) is None


@pytest.mark.parametrize(
    ("text", "payment"),
    [
        # The vocabulary's short forms.
        ("Loan of $5,000 at 2% per mth for 12 months", 472.80),
        ("Personal loan $3,000 at 1.5% pcm for 1 year", 275.04),
        ("Loan of £4,000 at 1% per calendar month for 2 years", 188.29),
        ("Loan of $5,000 at 1.5% p/m for 2 years", 249.62),
        # The ordinary timing: the first payment a period after the loan is made.
        (
            "A loan of $12,000 at 10% per annum is repaid in 3 equal yearly payments, the first "
            "due one year from now.",
            4825.38,
        ),
        (
            "A loan of $60,000 at 10% p.a. is to be repaid in 5 equal annual installments, the "
            "first one due at the end of the first year.",
            15827.85,
        ),
        # The loan named after its rate, or with its numbers, is the payments' own.
        (
            "The quarterly rate is 2% on a $10,000 loan over 2 years with quarterly payments",
            1365.10,
        ),
        ("a $10,000 loan with an interest rate of 1% a month, 24 monthly payments", 470.73),
        (
            "A $4,000 loan at 1.5% per month on the outstanding balance, repaid in 24 monthly "
            "instalments",
            199.70,
        ),
        # A sum with spaced thousands put down is taken off the price.
        ("Car loan at 6% for 5 years: price 30 000, down 5 000", 483.32),
        ("Loan 10 000 at 6% for 3 years and 2 000 down", 243.38),
        # Look-alikes: a flat to live in, a late-fee window, a business started.
        ("I live in a flat; car loan of $20,000 at 6% for 5 years", 386.66),
        ("A $300,000 mortgage at 6% with a 2 week grace period", 1798.65),
        ("I'm starting a business and need a $50,000 loan at 8% for 5 years", 1013.82),
    ],
)
def test_the_loans_own_words_are_worked(text: str, payment: float) -> None:
    _, outputs = _worked(text)
    assert round(outputs["payment"] or 0.0, 2) == payment


@pytest.mark.parametrize(
    "text",
    [
        "Car loan $20,000 at 6%, 3-year warranty included",
        "I'm buying a car with a 7-year warranty at 6% on a $25,000 car loan",
        "Mortgage $300k at 6%, we plan to stay 7 years",
    ],
)
def test_a_length_that_is_another_things_is_no_term(text: str) -> None:
    values, _ = _worked(text)
    assert "months" not in values and "years" not in values


@pytest.mark.parametrize(
    "text",
    [
        "High-yield savings at 4.5% APY, $10,000 for 5 years",
        "Savings account, 4.5% AER, £10,000 for 5 years",
    ],
)
def test_a_savings_yield_grows_by_itself_each_year(text: str) -> None:
    # 10,000 * 1.045^5: a yield is what a year earns, however often it compounds.
    _, outputs = _worked(text)
    assert round(outputs["balance"] or 0.0, 2) == 12461.82


@pytest.mark.parametrize(
    ("text", "balance"),
    [
        # A loan's deferral words are none of a saving's: 5,000 * (1 + 0.06/12)^240.
        ("Invest $5,000 in a tax-deferred account at 6% for 20 years", 16551.02),
        # 500 * ((1 + 0.05/12)^120 - 1) / (0.05/12).
        ("After college I will save $500 a month at 5% for 10 years", 77641.14),
    ],
)
def test_a_savings_plan_is_not_held_to_a_loans_deferral(text: str, balance: float) -> None:
    _, outputs = _worked(text)
    assert round(outputs["balance"] or 0.0, 2) == balance
