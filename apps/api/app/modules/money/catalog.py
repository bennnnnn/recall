"""Every money product as data: its inputs, its formulas, its words and its rate lookup.

A product is one row. Its outputs are expressions over its input names, in the closed
language of ``services/law_binding/expression.py``: the server works the asked numbers
with them and the phone redraws the card from the same trees (docs/money.md). Nothing
else branches on a product's name, so a new product is a new row, and a kind of one
priced apart (a used car) is a ``Variant`` on its row.

Rates are yearly percentages (``rate`` 6.5 is 6.5 %; "2% a month" is read as 24, ``periods``)
and deposits and card payments are monthly. A loan is paid and compounds as often as the
request says (``payments``, a setting: no slider moves it), monthly when it says nothing; a
card compounds monthly; savings compound as often as the request says (``per_year``),
monthly when it says nothing.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Literal

from app.modules.money.periods import FREQUENCIES

Format = Literal["money", "percent", "years", "months", "number"]
Family = Literal["loan", "card_payoff", "savings", "afford"]


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
    # Its label when the request said the rate by a shorter period ("2% a month"): the
    # slider holds the yearly rate it comes to, so it says so. "" keeps ``label_key``.
    yearly_key: str = ""


@dataclass(frozen=True)
class Output:
    name: str
    label_key: str
    format: Format
    expression: str
    primary: bool = False
    # Shown when the value is not a number: a payment that never pays the card off.
    never_key: str | None = None
    # Its label at each value of the setting ``labelled_by`` names: a loan's payment made
    # four times a year is "Quarterly payment" (``Product.outputs_at``).
    labelled_by: str = ""
    labels: Mapping[float, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RateLookup:
    """How to look up today's average rate for a product on the web (``rates.py``).

    ``name`` says what the rate is, with ``{term}`` for the term bucket nearest the asked
    one ("30-year fixed mortgage"); ``terms`` are the buckets averages are published for,
    in the product's term unit (none: the rate has no term). A reading counts only when
    it lies within ``plausible`` (percent) and describes a day at most ``fresh_days`` ago.

    ``spread`` is said beside an average that mixes kinds of the product priced far apart
    (every savings account: big banks paying almost nothing beside high-yield accounts
    near 4%). Such an average is not the bar for any one account, so it judges no rate
    unrealistic (``note.market_note``): only an average of the same kind may.
    """

    name: str
    plausible: tuple[float, float]
    fresh_days: int
    terms: tuple[float, ...] = ()
    spread: str = ""

    def term_bucket(self, asked: float | None) -> float | None:
        if not self.terms:
            return None
        if asked is None:
            return self.terms[-1]
        return min(self.terms, key=lambda bucket: (abs(bucket - asked), -bucket))

    def describe(self, bucket: float | None) -> str:
        return self.name.format(term=f"{bucket:g}" if bucket is not None else "")


@dataclass(frozen=True)
class Variant:
    """A kind of the product a request may name, with its own average rate: a used car.

    "a used car for 14000" is a car loan, but its average is the used-car one, a few points
    above the new-car rate it was quoted (live, 2026-10-25). ``words`` name the kind as a
    describing word (``kinds.py``); ``lookup`` takes the place of the product's. When it
    finds nothing the product's own average stands in, with ``stand_in`` said beside it.
    """

    key: str
    words: tuple[str, ...]
    lookup: RateLookup
    stand_in: str


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
    # Kinds of the product priced apart; none named is the product's own ``lookup``.
    variants: tuple[Variant, ...] = ()
    goods: tuple[str, ...] = ()  # What the loan buys: "planning to buy a car" (``purchase``).
    # The product this one works as, judged by another average: a follow-up moving from one
    # to the other ("what if I invest for 20 years" after saving) is no switch.
    twin: str = ""
    # Terms a request fixes that no slider moves, with their usual values: how many times a
    # year savings compound. The outputs name them; ``outputs_at`` writes them in as numbers,
    # so a card's trees name only its sliders.
    settings: dict[str, float] = field(default_factory=dict)
    # Words that name the product only beside its payments and no other product's word:
    # "Ato Kebede borrowed Birr 10,000 … repays it in 18 equal monthly payments" is a loan,
    # but "Tom borrowed $2,000 at 8%. How much interest after 3 years?" is growth, and "I
    # borrowed $15,000 for a car" a car loan (``read.named_product``).
    asked_words: tuple[str, ...] = ()
    # Quoted by the year only: a rate said by a shorter period ("1.9% a month") is no rate
    # the reader can trust for it (``fits.said_by_period``).
    yearly_only: bool = False
    # The rule the outputs follow, said in the block so the reply names it (a lender's
    # guideline, not a law): "the common 28/36 rule".
    basis: str = ""

    def input(self, name: str) -> Input | None:
        return next((item for item in self.inputs if item.name == name), None)

    def outputs_at(self, settings: Mapping[str, float] | None = None) -> tuple[Output, ...]:
        """The outputs with every setting written in: the request's, else the usual one."""
        fixed = {**self.settings, **(settings or {})}
        if not fixed:
            return self.outputs
        named = re.compile(r"\b(" + "|".join(map(re.escape, fixed)) + r")\b")
        return tuple(
            replace(
                item,
                expression=named.sub(lambda m: f"{fixed[m[1]]:g}", item.expression),
                label_key=item.labels.get(fixed.get(item.labelled_by, 0.0), item.label_key),
            )
            for item in self.outputs
        )

    def variant(self, key: str) -> Variant | None:
        return next((item for item in self.variants if item.key == key), None)

    def rate_lookup(self, variant: str = "") -> RateLookup | None:
        """How to look up today's average for the product, or for the kind of it asked."""
        kind = self.variant(variant)
        return kind.lookup if kind is not None else self.lookup


