"""A frequency changes how often a loan is paid only when it is the loan's own schedule.

Two reviews of the rate-period reader (2026-11-14) found another thing's frequency setting
the loan's schedule: "$300,000 mortgage at 6% for 30 years, how much do I pay annually?"
worked one payment a year of 21,794.67 (the mortgage is 1,798.65 a month), and school fees,
HOA dues, a wage paid weekly after a comma, extra payments, "quarterly taxes" and a car
lease's payments each moved the loan to their frequency. Only a positive form in the loan's
own sentence sets it now; a non-monthly frequency of payments there in any other form works
no numbers, and one in a sentence about something else is ignored. It also found
"borrowed" naming a loan in growth questions and everyday lines, and a yearly car loan's term
slider stopping at half a payment. Every expected payment is the textbook
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
        # Something else paid by the period, in a sentence of its own.
        ("My salary is $4,000, paid weekly. What's my payment on a $300,000 mortgage at 6% for 30 years?", 1798.65),
        ("I earn $2,000, paid weekly. What would a $20,000 car loan at 7% for 5 years cost me?", 396.02),
        (f"{MORTGAGE}. HOA dues are $300, paid quarterly.", 1798.65),
        (f"{MORTGAGE}. Property tax is $4,000, paid yearly.", 1798.65),
        ("Nurse, paid weekly. What's the payment on a $250,000 mortgage at 6.5% for 30 years?", 1580.17),
        ("We pay quarterly taxes. Our $400,000 mortgage at 6.5% for 30 years, what's the payment?", 2528.27),
        ("I pay weekly for daycare. What's my payment on a $300,000 mortgage at 6% for 30 years?", 1798.65),
        (f"{MORTGAGE}. I pay my bills weekly.", 1798.65),
        (f"{MORTGAGE}. I get my paycheck weekly.", 1798.65),
        (f"{MORTGAGE}. My bonus is paid yearly.", 1798.65),
        (f"{MORTGAGE}. Dividends are paid quarterly.", 1798.65),
        (f"{LOAN}. My pay is weekly.", 304.22),
        ("A $20,000 car loan at 7% for 5 years. My wife gets paid weekly and I'm paid monthly.", 396.02),
        # A describing word of another noun in the loan's own sentence.
        ("I pay annual property tax of $5,000 on my $300,000 mortgage at 6% for 30 years. What is my payment?", 1798.65),
        ("I pay yearly insurance on my car. What is the payment on a $25,000 car loan at 6% for 5 years?", 483.32),
        ("I need a $10,000 loan at 6% for 3 years to pay quarterly tuition", 304.22),
        (f"{MORTGAGE} with weekly reminders to pay", 1798.65),
        # Paid monthly, said as monthly, also as a count.
        (f"{MORTGAGE}, twelve payments a year", 1798.65),
        (f"{MORTGAGE} with 12 payments each year", 1798.65),
    ],
)  # fmt: skip
def test_a_frequency_that_is_not_the_loans_schedule_leaves_it_monthly(
    text: str, payment: float
) -> None:
    assert _payment(text) == ({}, payment)


@pytest.mark.parametrize(
    ("text", "payments", "payment"),
    [
        ("A loan of $10,000 at 6% for 3 years, payable quarterly", 4, 916.80),
        (f"{MORTGAGE}, paid back yearly", 1, 21794.67),
        ("A loan of $10,000 at 6% for 3 years is repaid quarterly", 4, 916.80),
        ("A loan of $10,000 at 6% for 3 years, to be repaid in quarterly instalments", 4, 916.80),
        ("A loan of $10,000 paid quarterly over 3 years at 6%", 4, 916.80),
        (f"{LOAN}, the payments are quarterly", 4, 916.80),
        ("car loan 20k at 6% paid quarterly for 5 years", 4, 1164.91),
        ("I'd go for 12 quarterly payments on a loan of 10,000 at 6%", 4, 916.80),
        ("A $20,000 car loan at 6% for 2 years, 8 quarterly payments", 4, 2671.68),
        ("A $10,000 loan at 6% quarterly payments for 3 years", 4, 916.80),
        ("A $10,000 loan at 6% for 3 years quarterly payments", 4, 916.80),
        ("A $10,000 loan at 6% for 3 years with 4 equal payments a year", 4, 916.80),
        # Counted, spelled or in digits, as the one vocabulary reads it.
        (f"{LOAN}, paid twice a year", 2, 1845.98),
        (f"{LOAN}, repaid once a year", 1, 3741.10),
        (f"{LOAN}, paid four times a year", 4, 916.80),
        (f"{LOAN} with 2 payments per year", 2, 1845.98),
        (f"{LOAN} with two payments a year", 2, 1845.98),
        (f"{LOAN} with two equal payments a year", 2, 1845.98),
        (f"{LOAN} paid every 3 months", 4, 916.80),
        (f"{LOAN} paid every six months", 2, 1845.98),
        ("A $300,000 mortgage at 6% for 30 years with four payments a year", 4, 5405.56),
        ("A $300,000 mortgage at 6% for 30 years, fifty-two payments a year", 52, 414.79),
    ],
)
def test_the_loans_own_schedule_is_worked(text: str, payments: int, payment: float) -> None:
    assert _payment(text) == ({"payments": payments}, payment)


@pytest.mark.parametrize(
    "text",
    [
        # Another thing's frequency in the loan's own sentence, or in one about payments.
        "$300,000 mortgage at 6% for 30 years, total paid yearly?",
        f"{MORTGAGE}, school fees paid quarterly",
        f"{MORTGAGE}, HOA dues paid quarterly",
        f"{MORTGAGE}, my HOA payments are quarterly",
        f"{MORTGAGE}, my property taxes are paid half-yearly",
        f"{MORTGAGE}, I pay my rent weekly",
        f"{MORTGAGE}, I earn $2,000 paid weekly",
        f"{MORTGAGE}, insurance $1,200, paid annually",
        f"{MORTGAGE}, and my wife gets paid every week",
        f"{MORTGAGE}, I can make extra payments annually",
        f"{MORTGAGE}, plus additional payments yearly",
        f"{MORTGAGE}; my student loan payments are quarterly",
        f"{MORTGAGE}; I also make quarterly payments on my student loan",
        f"{MORTGAGE}. I make weekly payments to my credit card.",
        "I'm self-employed with quarterly payments to the IRS. What's my payment on a $300,000 mortgage at 6% for 30 years?",
        "My $300,000 mortgage at 6% for 30 years. I also have a car lease; the payments are quarterly.",
        "A $20,000 car loan at 6% for 5 years; my mortgage payments are weekly",
        "A $10,000 loan at 8% for 3 years to cover rent, paid weekly",
        "A $15,000 personal loan at 9% for 3 years, paid annually by my employer as a bonus",
        "Can I afford a $300,000 mortgage at 6% for 30 years if I'm paid every week?",
        f"{LOAN} with interest paid quarterly",
        # The loan's own schedule, but not said in the loan's own sentence or form.
        f"{LOAN}. I'm paying it weekly",
        f"{MORTGAGE}. I will pay it off weekly",
        f"{LOAN} and I want to pay weekly",
        "What's the payment on a $10,000 loan at 6% for 3 years if I pay weekly?",
        f"{LOAN}. The payments are quarterly.",
        f"{MORTGAGE}. What is my quarterly payment?",
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
        # A count of payments the words do not give whole.
        f"{MORTGAGE} with a dozen payments a year",
        f"{LOAN} with several payments a year",
        # A count said by another frequency than the loan is read as paid by.
        "A loan of $10,000 at 6%, repaid quarterly, and I can manage 36 monthly payments",
        # A term that is no whole number of its payments.
        "car loan of 20k at 6% for 30 months with yearly payments",
        "a loan of 10,000 at 6% for 2.5 years with annual payments",
        # Bare frequencies in a list: whose they are is not said.
        "$300k mortgage, 6%, 30 years, weekly",
        "$300k mortgage, 6%, 30 years, quarterly",
    ],
)  # fmt: skip
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
