"""A rate charged by the month or the quarter, payments made quarterly, and a term told as a
count of payments are worked as the words say, or not at all.

Live (2026-11-14, an Ethiopian grade 12 book): "repay the loan in 48 equal monthly payments
… the bank charges 2% per month on the unpaid balance, compounded monthly" was worked as a
yearly rate of 2% over a 5-year term the user never gave: 1,665.14 a month where the loan
costs 3,097.17. Every expected number here is the textbook formula worked apart from the
catalog: a payment P·i / (1 - (1 + i)^-n) at the period's rate i over n payments, a card's
months -log(1 - i·B/p) / log(1 + i), a balance P·(1 + i)^n.
"""

from __future__ import annotations

import pytest

from app.modules.money.block import money_block
from app.modules.money.fence import calculator_fence
from app.modules.money.follow_up import follow_up_request
from app.modules.money.note import market_note
from app.modules.money.read import read_money_request
from app.modules.money.solve import Worked, work
from app.modules.money.worked_problem import lays_out_working
from app.tests.modules.money.money_support import average
from app.tests.modules.money.test_money_card import _spec

B098 = (
    "Suppose you borrow Birr 95,000 from a bank and agree to repay the loan in 48 equal "
    "monthly payments. If the bank charges 2% per month on the unpaid balance, compounded "
    "monthly, how much is each payment?"
)
QUARTERLY = (
    "Birr 20,000 is borrowed at 3% per quarter and repaid in 8 equal quarterly payments. "
    "Find the payment."
)


def _worked(text: str) -> Worked:
    request = read_money_request(text)
    assert request is not None, text
    worked = work(request, None)
    assert worked is not None, text
    return worked


@pytest.mark.parametrize(
    ("text", "output", "expected"),
    [
        # 95,000·0.02/(1 - 1.02^-48)
        (B098, "payment", 3097.17),
        ("I borrow $10,000 at 1% per month for 24 months. What is the monthly payment?", "payment", 470.73),
        ("A loan of 50,000 at 12% annual interest is repaid in 36 monthly payments. What is the payment?", "payment", 1660.72),
        ("Find the monthly payment on a 200,000 loan at 0.5% per month over 10 years", "payment", 2220.41),
        (QUARTERLY, "payment", 2849.13),
        ("A loan of 12,000 at a monthly interest rate of 1.5% is repaid in 24 monthly payments.", "payment", 599.09),
        ("Ato Kebede borrowed Birr 10,000 at 1.5% per month and repays it in 18 equal monthly payments.", "payment", 638.06),
        ("A loan of 6,000 at 1% a month is repaid in twenty-four monthly instalments.", "payment", 282.44),
        ("Rs 50,000 loan at 1% p.m. repaid in 24 EMIs", "payment", 2353.67),
        ("Loan 5000 at 1% per month repaid in 12 equal payments", "payment", 444.24),
        ("personal loan of $10,000 at 1% a month for 3 years", "payment", 332.14),
        # Payments made other than monthly: the yearly rate over that many payments a year.
        ("A loan of 30,000 at 10% per year is repaid in 5 equal annual payments.", "payment", 7913.92),
        ("A loan of 30,000 at 6% per half-year repaid in 10 semi-annual payments", "payment", 4076.04),
        ("A loan of 8,000 at 6% per year compounded quarterly is repaid in 12 quarterly payments.", "payment", 733.44),
        ("loan of 40,000 at 9% over 8 quarters with quarterly payments", "payment", 5519.38),
        ("car loan of 20k at 6% for 5 years with weekly payments", "payment", 89.08),
        ("a 20k car loan at 6% with 52 payments a year for 5 years", "payment", 89.08),
        # A card's APR is its periodic rate times the periods a year.
        ("I have a credit card balance of $3,000 at 2% per month and pay $150 a month. How long to pay it off?", "months", 25.80),
        ("I owe $2,000 on my credit card at 1.5% a month and pay $100 a month. How long?", "months", 23.96),
        ("credit card debt of 4000 at 0.05% per day, I pay 200 a month", "months", 24.03),
        ("credit card balance of $3,000 at 24% APR with a monthly payment of $150, how long to pay off?", "months", 25.80),
        # Savings compound by the period their rate is charged by.
        ("I deposit $5,000 in a savings account at 2% per quarter compounded quarterly for 3 years.", "balance", 6341.21),
        ("Put 2,000 in a savings account at 2% per half-year for 3 years, compounded semi-annually", "balance", 2252.32),
        ("Put 1000 into a savings account at 0.75% a month for 2 years", "balance", 1196.41),
        ("savings account at 0.5% per month, I put in 300 a month for 4 years", "balance", 16229.35),
        # 200·(1.005^36 - 1)/0.005: 36 monthly deposits, never a 200 start and a 36 deposit.
        ("I save with 36 monthly deposits of $200 into a savings account at 6%. How much will I have?", "balance", 7867.22),
    ],
)  # fmt: skip
def test_a_rate_and_term_said_by_their_period_are_worked_as_said(
    text: str, output: str, expected: float
) -> None:
    worked = _worked(text)
    assert worked.assumed in ((), ("start",), ("deposit",)), worked.assumed
    value = worked.outputs[output]
    assert value is not None and round(value, 2) == expected