# --- Formulas -------------------------------------------------------------------------

# A loan's rate for one of its ``payments`` a year: 12 a year is a month's (rate/1200).
_PERIOD_RATE = "(rate/(100*payments))"
# The card's label for a loan's payment, by how many are made a year.
_PAYMENT_LABELS: dict[float, str] = {
    count: item.payment_key for count, item in FREQUENCIES.items() if item.payment_key
}


def _payment(count: str) -> str:
    """The level payment on ``amount`` over ``count`` payments; at 0 % it is amount ÷ count."""
    r = _PERIOD_RATE
    return f"(amount*{r}/(1 - (1 + {r})**(-({count}))) if rate > 0 else amount/({count}))"


def _loan_outputs(count: str) -> tuple[Output, ...]:
    """A loan's results; ``count`` is its number of payments over its term."""
    payment = _payment(count)
    return (
        Output(
            "payment",
            "money.monthly_payment",
            "money",
            payment,
            primary=True,
            labelled_by="payments",
            labels=_PAYMENT_LABELS,
        ),
        Output("interest", "money.total_interest", "money", f"{payment}*({count}) - amount"),
        Output("total", "money.total_paid", "money", f"{payment}*({count})"),
    )


# Payments over a term counted in years, or in months.
_BY_YEARS = "years*payments"
_BY_MONTHS = "months*payments/12"


_CARD_R = "(apr/1200)"
# Months to clear ``balance`` paying ``payment`` a month. A payment at or below the first
# month's interest never clears it: 1/0 gives no number, and the card says "never".
_CARD_MONTHS = (
    f"((-log(1 - {_CARD_R}*balance/payment)/log(1 + {_CARD_R}) if apr > 0 else balance/payment)"
    f" if payment > balance*{_CARD_R} else 1/0)"
)
# Savings grow by one month's share of ``per_year`` compoundings a month: 4 a year is
# (1 + rate/400) a quarter, so a start grows (1 + rate/400)**(4*years), and a deposit
# made each month earns the same growth for the months it is in.
_STEP = "(1 + rate/(100*per_year))**(per_year/12)"
_GROWTH = f"({_STEP})**(years*12)"
_SAVED = (
    f"(start*{_GROWTH} + (deposit*({_GROWTH} - 1)/({_STEP} - 1) if rate > 0 else deposit*years*12))"
)

# --- Inputs ---------------------------------------------------------------------------

