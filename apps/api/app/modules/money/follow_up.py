"""A line that changes the chat's last money request: that request, changed, worked again.

"hmm what if i only do 3 years instead", right after a used-car loan of 11 000 over 60
months at 7.16 %, is that loan over 36 months. The turn read only its own message, so
no card was built and the model did the arithmetic itself: $340.58 a month and
$1,260.88 interest, where the loan costs $340.45 and $1,256.32 (live, 2026-10-25). The
follow-up chips under a money reply ask exactly this.

A change line asks for one ("what if", "how about", "instead") or is only the change
("36 months?", "and 5000 down?"). Every number in it must be a rate, a term or a sum
whose role its own words make certain (``follow_up_words``), or the line is no change:
"what if sales tax is 7%" is no new rate and "what if I pay 400 instead?" no $400 loan,
though a first version read both that way. The request it changes is the last one in
the user's last few lines, with every line after it a change of it too, so a what-if
after the chat moved on ("what if i only do 3 sets instead" after a workout) is not one.
A line the reader is unsure of goes to the model, which answers it as before.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from app.modules.money import follow_up_words as words
from app.modules.money.catalog import Product
from app.modules.money.kinds import named_plain_kind, named_variant
from app.modules.money.read import (
    Amount,
    MoneyRequest,
    named_product,
    rate_match,
    read_money_request,
    stated_amounts,
    stated_down_share,
    term_matches,
    term_value,
)
from app.modules.money.solve import rate_name

# The user lines a follow-up may reach back over: the request and the changes after it.
_WINDOW = 3
_MAX_CHARS = 300
# "100%" after a reply agrees with it: no loan, card or savings rate is that high.
_RATE_CEILING = 100.0
# The input a card's or a savings plan's monthly sum fills; a loan takes none.
_EACH_MONTH = {"card_payoff": "payment", "savings": "deposit"}


def follow_up_request(text: str, earlier: Sequence[str]) -> MoneyRequest | None:
    """The chat's last money request with ``text``'s change made, or None.

    ``earlier`` is the user's lines before this one, oldest first. Each of the last
    ``_WINDOW`` is read as its turn read it: a change of the request before it, a new
    request, or neither, which ends the money conversation.
    """
    if not _asks_a_change(text):
        return None
    request: MoneyRequest | None = None
    for line in list(earlier)[-_WINDOW:]:
        request = (changed(request, line) if request is not None else None) or _fresh(line)
    return changed(request, text) if request is not None else None


def changed(request: MoneyRequest, line: str) -> MoneyRequest | None:
    """``request`` with the change ``line`` asks for, or None when it asks none."""
    if not _asks_a_change(line):
        return None
    text = words.OLD_VALUE.sub(" ", line)
    product = request.product
    if (
        words.RELATIVE.search(text)
        or words.OTHER_THING.search(text)
        or _switches_product(product, text)
    ):
        return None
    values = dict(request.values)
    names: list[str] = []
    rate = _rate(text)
    if rate is not None:
        values[rate_name(product)] = rate
        names.append(rate_name(product))
    terms = [found for found in term_matches(text) if _is_loan_term(text, found.start())]
    term = term_value(product, terms[0]) if len(terms) == 1 else {}
    values.update(term)
    names.extend(term)
    amounts = stated_amounts(text)
    share = stated_down_share(text)
    down = _place_sums(request, text, (amounts, share), values, names)
    placed = (rate is not None) + bool(term) + len(amounts) + (share is not None)
    variant = _kind(request, text)
    if down is None or variant is None or placed != len(words.NUMBER.findall(text)):
        return None
    if variant != request.variant:
        names.append("variant")
    if not names:
        return None
    # While the rate is today's average, a new term keeps the one the last reply used.
    assumed_rate = rate_name(product) not in values
    return replace(
        request,
        values=values,
        variant=variant,
        down=down,
        rate_term=_rate_term(request) if assumed_rate else None,
        changed=tuple(dict.fromkeys(names)),
    )


def _fresh(line: str) -> MoneyRequest | None:
    found = read_money_request(line)
    return found if found is not None and not found.rates_only else None


def _asks_a_change(line: str) -> bool:
    if not line or len(line) > _MAX_CHARS:
        return False
    return words.CUE.search(line) is not None or words.ONLY_THE_CHANGE.match(line) is not None


def _rate(text: str) -> float | None:
    """The new rate, when the words beside the percent say it is the rate; else none.

    A percent that is no rate stays unplaced, so the line is no follow-up.
    """
    match = rate_match(text)
    if match is None or float(match.group(1)) >= _RATE_CEILING:
        return None
    before = text[max(0, match.start() - 32) : match.start()]
    if (
        words.RATE_BEFORE.search(before)
        or words.RATE_AFTER.match(text, match.end())
        or words.ONLY_THE_CHANGE.match(text)
    ):
        return float(match.group(1))
    return None


def _is_loan_term(text: str, at: int) -> bool:
    return words.TERM_BEFORE.search(text[max(0, at - 32) : at]) is not None


def _kind(request: MoneyRequest, text: str) -> str | None:
    """The kind after the change: a variant named, the plain kind, or the request's own.

    None when the line names both ("a new car, not a used one").
    """
    variant = named_variant(request.product, text)
    plain = named_plain_kind(request.product, text)
    if variant and plain:
        return None
    return variant or ("" if plain else request.variant)


def _switches_product(product: Product, text: str) -> bool:
    """The line names another product: "a car loan instead" after a mortgage.

    A plainer word for this one is no switch: "the loan" after a car loan (the generic
    loan's word "loan" is inside "car loan").
    """
    named = named_product(text)
    if named is None or named.key == product.key:
        return False
    return not any(words.whole_word(word, own) for word in named.words for own in product.words)


def _place_sums(
    request: MoneyRequest,
    text: str,
    sums: tuple[list[Amount], float | None],
    values: dict[str, float],
    names: list[str],
) -> float | None:
    """Put each sum, and a share put down, into the input its words name.

    Returns the loan's down payment after the change; None when a sum's role is not
    certain, or two sums name the same input.
    """
    amounts, share = sums
    loan = request.product.family == "loan"
    price = values.get("amount", 0.0) + request.down if loan else 0.0
    down = request.down
    seen: set[str] = set()
    if share is not None:
        if not loan:
            return None
        seen.add("down")
    for amount in amounts:
        role = _role(request, text, amount)
        if role is None or role in seen:
            return None
        seen.add(role)
        if role == "down":
            down = amount.value
        elif role == "price":
            price = amount.value
        elif role == "borrowed":
            price, down = amount.value, 0.0
        else:
            values[role] = amount.value
        # The price and the sum borrowed both change the loan's amount.
        names.append("amount" if role in ("price", "borrowed") else role)
    if share is not None:
        down = price * share / 100
        names.append("down")
    if loan and seen:
        if price <= down:
            return None
        values["amount"] = price - down
    return down


def _role(request: MoneyRequest, text: str, amount: Amount) -> str | None:
    """What one sum of a change line is, when its words make that certain; else None."""
    family = request.product.family
    at, end = amount.span
    before = text[max(0, at - 32) : at]
    if amount.down:
        return "down" if family == "loan" else None
    if amount.monthly:
        return _EACH_MONTH.get(family)
    if words.PER_PERIOD.match(text, end):
        return None
    if family == "card_payoff":
        if words.PAYING.search(before):
            return "payment"
        return "balance" if words.BALANCE_BEFORE.search(before) else None
    if family == "savings":
        return "start" if amount.start else None
    if words.BORROWED.search(before) or words.LOAN_AFTER.match(text, end):
        return "borrowed"
    if words.NOT_THE_PRICE.search(before):
        return None
    # A loan has one sum of its own, its price: a line that is only the sum changes it.
    if (
        words.PRICE_BEFORE.search(before)
        or words.THING_AFTER.match(text, end)
        or words.ONLY_THE_CHANGE.match(text)
    ):
        return "price"
    return None


def _rate_term(request: MoneyRequest) -> float | None:
    """The term the request's average was looked up for: its first ask's own."""
    if request.rate_term is not None:
        return request.rate_term
    product = request.product
    for name in ("years", "months"):
        if product.input(name) is not None:
            return request.values.get(name, product.defaults.get(name))
    return None
