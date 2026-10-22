"""Every money product as data: its inputs, its formulas, its words and its rate lookup.

A product is one row. Its outputs are expressions over its input names, in the closed
language of ``services/law_binding/expression.py``: the server works the asked numbers
with them and the phone redraws the card from the same trees (docs/money.md). Nothing
else branches on a product's name, so a new product is a new row.

Rates are yearly percentages (``rate`` 6.5 is 6.5 %), compounded monthly, and payments
are monthly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Format = Literal["money", "percent", "years", "months", "number"]
Family = Literal["loan", "card_payoff", "savings"]


@dataclass(frozen=True)
class Span:
    """How a slider's range follows the asked value.

    ``scale``: from ``low`` times the value to ``high`` times it (``base`` stands in for 0);
    ``fixed``: from ``low`` to ``high``; ``rate``: from 0 to the larger of ``high`` and twice
    the asked rate or today's average. ``step`` 0 lets the range pick a round step.
    """

    kind: Literal["scale", "fixed", "rate"]
    low: float
    high: float
    step: float = 0.0
    # ``scale`` only: the value the range is built around when the asked one is 0, and the
    # most the range may reach (0: no cap).
    base: float = 0.0
    ceiling: float = 0.0


@dataclass(frozen=True)
class Input:
    name: str
    label_key: str
    format: Format
    span: Span


@dataclass(frozen=True)
class Output:
    name: str
    label_key: str
    format: Format
    expression: str
    primary: bool = False
    # Shown when the value is not a number: a payment that never pays the card off.
    never_key: str | None = None


@dataclass(frozen=True)
class RateLookup:
    """How to look up today's average rate for a product on the web (``rates.py``).

    ``name`` says what the rate is, with ``{term}`` for the term bucket nearest the asked
    one ("30-year fixed mortgage"); ``terms`` are the buckets averages are published for,
    in the product's term unit (none: the rate has no term). A reading counts only when
    it lies within ``plausible`` (percent) and describes a day at most ``fresh_days`` ago.
    """

    name: str
    plausible: tuple[float, float]
    fresh_days: int
    terms: tuple[float, ...] = ()

    def term_bucket(self, asked: float | None) -> float | None:
        if not self.terms:
            return None
        if asked is None:
            return self.terms[-1]
        return min(self.terms, key=lambda bucket: (abs(bucket - asked), -bucket))

    def describe(self, bucket: float | None) -> str:
        return self.name.format(term=f"{bucket:g}" if bucket is not None else "")


@dataclass(frozen=True)
class Product:
    key: str
    family: Family
    title_key: str
    # Words that name the product in a request ("home loan", "car payment").
    words: tuple[str, ...]
    inputs: tuple[Input, ...]
    outputs: tuple[Output, ...]
    # Values a request may leave out, said as an assumption in the reply.
    defaults: dict[str, float] = field(default_factory=dict)
    lookup: RateLookup | None = None

    def input(self, name: str) -> Input | None:
        return next((item for item in self.inputs if item.name == name), None)


# --- Formulas -------------------------------------------------------------------------

_MONTHLY = "(rate/1200)"


def _payment(months: str) -> str:
    """The level monthly payment on ``amount`` over ``months``; at 0 % it is amount ÷ months."""
    r = _MONTHLY
    return f"(amount*{r}/(1 - (1 + {r})**(-({months}))) if rate > 0 else amount/({months}))"


def _loan_outputs(months: str) -> tuple[Output, ...]:
    payment = _payment(months)
    return (
        Output("payment", "money.monthly_payment", "money", payment, primary=True),
        Output("interest", "money.total_interest", "money", f"{payment}*({months}) - amount"),
        Output("total", "money.total_paid", "money", f"{payment}*({months})"),
    )


_CARD_R = "(apr/1200)"
# Months to clear ``balance`` paying ``payment`` a month. A payment at or below the first
# month's interest never clears it: 1/0 gives no number, and the card says "never".
_CARD_MONTHS = (
    f"((-log(1 - {_CARD_R}*balance/payment)/log(1 + {_CARD_R}) if apr > 0 else balance/payment)"
    f" if payment > balance*{_CARD_R} else 1/0)"
)
_GROWTH = f"(1 + {_MONTHLY})**(years*12)"
_SAVED = (
    f"(start*{_GROWTH} + (deposit*({_GROWTH} - 1)/{_MONTHLY} if rate > 0 else deposit*years*12))"
)

# --- Inputs ---------------------------------------------------------------------------

_AMOUNT = Input("amount", "money.amount", "money", Span("scale", 0.25, 2.5, base=100_000))
_RATE = Input("rate", "money.rate", "percent", Span("rate", 0.0, 15.0, step=0.05))
_APR = Input("apr", "money.apr", "percent", Span("rate", 0.0, 36.0, step=0.1))
_BALANCE = Input("balance", "money.balance", "money", Span("scale", 0.25, 3.0, base=5000))
_CARD_PAYMENT = Input(
    "payment", "money.monthly_payment", "money", Span("scale", 0.25, 5.0, base=100)
)
_START = Input(
    "start", "money.start", "money", Span("scale", 0.0, 3.0, base=10_000, ceiling=10_000_000)
)
_DEPOSIT = Input(
    "deposit", "money.deposit", "money", Span("scale", 0.0, 3.0, base=500, ceiling=1_000_000)
)


def _years(low: float, high: float) -> Input:
    return Input("years", "money.term_years", "years", Span("fixed", low, high, step=1))


def _months(low: float, high: float, step: float) -> Input:
    return Input("months", "money.term_months", "months", Span("fixed", low, high, step=step))


PRODUCTS: tuple[Product, ...] = (
    Product(
        key="mortgage",
        family="loan",
        title_key="money.title.mortgage",
        words=("mortgage", "home loan", "house loan", "housing loan", "house", "home", "condo"),
        inputs=(_AMOUNT, _RATE, _years(5, 40)),
        outputs=_loan_outputs("years*12"),
        defaults={"years": 30},
        lookup=RateLookup("{term}-year fixed mortgage rate", (1.0, 15.0), 21, (15, 30)),
    ),
    Product(
        key="car",
        family="loan",
        title_key="money.title.car",
        words=("car loan", "auto loan", "car payment", "vehicle loan", "truck loan", "car", "auto"),
        inputs=(_AMOUNT, _RATE, _months(12, 96, 6)),
        outputs=_loan_outputs("months"),
        defaults={"months": 60},
        lookup=RateLookup("{term}-month new car loan rate", (1.0, 25.0), 120, (36, 48, 60, 72)),
    ),
    Product(
        key="student",
        family="loan",
        title_key="money.title.student",
        words=("student loan", "student loans", "college loan", "school loan"),
        inputs=(_AMOUNT, _RATE, _years(1, 30)),
        outputs=_loan_outputs("years*12"),
        defaults={"years": 10},
        lookup=RateLookup("undergraduate federal student loan interest rate", (1.0, 15.0), 400),
    ),
    Product(
        key="personal",
        family="loan",
        title_key="money.title.personal",
        words=("personal loan", "personal loans"),
        inputs=(_AMOUNT, _RATE, _months(6, 84, 6)),
        outputs=_loan_outputs("months"),
        defaults={"months": 36},
        lookup=RateLookup("personal loan interest rate", (3.0, 40.0), 120),
    ),
    Product(
        key="loan",
        family="loan",
        title_key="money.title.loan",
        words=("loan", "borrow", "borrowing", "finance", "financing"),
        inputs=(_AMOUNT, _RATE, _years(1, 40)),
        outputs=_loan_outputs("years*12"),
        defaults={"years": 5},
    ),
    Product(
        key="card",
        family="card_payoff",
        title_key="money.title.card",
        words=("credit card", "credit cards", "card balance", "card debt", "visa", "mastercard"),
        inputs=(_BALANCE, _APR, _CARD_PAYMENT),
        outputs=(
            Output("months", "money.months_to_payoff", "months", _CARD_MONTHS, True, "money.never"),
            Output(
                "interest",
                "money.total_interest",
                "money",
                f"{_CARD_MONTHS}*payment - balance",
                never_key="money.never",
            ),
        ),
        lookup=RateLookup("credit card interest rate (APR)", (8.0, 40.0), 120),
    ),
    Product(
        key="savings",
        family="savings",
        title_key="money.title.savings",
        words=(
            "savings",
            "save",
            "saving",
            "invest",
            "investing",
            "investment",
            "deposit",
            "compound",
            "retirement",
        ),
        inputs=(_START, _DEPOSIT, _RATE, _years(1, 50)),
        outputs=(
            Output("balance", "money.final_balance", "money", _SAVED, primary=True),
            Output("deposited", "money.total_deposited", "money", "start + deposit*years*12"),
            Output(
                "interest", "money.interest_earned", "money", f"{_SAVED} - start - deposit*years*12"
            ),
        ),
        defaults={"start": 0, "deposit": 0, "years": 10},
        lookup=RateLookup("savings account interest rate (APY)", (0.01, 10.0), 60),
    ),
)


def product(key: str) -> Product:
    return next(item for item in PRODUCTS if item.key == key)
