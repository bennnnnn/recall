"""A line that changes the chat's last money request: that request, changed, worked again.

"hmm what if i only do 3 years instead", right after a used-car loan of 11 000 over 60
months at 7.16 %, is that loan over 36 months. The turn read only its own message, so
no card was built and the model did the arithmetic itself: $340.58 a month and
$1,260.88 interest, where the loan costs $340.45 and $1,256.32 (live, 2026-10-25). The
follow-up chips under a money reply ask exactly this.

A change line asks for one ("what if", "how about", "instead") or is only the change
("36 months?", "and 5000 down?"), and is read with the request reader's own rules;
every number in it must be a rate, a term or a sum whose role its words give, or it is
no change. The request it changes is the last one in the user's last few lines, with
every line after it a change of it too, so a what-if after the chat moved on ("what if
i only do 3 sets instead" after a workout, "what if the perimeter was 48?") is not one.
A change by an amount ("1% lower", "2000 more down") is not read: the model answers it
as before.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import replace

from app.modules.money.catalog import Product
from app.modules.money.read import (
    Amount,
    MoneyRequest,
    named_product,
    named_variant,
    read_money_request,
    stated_amounts,
    stated_down_share,
    stated_rate,
    term_matches,
    term_value,
)
from app.modules.money.solve import rate_name

# The user lines a follow-up may reach back over: the request and the changes after it.
_WINDOW = 3
_MAX_CHARS = 300
# "100%" after a reply agrees with it: no loan, card or savings rate is that high.
_RATE_CEILING = 100.0
_CUE = re.compile(
    r"\b(?:what\s+(?:if|about|would)|how\s+about|instead|rather|suppose|supposing|"
    r"let'?s\s+(?:say|try|do)|make\s+it|change\s+it|switch\s+to|try|"
    r"and\s+(?:if|with|at|over|for|in))\b"
    r"|^\W*(?:(?:hmm+|ok(?:ay)?|so|and|but|oh|well|then|now)\W+)*(?:if|with|at|over|for|say)\b",
    re.I,
)
# A line of nothing but numbers, units and joining words: "36 months?", "and 5000 down?".
_ONLY_THE_CHANGE = re.compile(
    r"^(?:[\W\d]|\b(?:and|or|so|ok(?:ay)?|then|hmm+|at|over|for|with|a|an|the|down|in|"
    r"years?|yrs?|months?|mos?|percent|k|instead|please|maybe|now|apr|rate|term|dollars?)\b)*$",
    re.I,
)
# "3 years instead of 5", "7% not 7.16%": the old value is no change.
_OLD_VALUE = re.compile(
    r"\b(?:instead\s+of|rather\s+than|in\s+place\s+of|not|from)\s+(?:the\s+)?"
    r"(?:[$€£¥₹₦]\s?)?\d[\d,.]*\s?(?:%|percent|k\b|grand|years?|yrs?|months?|mos?)?",
    re.I,
)
_RELATIVE = re.compile(
    r"\b(?:by|extra|another|additional|drops?|dropped|falls?|fell|rises?|rose|"
    r"increase[sd]?|decrease[sd]?|(?:go(?:es)?|went)\s+(?:up|down)|cut|raise[sd]?)"
    r"\s+(?:an?\s+)?(?:[$€£¥₹₦]\s?)?\d"
    r"|\d[\d,.]*\s?(?:%|percent|k\b|grand|dollars?|years?|months?)?\s+"
    r"(?:more|less|lower|higher|extra|cheaper|longer|shorter|fewer|off)\b",
    re.I,
)
_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
# A sum with no "down" or "a month" says what it is by the words before it ("what if the
# car was 18k", "for a $350k house", "I pay 300") or the thing after it ("a 20k car").
# "What if I made 50k a year" and "my salary is 50k" name nothing the request has.
_FILLER = r"\s(?:(?:a|an|only|just|about|around|like)\s)*$"
_ROLE_BEFORE = re.compile(
    r"\b(?:for|of|costs?|costing|priced?|worth|pay(?:s|ing)?|paid|put(?:ting)?|with|"
    r"sav(?:e|ed|ing)|deposit(?:ed|ing)?|invest(?:ed|ing)?|"
    r"(?:car|house|home|condo|price|loan|balance|it|that|one|amount)"
    rf"(?:\s(?:was|is|were|became)|'s)){_FILLER}",
    re.I,
)
_THING_AFTER = re.compile(
    r"\s?(?:[a-z-]+\s)?(?:car|house|home|condo|truck|suv|vehicle|one|loan|mortgage|balance)\b",
    re.I,
)
_PER_PERIOD = re.compile(
    r"\s?(?:(?:a|an|per|each|every|/)\s?(?:year|yr|week|wk|day|hour|hr)\b"
    r"|annually|yearly|weekly|daily|hourly)",
    re.I,
)
# "What if I only borrow 8000", "a 25000 car loan": the sum borrowed, with nothing put down.
_BORROWED = re.compile(
    rf"\b(?:borrow(?:ed|ing)?|financ(?:e|ed|ing)|(?:loan|mortgage)\sof){_FILLER}", re.I
)
_LOAN_AFTER = re.compile(r"\s?(?:[a-z-]+\s)?(?:loan|mortgage)\b", re.I)
_PAYING = re.compile(rf"\b(?:pay(?:s|ing)?|paid){_FILLER}", re.I)
# A length of time is the loan's term by the words before it: "do 3 years", "over 48
# months", "make it 4 years", "pay it off in 2 years", "a 15 year mortgage", "36 months?".
# "Wait 2 years", "keep it for 10 years" or "I'm 3 years into the loan" says no term.
_TERM_ROLE_BEFORE = re.compile(
    r"(?:^|[,;:?!.(]|\d\s?(?:%|k\b)?|\b(?:what\s+if|what\s+about|how\s+about|and|or|so|"
    r"ok(?:ay)?|hmm+|then|instead|do|did|doing|make|made|go|went|try|say|take|took|get|got|"
    r"pick|picked|choose|chose|change|switch|finance[sd]?|financing|borrow(?:ed)?|spread|"
    r"pay|paid|off|sav(?:e|ing)|invest(?:ing)?|leave|with|at|to|on|over|a|an|down|"
    r"(?:loan|mortgage|term|it|that)\s+(?:was|is|were|be)))"
    r"\s*(?:(?:i|we|it|only|just|the|maybe|like|for|over|in|out|about|around)\s+)*$",
    re.I,
)
# The input a family's one-off sum and its monthly sum fill.
_ONCE = {"loan": "amount", "card_payoff": "balance", "savings": "start"}
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
    text = _OLD_VALUE.sub(" ", line)
    product = request.product
    if _RELATIVE.search(text) or _switches_product(product, text):
        return None
    values = dict(request.values)
    names: list[str] = []
    rate = stated_rate(text)
    if rate is not None and rate >= _RATE_CEILING:
        return None
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
    if down is None or placed != len(_NUMBER.findall(text)):
        return None
    variant = named_variant(product, text) or request.variant
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


def _is_loan_term(text: str, at: int) -> bool:
    return _TERM_ROLE_BEFORE.search(text[max(0, at - 32) : at]) is not None


def _asks_a_change(line: str) -> bool:
    if not line or len(line) > _MAX_CHARS:
        return False
    return _CUE.search(line) is not None or _ONLY_THE_CHANGE.match(line) is not None


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
    request: MoneyRequest,
    text: str,
    sums: tuple[list[Amount], float | None],
    values: dict[str, float],
    names: list[str],
) -> float | None:
    """Put each sum, and a share put down, into the input its words name.

    Returns the loan's down payment after the change; None when a sum names no input of
    this request, or two name the same one.
    """
    amounts, share = sums
    family = request.product.family
    once = _ONCE[family]
    loan = family == "loan"
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
        names.append("down" if role == "down" else once if role in ("price", "borrowed") else role)
    if share is not None:
        down = price * share / 100
        names.append("down")
    if loan and seen:
        if price <= down:
            return None
        values["amount"] = price - down
    return down


def _role(request: MoneyRequest, text: str, amount: Amount) -> str | None:
    """What one sum of a change line is: an input's name, or the loan's price parts."""
    family = request.product.family
    at, end = amount.span
    before = text[max(0, at - 32) : at]
    monthly = _EACH_MONTH.get(family)
    if amount.down:
        return "down" if family == "loan" else None
    if amount.monthly or (family == "card_payoff" and _PAYING.search(before)):
        return monthly
    if amount.start and family == "savings":
        return "start"
    if family == "loan" and (_BORROWED.search(before) or _LOAN_AFTER.match(text, end)):
        return "borrowed"
    # A line that is only the sum ("$18,000?") changes the request's own.
    named = _ROLE_BEFORE.search(before) or _THING_AFTER.match(text, end)
    if _PER_PERIOD.match(text, end) or not (named or _ONLY_THE_CHANGE.match(text)):
        return None
    if family == "loan":
        return "price"
    # A sum that could be either fills the one the request gave: "what if I save 300
    # instead" after "save 200 a month" is the deposit.
    if monthly is not None and _ONCE[family] not in request.values and monthly in request.values:
        return monthly
    return _ONCE[family]


def _rate_term(request: MoneyRequest) -> float | None:
    """The term the request's average was looked up for: its first ask's own."""
    if request.rate_term is not None:
        return request.rate_term
    product = request.product
    for name in ("years", "months"):
        if product.input(name) is not None:
            return request.values.get(name, product.defaults.get(name))
    return None
