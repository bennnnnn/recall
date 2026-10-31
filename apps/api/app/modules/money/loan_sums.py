"""Which sum in a loan request is the loan: the price less what is put down, or the one
said to be borrowed, or none.

Live (2026-10-31, an Ethiopian grade 12 book): "a house that costs Birr 250,000. He has
saved Birr 50,000 which he will use as a deposit, and will finance the rest of the cost
by taking out a loan" was worked as a loan of 250,000, the first sum, and the card's
payment was the price's. The loan is the price less the sum put down, said as a down
payment or a deposit ("which he will use as a deposit") or by borrowing "the rest" of
two sums. When two sums stand with one said to be a price and none said to be borrowed,
which one is the loan is not said, and none is read: the model asks or works it in words.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Sum:
    """One sum of money in a request, with what its neighbours say it is."""

    value: float
    monthly: bool
    down: bool
    start: bool
    # Said to be borrowed ("borrow 20k", "owe 250k", "a 200k loan").
    loan: bool = False
    # Said to be what the thing costs ("costs 250,000", "a 400k house").
    price: bool = False


@dataclass(frozen=True)
class LoanSums:
    amount: float | None
    # A price with money down; a new down payment is taken off this price (``follow_up``).
    price: float | None = None
    down: float | None = None


# "Finance the rest of the cost", "borrows the remainder", "the difference on a loan".
_REST = re.compile(
    r"\bthe\s(?:rest|remainder|difference|remaining\s(?:amount|cost|price|sum))\b", re.I
)
_BORROWED = re.compile(r"\b(?:borrow\w*|financ\w*|loans?|mortgage)\b", re.I)
_SENTENCES = re.compile(r"[^.;!?]+")


def rest_is_borrowed(text: str) -> bool:
    """One sentence borrows what is left of the price: "and borrows the rest"."""
    return any(
        _REST.search(sentence) and _BORROWED.search(sentence)
        for sentence in _SENTENCES.findall(text)
    )


def loan_sums(sums: list[Sum], share: float | None, rest: bool) -> LoanSums:
    """The loan, and its price and down payment when the request gives money down."""
    once = [item for item in sums if not item.monthly]
    named = [item for item in once if not item.down]
    # "Borrow 20k and pay the rest in cash" borrows the sum it names, not the rest.
    if rest and len(once) == 2 and len(named) == 2 and not any(item.loan for item in named):
        put, cost = sorted(item.value for item in named)
        return LoanSums(cost - put, cost, put) if put < cost else LoanSums(None)
    if len(named) > 1:
        borrowed = [item for item in named if item.loan]
        if len(borrowed) == 1 and len(named) == len(once):
            return LoanSums(borrowed[0].value)
        if any(item.price for item in named):
            return LoanSums(None)
    first = named[0].value if named else None
    down = _down(once, first, share)
    if first is None or first <= (down or 0.0):
        return LoanSums(None)
    if down is not None and 0 < down < first:
        return LoanSums(first - down, first, down)
    return LoanSums(first)


def _down(once: list[Sum], first: float | None, share: float | None) -> float | None:
    """The sum down: said ("3000 down"), else a share of the first sum ("20% down")."""
    said = next((item.value for item in once if item.down), None)
    if said is None and share is not None and first is not None:
        return first * share / 100
    return said
