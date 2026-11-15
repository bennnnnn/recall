"""A frequency changes how often a loan is paid only when it is the loan's own schedule.

A review of the rate-period reader (2026-11-14) found any "pay" or "paid" before a frequency
setting the loan's schedule: "$300,000 mortgage at 6% for 30 years, how much do I pay
annually?" worked one payment a year of 21,794.67 (the mortgage is 1,798.65 a month), and
school fees, HOA dues, a wage and extra payments each moved the loan to their frequency. It
also found "borrowed" naming a loan in growth questions and everyday lines, and a yearly
car loan's term slider stopping at half a payment. Every expected payment is the textbook
P·i / (1 - (1 + i)^-n), worked apart from the catalog.
"""

from __future__ import annotations

import json

import pytest

from app.modules.money.fence import calculator_fence
from app.modules.money.follow_up import follow_up_request
from app.modules.money.read import read_money_request
from app.modules.money.solve import work

MORTGAGE = "A $300,000 mortgage at 6% for 30 years"
LOAN = "A $10,000 loan at 6% for 3 years"


def _payment(text: str) -> tuple[dict[str, float], float]:
    request = read_money_request(text)
    assert request is not None, text
    worked = work(request, None)
    assert worked is not None and worked.outputs["payment"] is not None, text
    return request.settings, round(worked.outputs["payment"], 2)


@pytest.mark.parametrize(
    ("text", "payment"),
    [
        # A question about what a period costs asks a total: the loan stays monthly.
        ("$300,000 mortgage at 6% for 30 years, how much do I pay annually?", 1798.65),
        (f"{LOAN}, how much interest do I pay per year?", 304.22),
        (f"{LOAN}. What do I pay each quarter?", 304.22),
        (f"{LOAN}. How much would I pay a year?", 304.22),
        ("Tell me how much I'd pay a year on a $10,000 loan at 6% for 3 years", 304.22),
        ("$300,000 mortgage at 6% for 30 years, total paid yearly?", 1798.65),
        # Something else paid by the period.
        (f"{MORTGAGE}, school fees paid quarterly", 1798.65),
        (f"{MORTGAGE}, HOA dues paid quarterly", 1798.65),
        (f"{MORTGAGE}, my HOA payments are quarterly", 1798.65),
        (f"{MORTGAGE}, my property taxes are paid half-yearly", 1798.65),
        (f"{MORTGAGE}. The seller wants the deposit paid weekly", 1798.65),
        (f"{MORTGAGE}, I pay my rent weekly", 1798.65),
        (f"{LOAN} with interest paid quarterly", 304.22),
        ("A $20,000 car loan at 6% for 5 years, my insurance premium is payable yearly", 386.66),
        # A wage.
        (f"{MORTGAGE}, I earn $2,000 paid weekly", 1798.65),
        (f"{LOAN}. My pay is weekly.", 304.22),
        (f"{MORTGAGE}, and my wife gets paid every week", 1798.65),
        (f"{MORTGAGE}, my husband is paid weekly", 1798.65),
        # Payments made beside the loan's own.
        (f"{MORTGAGE}, I can make extra payments annually", 1798.65),
        (f"{MORTGAGE}, plus additional payments yearly", 1798.65),
        (f"{MORTGAGE}; my student loan payments are quarterly", 1798.65),
        ("A $20,000 car loan at 6% for 5 years; my mortgage payments are weekly", 386.66),
        # Paid monthly, said as monthly.
        ("I'm paid quarterly but pay monthly on my $300,000 mortgage at 6% for 30 years", 1798.65),
    ],
)
def test_a_frequency_that_is_not_the_loans_schedule_leaves_it_monthly(
    text: str, payment: float
) -> None:
    assert _payment(text) == ({}, payment)


@pytest.mark.parametrize(
    ("text", "payments", "payment"),
    [
        ("A loan of $10,000 at 6% for 3 years, payable quarterly", 4, 916.80),
        (f"{LOAN}. I'm paying it weekly", 52, 70.08),
        (f"{MORTGAGE}. I will pay it off weekly", 52, 414.79),
        (f"{MORTGAGE}, paid back yearly", 1, 21794.67),
        ("A loan of $10,000 at 6% for 3 years is repaid quarterly", 4, 916.80),
        ("A loan of $10,000 at 6% for 3 years, to be repaid in quarterly instalments", 4, 916.80),
        (f"{LOAN} and I want to pay weekly", 52, 70.08),
        ("What's the payment on a $10,000 loan at 6% for 3 years if I pay weekly?", 52, 70.08),
        ("What's the payment on a $10,000 loan at 6% for 3 years, paying weekly?", 52, 70.08),
        ("A loan of $10,000 paid quarterly over 3 years at 6%", 4, 916.80),
        (f"{LOAN}, the payments are quarterly", 4, 916.80),
        ("car loan 20k at 6% paid quarterly for 5 years", 4, 1164.91),
        ("I'd go for 12 quarterly payments on a loan of 10,000 at 6%", 4, 916.80),
        ("A $20,000 car loan at 6% for 2 years, 8 quarterly payments", 4, 2671.68),
        ("A $10,000 loan at 6% quarterly payments for 3 years", 4, 916.80),
        ("A $10,000 loan at 6% for 3 years quarterly payments", 4, 916.80),
        ("A $10,000 loan at 6% for 3 years with 4 equal payments a year", 4, 916.80),
    ],
)
def test_the_loans_own_schedule_is_worked(text: str, payments: int, payment: float) -> None:
    assert _payment(text) == ({"payments": payments}, payment)