_AMOUNT = Input("amount", "money.amount", "money", Span("scale", 0.25, 2.5, base=100_000))
_RATE = Input(
    "rate", "money.rate", "percent", Span("rate", 0.0, 15.0, step=0.05), "money.yearly_rate"
)
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


# Savings and investing grow money the same way; only the rate they are judged by differs.
_SAVINGS_OUTPUTS = (
    Output("balance", "money.final_balance", "money", _SAVED, primary=True),
    Output("deposited", "money.total_deposited", "money", "start + deposit*years*12"),
    Output("interest", "money.interest_earned", "money", f"{_SAVED} - start - deposit*years*12"),
)

# What an income may borrow by the common 28/36 rule: the home's payment at most 28% of the
# gross monthly income, and every debt's payments with it at most 36%. The most it may pay
# is the smaller room, never below 0; the most it may borrow is that payment's loan.
_HOUSING = "(income*0.28/12)"
_ALL_DEBTS = "(income*0.36/12 - debts)"
_ROOM = f"({_HOUSING} if {_HOUSING} < {_ALL_DEBTS} else {_ALL_DEBTS})"
_MOST_PAYMENT = f"({_ROOM} if {_ROOM} > 0 else 0)"
_MONTH_RATE = "(rate/1200)"
_MOST_LOAN = (
    f"({_MOST_PAYMENT}*(1 - (1 + {_MONTH_RATE})**(-(years*12)))/{_MONTH_RATE}"
    f" if rate > 0 else {_MOST_PAYMENT}*years*12)"
)
_INCOME = Input("income", "money.income", "money", Span("scale", 0.25, 3.0, base=100_000))
_DEBTS = Input("debts", "money.debts", "money", Span("scale", 0.0, 3.0, base=500, ceiling=100_000))
_MORTGAGE_LOOKUP = RateLookup("{term}-year fixed mortgage rate", (1.0, 15.0), 21, (15, 30))

_USED_WORDS = (  # "certified pre-owned" is read by "pre-owned"
    "used", "pre-owned", "preowned", "pre owned", "second-hand", "secondhand", "second hand",
)  # fmt: skip