@pytest.mark.parametrize(
    ("text", "name", "value"),
    [
        (B098, "rate", 24),
        (B098, "years", 4),
        (QUARTERLY, "rate", 12),
        (QUARTERLY, "years", 2),
        ("personal loan of 20000 at 1% a month over 36 monthly payments", "months", 36),
        ("I deposit $5,000 in a savings account at 2% per quarter compounded quarterly for 3 years.", "rate", 8),
    ],
)  # fmt: skip
def test_the_yearly_rate_and_the_term_are_read_from_the_periods(
    text: str, name: str, value: float
) -> None:
    request = read_money_request(text)
    assert request is not None and request.values[name] == value


@pytest.mark.parametrize(
    "text",
    [
        # A rate's period that may be how often it is paid or compounded.
        "savings account paying 4% monthly, 200 a month for 5 years",
        "car loan of 20k at 1.5% monthly for 3 years",
        "a savings account that pays interest each month at 4%, 200 a month for 5 years",
        "the bank charges interest per month at the rate of 2% on a loan of 10,000 over 2 years",
        # A rate charged by one period and paid or compounded by another.
        "Birr 20,000 is borrowed at 3% per quarter. Find the monthly payment over 2 years.",
        "Birr 20,000 is borrowed at 3% per quarter and repaid in 8 equal payments.",
        "a loan of 10,000 at 12% per year compounded monthly with quarterly payments for 2 years",
        "a loan of 10,000 at 1% per month, compounded quarterly, for 2 years",
        "car loan 20k at 6% paid quarterly for 5 years, what is the monthly payment",
        "I deposit $5,000 in a savings account at 5% per quarter compounded monthly for 3 years.",
        # A frequency no product pays, or deposits made other than monthly.
        "car loan 20k at 6%, bi-weekly payments, 5 years",
        "mortgage of 300k at 6% for 30 years with payments every two weeks",
        "She makes quarterly deposits of $500 into a savings account at 8% for 5 years.",
        "I have $3,000 on my credit card at 24% APR and make quarterly payments of $300",
        # A count of payments or a length no word says how to read, and no other term.
        "car loan 20k at 6% with 60 payments",
        "repay a 2000 loan at 5% in 90 days",
        # A count of payments that is not said as the term, with no other term.
        "I make 36 monthly deposits of $200 into a savings account at 6%. How much will I have?",
        # Another payee's payments in the loan's own sentence: no level loan the card works.
        "my rent payments each month are 1500, mortgage 300k at 6% for 30 years payment?",
        # A rate by the month on a loan only ever quoted by the year (2026-11-14 review).
        "a mortgage of 300k at 0.5% a month for 30 years",
        "car loan of $20,000 at 1% a month for 5 years",
        "How much is a $25,000 car loan at 1.9% a month?",
        "student loan of $30,000 at 0.4% a month for 10 years",
        "car loan of 20000 at 1% a month over 36 monthly payments",
    ],
)
def test_a_period_the_words_leave_open_works_no_numbers(text: str) -> None:
    assert read_money_request(text) is None