@pytest.mark.parametrize(
    "text",
    [
        # Two frequencies offered.
        f"{LOAN} with monthly or quarterly payments",
        f"{LOAN}, should I pay weekly or monthly?",
        # A percent before "paid quarterly": the interest's, or the loan's.
        "Car loan of 20k for 5 years; the bank wants 6% paid quarterly",
        # Payments that may be another's: extra ones, or the loan's under a verb not read.
        f"{LOAN}, I want to make extra quarterly payments",
        "I can manage quarterly payments on a 10,000 loan at 6% for 3 years",
        # "The yearly payment" with no schedule said: twelve monthly ones, or one a year.
        "What is my yearly mortgage payment on $300,000 at 6% for 30 years?",
        "What's the quarterly payment on a $10,000 loan at 6% for 3 years?",
        # A count said by another frequency than the loan is read as paid by.
        "A loan of $10,000 at 6%, repaid quarterly, and I can manage 36 monthly payments",
        # A term that is no whole number of its payments.
        "car loan of 20k at 6% for 30 months with yearly payments",
        "a loan of 10,000 at 6% for 2.5 years with annual payments",
    ],
)
def test_a_schedule_the_words_leave_open_works_no_numbers(text: str) -> None:
    assert read_money_request(text) is None


def test_the_quarterly_payment_asked_beside_quarterly_compounding_is_worked() -> None:
    """A lone "the quarterly payment" stands on a schedule said elsewhere: the compounding."""
    text = "Find the quarterly payment on a loan of 10,000 at 6% compounded quarterly for 3 years"
    assert _payment(text) == ({"payments": 4}, 916.80)


@pytest.mark.parametrize(
    "text",
    [
        # Growth or simple interest: no amortised loan.
        "Tom borrowed $2,000 at 8% per annum. How much interest after 3 years?",
        "Tom borrowed $2,000 at 8% per annum for 3 years. Find the interest.",
        "I borrowed $500 from my brother at 2% per month, how much do I owe after 6 months?",
        "He borrowed 2,000 birr and pays 10% interest per month. How much interest after 3 months?",
        "She borrows $3,000 at 1.5% a month; what does she owe after a year?",
        # Everyday lines.
        "My sister borrowed $200 from me last week and paid back 10%",
        "I borrowed $50 from my friend and she wants 5% back next week",
        "I borrowed 10k from my dad, I pay him back 500 a month, no interest",
        "He borrows $20 from me every week and pays back 10% more",
    ],
)
def test_borrowed_without_its_payments_is_no_loan(text: str) -> None:
    assert read_money_request(text) is None


@pytest.mark.parametrize(
    ("text", "product"),
    [
        ("I borrowed $15,000 for a car at 7% for 5 years", "car"),
        ("We borrowed $250,000 for our house at 6.5% over 30 years", "mortgage"),
        ("she borrows the rest at 6% for 15 years after paying $40,000 on a $240,000 condo", "mortgage"),
        ("I borrowed $15,000 for a car at 7%, what is the monthly payment?", "car"),
        ("I borrowed $8,000 at 3% per quarter and will repay in 8 quarterly payments", "loan"),
    ],
)  # fmt: skip
def test_a_product_word_outranks_borrowed(text: str, product: str) -> None:
    request = read_money_request(text)
    assert request is not None and request.product.key == product


def test_a_car_loan_paid_yearly_slides_by_whole_payments() -> None:
    request = read_money_request("car loan $20,000 at 6% repaid in 3 annual payments")
    assert request is not None
    worked = work(request, None)
    assert worked is not None and round(worked.outputs["payment"] or 0, 2) == 7482.20
    fence = calculator_fence(worked, None, "USD")
    assert fence is not None
    controls = {item["name"]: item for item in json.loads(fence.split("\n")[1])["controls"]}
    months = controls["months"]
    assert (months["min"], months["max"], months["step"], months["value"]) == (12, 96, 12, 36)


@pytest.mark.parametrize(
    ("text", "low", "step"),
    [
        ("personal loan $9,000 at 10% with yearly payments for 3 years", 12, 12),
        ("personal loan $9,000 at 10% with half-yearly payments for 3 years", 6, 6),
        ("car loan of 20k at 6% for 5 years with quarterly payments", 12, 6),
        ("car loan of 20k at 6% for 5 years with weekly payments", 12, 6),
        ("car loan of 20k at 6% for 5 years", 12, 6),
    ],
)
def test_every_term_on_the_slider_is_a_whole_number_of_payments(
    text: str, low: float, step: float
) -> None:
    request = read_money_request(text)
    assert request is not None
    fence = calculator_fence(work(request, None), None, "USD")  # type: ignore[arg-type]
    assert fence is not None
    months = next(
        item for item in json.loads(fence.split("\n")[1])["controls"] if item["name"] == "months"
    )
    assert (months["min"], months["step"]) == (low, step)
    payments = request.settings.get("payments", 12)
    stops = range(int(months["min"]), int(months["max"]) + 1, int(months["step"]))
    assert all((stop * payments / 12).is_integer() for stop in stops)


def test_a_new_term_of_part_payments_is_left_to_the_model() -> None:
    earlier = ["car loan $20,000 at 6% repaid in 3 annual payments"]
    assert follow_up_request("what if 30 months instead", earlier) is None
    changed = follow_up_request("what if 4 years instead", earlier)
    assert changed is not None and changed.values["months"] == 48
