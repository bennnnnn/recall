"""A line that changes the chat's last money request: that request, changed, worked again.

"hmm what if i only do 3 years instead", right after a used-car loan of 11 000 over 60
months, is that loan over 36 months. The turn read only its own message, so no card was
built and the model did the arithmetic itself, off by dollars (live, 2026-10-25). The
follow-up chips under a money reply ask exactly this.

The line is read by ``change_line``'s positive grammar: every word of it must be a change
phrase or filler, so a line about anything else is no follow-up. The change must then
fit the request: a role its product has (a card has no down payment), a currency the
request is in, and a value the request's own card slider reaches (a mortgage runs 5 to 40
years, so "5% for 2 years" is no new term). The request it changes is the last one in
the user's last few lines, with every line after it a change of it too. A line this
declines goes to the model, which answers it as before: a declined follow-up costs a
little arithmetic, a misread one a wrong number the reply calls the answer.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import replace

from app.modules.money.catalog import Product
from app.modules.money.change_line import Change, read_change
from app.modules.money.currencies import currency_for
from app.modules.money.fence import slider_range
from app.modules.money.kinds import kind_of
from app.modules.money.read import MoneyRequest, named_product, read_money_request, term_in
from app.modules.money.solve import rate_name

# The user lines a follow-up may reach back over: the request and the changes after it.
_WINDOW = 3
# The sums each family takes; a sum of any other role makes the line no change of it.
_ROLES = {
    "loan": frozenset({"price", "borrowed", "down", "bare"}),
    "card_payoff": frozenset({"monthly", "pay", "balance"}),
    "savings": frozenset({"monthly", "start"}),
}
# A card's monthly sum is its payment, a savings plan's its deposit; each said its own way.
_EACH_MONTH = {"card_payoff": ("payment", "pay"), "savings": ("deposit", "save")}


def follow_up_request(
    text: str, earlier: Sequence[str], location: str | None = None
) -> MoneyRequest | None:
    """The chat's last money request with ``text``'s change made, or None.

    ``earlier`` is the user's lines before this one, oldest first. Each of the last
    ``_WINDOW`` is read as its turn read it: a change of the request before it, a new
    request, or neither, which ends the money conversation. ``location`` is the user's
    place, which gives the request its currency when it named none.
    """
    if read_change(text) is None:
        return None
    request: MoneyRequest | None = None
    for line in list(earlier)[-_WINDOW:]:
        if request is not None:
            request = changed(request, line, location)
        request = request or _fresh(line)
    return changed(request, text, location) if request is not None else None


def changed(request: MoneyRequest, line: str, location: str | None) -> MoneyRequest | None:
    """``request`` with the change ``line`` states, or None when it states none that fits."""
    change = read_change(line)
    product = request.product
    if change is None or _switches_product(product, line):
        return None
    currency = currency_for(request.currency, location)
    if any(named != currency for named in change.currencies):
        return None
    values = dict(request.values)
    names: list[str] = []
    if change.rate is not None:
        values[rate_name(product)] = change.rate
        names.append(rate_name(product))
    if change.term is not None:
        term = term_in(product, *change.term)
        if not term or (change.saving_term and product.family != "savings"):
            return None
        values.update(term)
        names.extend(term)
    down = _place_sums(request, change, values, names)
    variant = _kind(request, change)
    if down is None or variant is None or not _in_range(request, values):
        return None
    if variant != request.variant:
        names.append("variant")
    if not names:
        return None
    return replace(
        request,
        values=values,
        variant=variant,
        down=down[0],
        down_share=down[1],
        changed=tuple(dict.fromkeys(names)),
    )


def _fresh(line: str) -> MoneyRequest | None:
    found = read_money_request(line)
    return found if found is not None and not found.rates_only else None


def _switches_product(product: Product, text: str) -> bool:
    """The line names another product: "a car loan instead" after a mortgage.

    A plainer word for this one is no switch: "the loan" after a car loan (the generic
    loan's word "loan" is inside "car loan").
    """
    named = named_product(text)
    if named is None or named.key == product.key:
        return False
    return not any(
        re.search(rf"\b{re.escape(word)}\b", own) for word in named.words for own in product.words
    )


def _place_sums(
    request: MoneyRequest, change: Change, values: dict[str, float], names: list[str]
) -> tuple[float, float | None] | None:
    """Fill the inputs the sums name. Returns the loan's down payment and its share of the
    price after the change, or None when a sum names nothing this request has."""
    family = request.product.family
    if not set(change.sums) <= _ROLES[family]:
        return None
    if family == "loan":
        return _loan_sums(request, change, values, names)
    if change.down_share is not None:
        return None
    each_month, verb = _EACH_MONTH[family]
    filled: set[str] = set()
    for role, value in change.sums.items():
        if role == "monthly" and change.monthly_verb not in ("", verb):
            return None
        name = each_month if role in ("monthly", "pay") else role
        if name in filled:
            return None
        filled.add(name)
        values[name] = value
        names.append(name)
    return request.down, request.down_share


def _loan_sums(
    request: MoneyRequest, change: Change, values: dict[str, float], names: list[str]
) -> tuple[float, float | None] | None:
    """A loan's price, sum borrowed and down payment. A share put down ("20% down") stays a
    share, so a new price ("what about a 600k house?") takes it again."""
    sums = change.sums
    price = values["amount"] + request.down
    down, share = request.down, request.down_share
    new_price = sums.get("price", sums.get("bare"))
    if "borrowed" in sums:
        if new_price is not None or "down" in sums or change.down_share is not None:
            return None
        price, down, share = sums["borrowed"], 0.0, None
    if "price" in sums and "bare" in sums:
        return None
    if new_price is not None:
        price = new_price
        if share is not None:
            down = price * share / 100
            names.append("down")
    if "down" in sums:
        down, share = sums["down"], None
        names.append("down")
    if change.down_share is not None:
        share = change.down_share
        down = price * share / 100
        names.append("down")
    if "borrowed" in sums or new_price is not None:
        names.append("amount")
    if price <= down:
        return None
    values["amount"] = price - down
    return down, share


def _kind(request: MoneyRequest, change: Change) -> str | None:
    """The kind after the change: the one the line names, else the request's own."""
    if change.kind is None:
        return request.variant
    kind = kind_of(request.product, change.kind)
    return request.variant if kind is None else kind


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