@pytest.mark.parametrize(
    ("text", "name", "value"),
    [
        # A sum or a speed per period that is no rate and no payment.
        ("My salary is 5,000 per month and I want a car loan of 20,000 at 6%. What is the monthly payment?", "rate", 6),
        ("My phone plan is $40 per month. What is the payment on a 10,000 loan at 7% for 3 years?", "amount", 10000),
        ("I drive at 60 miles per hour to the bank. Loan of 15000 at 8% for 4 years payment?", "years", 4),
        ("I run at 10 km per hour; car loan 15000 at 7% for 4 years", "months", 48),
        ("I get paid weekly. Car loan of 20k at 6% for 5 years, what's the monthly payment?", "months", 60),
        ("My salary is Birr 8,000 per month. What would a loan of Birr 50,000 at 12% for 3 years cost each month?", "rate", 12),
        # Another thing's period in a sentence of its own, and a period a time is said in.
        ("Property tax is 3,000 each year. What's the payment on a 300k mortgage at 6% over 30 years?", "amount", 300000),
        ("My rent payments each month are 1500. Mortgage 300k at 6% for 30 years, payment?", "rate", 6),
        ("I have 30 days to decide on a 20k car loan at 6% for 60 months", "months", 60),
        # Payments gone by are no term; a monthly payment beside a monthly count is one.
        ("I made 12 monthly payments on my car loan of 20k at 6% for 5 years", "months", 60),
        ("a $20,000 car loan at 6% monthly payments over 5 years", "rate", 6),
        ("a 20k car loan at 6% with 12 payments a year for 5 years", "months", 60),
        ("6% a year for 10 years: I deposit 500 every month into savings", "rate", 6),
        ("I'll save $200 a month at 5% per annum for 20 years", "rate", 5),
    ],
)  # fmt: skip
def test_a_period_beside_another_number_keeps_the_yearly_monthly_reading(
    text: str, name: str, value: float
) -> None:
    request = read_money_request(text)
    assert request is not None, text
    assert request.values[name] == value
    assert request.rate_per == 1 and "payments" not in request.settings


def test_the_block_says_the_users_rate_and_how_often_the_loan_is_paid() -> None:
    request = read_money_request(QUARTERLY)
    assert request is not None
    block = money_block(request, work(request, None), None)
    assert "yearly rate 12% (the user's 3% a quarter, times 4)" in block
    assert "payments quarterly" in block
    assert "quarterly payment 2,849.13" in block
    assert "monthly payment" not in block


def test_the_card_names_a_quarterly_payment_and_holds_its_number() -> None:
    worked = _worked(QUARTERLY)
    spec = _spec(calculator_fence(worked, None, "ETB"))
    payment = next(readout for readout in spec.readouts if readout.name == "payment")
    assert payment.label_key == "money.quarterly_payment"
    assert "payments" not in str(payment.tree)
    assert {control.name: control.value for control in spec.controls}["rate"] == 12


def test_a_monthly_loan_keeps_its_monthly_label() -> None:
    spec = _spec(calculator_fence(_worked(B098), None, "ETB"))
    assert spec.readouts[0].label_key == "money.monthly_payment"


def test_a_lessons_loan_with_its_count_of_payments_is_laid_out() -> None:
    """The 48 payments are the term, so nothing is assumed and nothing stated goes unused."""
    request = read_money_request(B098)
    assert request is not None
    assert lays_out_working(B098, request, work(request, None))


def test_a_rate_said_by_the_month_is_judged_as_the_yearly_rate_it_is() -> None:
    worked = _worked("personal loan of $10,000 at 2.5% a month for 3 years")
    note = market_note(worked, average(12, "personal loan interest rate"), 2.0)
    assert note is not None
    assert note.startswith("**Note:** 2.5% a month (30% a year) is not a realistic")


def test_a_monthly_rate_near_the_average_is_no_unrealistic_rate() -> None:
    worked = _worked("personal loan of $10,000 at 1% a month for 3 years")
    note = market_note(worked, average(12, "personal loan interest rate"), 2.0)
    assert note is not None and "not a realistic" not in note


def test_a_bare_rate_after_a_rate_by_the_month_is_left_to_the_model() -> None:
    """A bare "what about 1.5%?" after "2% a month" may be a month's or a year's rate."""
    earlier = ["I borrow $10,000 at 2% per month for 24 months. What is the monthly payment?"]
    assert follow_up_request("what about 1.5%?", earlier) is None


