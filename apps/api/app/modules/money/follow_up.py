"""A line that changes the chat's last money request: that request, changed, worked again.

"hmm what if i only do 3 years instead", right after a used-car loan of 11 000 over 60
months, is that loan over 36 months. The turn read only its own message, so no card was
built and the model did the arithmetic itself, off by dollars (live, 2026-10-25). The
follow-up chips under a money reply ask exactly this.

The server works a new term, a new rate or a new down payment only (``change_line``), read
by a positive grammar so a line about anything else is no follow-up. A down payment comes
off a price the user stated, never off a sum they called a loan or a balance ("a 20k car
loan", "I owe 15k"): the price a buying line gave ("buying a car" then "20k with 6
percent", live 2026-10-25: "Down payment 3k" is a loan of 17k) or one with money down ("a
400k house with 20% down"). A second one replaces the first. A line that says which a
guessed amount was ("no, 60k is the loan") puts the guess right (``correction``). The new
value must also lie on the slider the request's last card had (a mortgage runs 5 to 40
years: "2 years" is no new term). The request it changes is the last one in the user's
last few lines, with every line after it a change of it too. Every other change (a price,
a percent down, a card payment, a deposit, used or new) goes to the model, which answers
it as before: three reviews of wider readers each found new shapes they misread, and a
misread follow-up is a wrong number the reply calls the answer.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import replace

from app.modules.money.catalog import Product
from app.modules.money.change_line import read_change
from app.modules.money.correction import corrected, is_correction
from app.modules.money.fence import slider_range
from app.modules.money.purchase import purchase_request
from app.modules.money.read import MoneyRequest, named_product, read_money_request, term_in
from app.modules.money.solve import rate_name

# The user lines a follow-up may reach back over: the request and the changes after it.
_WINDOW = 3


def follow_up_request(text: str, earlier: Sequence[str | Sequence[str]]) -> MoneyRequest | None:
    """The chat's last money request with ``text``'s change made, or None.

    ``earlier`` is the user's lines before this one, oldest first, each as the parts its
    own turn read it in (a multi-part line's requests, ``turn_plan``; a plain line is one
    part). Each of the last ``_WINDOW`` is read as its turn read it: its first part that
    changes the request before it or is a new request, or none, which ends the money
    conversation. A review (2026-10-25) found the whole of "set a reminder for 9 tomorrow
    and what's the payment on a 20000 car loan at 6%" read as a loan of 9.
    """
    if read_change(text) is None and not is_correction(text):
        return None
    lines = [as_parts(line) for line in earlier]
    request: MoneyRequest | None = None
    for index in range(max(0, len(lines) - _WINDOW), len(lines)):
        before = lines[index - 1] if index else ()
        request = _line_request(request, lines[index], before)
    return _then(request, text) if request is not None else None


def as_parts(line: str | Sequence[str]) -> tuple[str, ...]:
    """An earlier line as the parts its turn read it in (a plain line is one part)."""
    return (line,) if isinstance(line, str) else tuple(line)


def _line_request(
    request: MoneyRequest | None, parts: tuple[str, ...], before: tuple[str, ...]
) -> MoneyRequest | None:
    """The money request an earlier line left, read part by part as its turn read it;
    ``before`` is the line before it, which may say what a bare amount and rate buy."""
    for part in parts:
        found = (_then(request, part) if request is not None else None) or _fresh(part, before)
        if found is not None:
            return found
    return None


def _then(request: MoneyRequest, line: str) -> MoneyRequest | None:
    """``request`` after ``line``: a guess put right, or a change made."""
    return corrected(request, line) or changed(request, line)


def changed(request: MoneyRequest, line: str) -> MoneyRequest | None:
    """``request`` with the new term, rate or down payment ``line`` states, or None when it
    states none that fits."""
    change = read_change(line)
    product = request.product
    if change is None or _switches_product(product, line):
        return None
    values = dict(request.values)
    names: list[str] = []
    price, down = request.price, request.down
    if change.down is not None:
        down, said_in = change.down
        if not product.goods or price is None or not 0 < down < price:
            return None
        if said_in and said_in != request.currency:
            return None
        values["amount"] = price - down
        names.append("amount")
    if change.rate is not None:
        values[rate_name(product)] = change.rate
        names.append(rate_name(product))
    if change.term is not None:
        term = term_in(product, *change.term)
        if not term or (change.saving_term and product.family != "savings"):
            return None
        values.update(term)
        names.extend(term)
    if not _in_range(request, values):
        return None
    return replace(request, values=values, changed=tuple(names), price=price, down=down, guessed="")


def _fresh(line: str, before: tuple[str, ...]) -> MoneyRequest | None:
    found = read_money_request(line) or purchase_request(line, before)
    return found if found is not None and not found.rates_only else None


def _switches_product(product: Product, text: str) -> bool:
    """The line names another product: "a 15 year mortgage" after a car loan.

    A plainer word for this one is no switch: "a 4 year loan" after a car loan (the
    generic loan's word "loan" is inside "car loan").
    """
    named = named_product(text)
    if named is None or named.key == product.key:
        return False
    return not any(
        re.search(rf"\b{re.escape(word)}\b", own) for word in named.words for own in product.words
    )


def _in_range(request: MoneyRequest, values: dict[str, float]) -> bool:
    """Each changed input lies within the slider its old value had on the last card."""
    product = request.product
    for item in product.inputs:
        if item.name not in values:
            continue
        old = request.values.get(item.name, product.defaults.get(item.name, 0.0))
        if values[item.name] == old:
            continue
        low, high, _ = slider_range(item.span, old, None)
        if not low <= values[item.name] <= high:
            return False
    return True