PRODUCTS: tuple[Product, ...] = (
    Product(
        key="mortgage",
        family="loan",
        title_key="money.title.mortgage",
        words=("mortgage", "home loan", "house loan", "housing loan", "house", "home", "condo"),
        inputs=(_AMOUNT, _RATE, _years(5, 40)),
        outputs=_loan_outputs(_BY_YEARS),
        settings={"payments": 12},
        yearly_only=True,
        defaults={"years": 30},
        lookup=_MORTGAGE_LOOKUP,
        goods=("house", "home", "condo"),
    ),
    Product(
        key="car",
        family="loan",
        title_key="money.title.car",
        words=("car loan", "auto loan", "car payment", "vehicle loan", "truck loan", "car", "auto"),
        inputs=(_AMOUNT, _RATE, _months(12, 96, 6)),
        outputs=_loan_outputs(_BY_MONTHS),
        settings={"payments": 12},
        yearly_only=True,
        defaults={"months": 60},
        lookup=RateLookup("{term}-month new car loan rate", (1.0, 25.0), 120, (36, 48, 60, 72)),
        goods=("car", "truck", "suv", "vehicle"),
        variants=(
            # Published for every term at once, often quarterly: no term, an older figure.
            Variant(
                "used",
                _USED_WORDS,
                RateLookup("used car loan rate", (2.0, 30.0), 180),
                "No used-car average was found; used-car loans usually cost more.",
            ),
        ),
    ),
    Product(
        key="student",
        family="loan",
        title_key="money.title.student",
        words=("student loan", "student loans", "college loan", "school loan"),
        inputs=(_AMOUNT, _RATE, _years(1, 30)),
        outputs=_loan_outputs(_BY_YEARS),
        settings={"payments": 12},
        yearly_only=True,
        defaults={"years": 10},
        lookup=RateLookup("undergraduate federal student loan interest rate", (1.0, 15.0), 400),
    ),
    Product(
        key="personal",
        family="loan",
        title_key="money.title.personal",
        words=("personal loan", "personal loans"),
        inputs=(_AMOUNT, _RATE, _months(6, 84, 6)),
        outputs=_loan_outputs(_BY_MONTHS),
        settings={"payments": 12},
        defaults={"months": 36},
        lookup=RateLookup("personal loan interest rate", (3.0, 40.0), 120),
    ),
    Product(
        key="loan",
        family="loan",
        title_key="money.title.loan",
        words=("loan", "borrow", "borrowing", "finance", "financing"),
        asked_words=("borrows", "borrowed"),
        inputs=(_AMOUNT, _RATE, _years(1, 40)),
        outputs=_loan_outputs(_BY_YEARS),
        settings={"payments": 12},
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
        # "a savings account for my retirement" is a savings account: the longer name wins.
        # "compound" alone is a chemistry noun: "A compound is composed of 53.33% carbon"
        # got a savings calculator (2026-10-30, a Grade 8 chemistry book). "Compounded" names
        # no product: a car loan compounded monthly is a loan.
        words=("savings account", "savings", "save", "saving", "deposit", "compound interest"),
        inputs=(_START, _DEPOSIT, _RATE, _years(1, 50)),
        outputs=_SAVINGS_OUTPUTS,
        defaults={"start": 0, "deposit": 0, "years": 10},
        # The national average (0.37%, 2026-09) is pulled down by big banks paying 0.01%;
        # "4% is not a realistic savings rate" beside it was wrong for a high-yield account
        # (2026-11-02). It is said for reference, with what it averages.
        lookup=RateLookup(
            "savings account interest rate (APY)",
            (0.01, 10.0),
            60,
            spread=(
                "That average includes accounts that pay almost nothing; high-yield "
                "savings accounts pay much more."
            ),
        ),
        settings={"per_year": 12},
    ),
    # How big a mortgage an income allows ("what mortgage can I afford", "can I afford a $1
    # million home?"). Read only by the model's reading of the chat (``model_read``): no
    # word names it, so no word rule reads it.
    Product(
        key="afford",
        family="afford",
        title_key="money.title.afford",
        words=(),
        inputs=(_INCOME, _DEBTS, _RATE, _years(1, 40)),
        outputs=(
            Output("most_loan", "money.most_loan", "money", _MOST_LOAN, primary=True),
            Output("most_payment", "money.most_payment", "money", _MOST_PAYMENT),
        ),
        defaults={"debts": 0, "years": 30},
        lookup=_MORTGAGE_LOOKUP,
        yearly_only=True,
        basis=(
            "These follow the common 28/36 rule lenders use as a guide: the home's monthly "
            "payment at most 28% of the gross monthly income, and all debt payments with it "
            "at most 36%. They leave out property tax, insurance and the down payment; say "
            "so in a few words."
        ),
    ),
    # Money put into a market, not a bank. "If I invest $200 a month at 7%" was a savings
    # account, and its note said "7% is not a realistic savings account interest rate
    # (APY)" beside the 0.37% average (2026-10-29); 7% is a usual long-run market
    # assumption. No average compares to a market's return, so none is looked up.
    Product(
        key="investing",
        family="savings",
        title_key="money.title.investing",
        words=("invest", "investing", "investment", "retirement"),
        inputs=(_START, _DEPOSIT, _RATE, _years(1, 50)),
        outputs=_SAVINGS_OUTPUTS,
        defaults={"start": 0, "deposit": 0, "years": 10},
        twin="savings",
        settings={"per_year": 12},
    ),
)


def product(key: str) -> Product:
    return next(item for item in PRODUCTS if item.key == key)


def plausible_rates(item: Product) -> tuple[float, float]:
    """The yearly rates ``item`` is plausibly charged: its average's plausible range, else the
    widest of its family's ("a loan" may be any loan). A rate said by a shorter period that
    comes to more or less was said casually: "a $300k mortgage at 6% per month" is no 72%
    loan (2026-11-14 review), so it is not worked."""
    if item.lookup is not None:
        return item.lookup.plausible
    ranges = [
        other.lookup.plausible
        for other in PRODUCTS
        if other.family == item.family and other.lookup is not None
    ]
    return min(low for low, _ in ranges), max(high for _, high in ranges)