def test_a_new_term_keeps_how_often_the_loan_is_paid() -> None:
    changed = follow_up_request("what if 3 years instead", [QUARTERLY])
    assert changed is not None
    assert changed.values["years"] == 3 and changed.settings == {"payments": 4}
    worked = work(changed, None)
    assert worked is not None and worked.outputs["payment"] is not None
    # 20,000·0.03/(1 - 1.03^-12)
    assert round(worked.outputs["payment"], 2) == 2009.24


@pytest.mark.parametrize(
    "text",
    [
        # A yearly rate said casually with "per month": no 72% mortgage (2026-11-14 review).
        "How much would I pay on a $300k mortgage at 6% per month?",
        "how much is a $25,000 car loan at 5% per month over 5 years",
        "what's a 300k mortgage at 6.5% a month for 30 years",
        "A $20,000 car loan at 6% per month for 60 months",
        "student loan of $30,000 at 4% a month for 10 years",
        "credit card balance of $3,000 at 5% a month, paying $150 a month",
        "I put $5,000 in a savings account at 5% per quarter for 3 years",
        "If I borrow $1,000 at 5% per month and pay nothing for a year, how much will I owe?",
        # A rate's period the words leave open: as "1.5% monthly".
        "A loan of $10,000, 2% interest monthly, 3 years",
        "A loan of $10,000 with monthly interest at 2% for 3 years",
        "car loan of 20k with interest each month at 1.5% for 3 years",
    ],
)
def test_a_rate_by_the_period_that_leaves_the_products_rates_is_not_worked(text: str) -> None:
    assert read_money_request(text) is None


@pytest.mark.parametrize(
    ("text", "rate", "per"),
    [
        # A time is no rate's period.
        ("If I take a $20,000 car loan at 6% a month from now, what's the payment?", 6, 1),
        ("A $20,000 car loan at 6% a month later, what's the payment over 5 years?", 6, 1),
        ("$300k mortgage at 6.5% a year from now for 30 years", 6.5, 1),
        ("$20,000 car loan at 6%, a month from now rates may rise", 6, 1),
        # "pm" is per month, as "p.m." and "pa" are.
        ("A loan of $12,000 at 1.25% pm for 24 months", 15, 12),
        ("A loan of $12,000 at 1.25% p.m. for 24 months", 15, 12),
        ("A loan of $12,000 at 15% pa for 2 years", 15, 1),
        # The yearly words: one yearly rate either way.
        ("A loan of $10,000 at 6% interest annually for 3 years", 6, 1),
        ("A loan of $10,000 with annual interest at 6% for 3 years", 6, 1),
        # A product's plausible rate, said by the month.
        ("personal loan of $20,000 at 1% a month for 5 years", 12, 12),
        ("I owe $3,000 on my credit card at 2% a month and pay $150 a month", 24, 12),
    ],
)
def test_a_rate_said_by_its_period_or_as_a_time(text: str, rate: float, per: int) -> None:
    request = read_money_request(text)
    assert request is not None, text
    name = "apr" if request.product.family == "card_payoff" else "rate"
    assert (request.values[name], request.rate_per) == (rate, per)


def test_a_rate_by_the_month_is_labelled_as_the_yearly_rate_on_the_slider() -> None:
    spec = _spec(calculator_fence(_worked(B098), None, "ETB"))
    rate = next(control for control in spec.controls if control.name == "rate")
    assert (rate.label_key, rate.value) == ("money.yearly_rate", 24)


@pytest.mark.parametrize(
    ("text", "name", "label"),
    [
        ("A loan of 50,000 at 12% annual interest repaid in 36 monthly payments", "rate", "money.rate"),
        ("a mortgage of 300k at 6% for 30 years", "rate", "money.rate"),
        # An APR says it is yearly already.
        ("I owe $2,000 on my credit card at 1.5% a month and pay $100 a month", "apr", "money.apr"),
    ],
)  # fmt: skip
def test_a_yearly_rate_keeps_its_own_label(text: str, name: str, label: str) -> None:
    spec = _spec(calculator_fence(_worked(text), None, "USD"))
    assert next(control for control in spec.controls if control.name == name).label_key == label
