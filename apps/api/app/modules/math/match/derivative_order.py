"""Which derivatives a question names, by order: the reading the extractor and the tool
check share.

"Find the 4th derivative of x^5" was a checked 5x⁴, "the fourth derivative" the same, and
"the nth derivative of e^(2x)" a checked 2e^(2x): the reader knew "second", "third" and
their digits, and read every other order as the first. "The 2ⁿᵈ derivative of eˣsin x" came
back as the first derivative too (2026-11-14); its raised suffix is the plain ordinal here
(``services/script_runs.py``). An ordinal, a Leibniz power (``d^2y/dx^2``) or Lagrange's
primes name an order; one no number gives ("the nth derivative", ``d^ny/dx^n``) is read as
``None``, and no reading answers it.

The interface is two functions: ``derivative_orders(text)`` is every order the text names,
in its order (``None`` for one no number gives, nothing when it names none), and
``asked_derivative_order(text)`` the one a question asks (the highest named, 1 when none,
``None`` when one named is no number).

An ordinal is read from the words straight before "derivative": "the eleventh derivative",
"the 1000th", "the 5-th" and "the 3 rd" were read as no ordinal at all and so as the first, a
checked first derivative (review, 2026-11-14). The words are read once, left to right, so a
32,000-character message costs what its words do; the regex this replaced took seconds on a
run of spaces after ``d^``.
"""

from __future__ import annotations

import re

from app.modules.math.match.calculus import lagrange_prime_order

_UNITS = (
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth",
)  # fmt: skip
_TEENS = (
    "tenth", "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth",
    "seventeenth", "eighteenth", "nineteenth",
)  # fmt: skip
_TENS = ("twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
# Every spelled ordinal to the ninety-ninth, then the round ones past it.
_SPELLED = {
    **{word: index + 1 for index, word in enumerate(_UNITS)},
    **{word: index + 10 for index, word in enumerate(_TEENS)},
    **{f"{word[:-1]}ieth": (index + 2) * 10 for index, word in enumerate(_TENS)},
    "hundredth": 100,
    "thousandth": 1000,
    "millionth": 1_000_000,
}
_TENS_VALUE = {word: (index + 2) * 10 for index, word in enumerate(_TENS)}
# "the hundred and first": a units word after these counts past them, and is no first.
_PAST_HUNDRED = frozenset({"hundred", "thousand", "million"})
# Shaped like an ordinal and read as none: "zeroth", "umpteenth", "zillionth".
_UNREAD_ORDINAL = re.compile(r"zeroth|[a-z]*(?:teenth|ieth|illionth)")
_SUFFIXES = frozenset({"st", "nd", "rd", "th"})
_DIGIT_ORDINAL = re.compile(r"(\d+)(?:st|nd|rd|th)")
# A letter's ordinal, which no number gives: "nth", "kth".
_LETTER_ORDINAL = re.compile(r"[a-z]th")
_WORDS = re.compile(r"[a-z0-9]+|[^\sa-z0-9]")
# Leibniz's ``d^2y/dx^2``, ``d^2/dx^2``, ``d^(n)y/dx^(n)``: the power on the first d. Read on
# text whose spaces are one each, so every piece is bounded and a run of them read once.
_LEIBNIZ_ORDER = re.compile(
    r"(?<![a-z])d ?\^ ?[({]? ?(?:(?P<digits>\d{1,2})|[a-z]) ?[)}]? ?[a-z]? ?/ ?d"
)

# Not read: no ordinal stands before "derivative".
_NONE_HERE = object()


def _ordinal_at(words: list[str], end: int) -> tuple[object, int]:
    """The ordinal whose last word is ``words[end]`` and where it starts, or ``_NONE_HERE``.
    A value of None is an order no number gives."""
    if end < 0:
        return _NONE_HERE, end
    word = words[end]
    digits = _DIGIT_ORDINAL.fullmatch(word)
    if digits:
        return int(digits.group(1)), end
    if word in _SPELLED:
        tens = end - 2 if end >= 2 and words[end - 1] in {"-", "and"} else end - 1
        if tens >= 0 and (words[tens] in _PAST_HUNDRED or words[tens].isdigit()):
            return None, tens
        if word in _UNITS and tens >= 0 and words[tens] in _TENS_VALUE:
            # "twenty-first", "thirty second"
            return _TENS_VALUE[words[tens]] + _SPELLED[word], tens
        return _SPELLED[word], end
    if _LETTER_ORDINAL.fullmatch(word) or _UNREAD_ORDINAL.fullmatch(word):
        return None, end
    if word in _SUFFIXES and end >= 1:
        # "5-th", "3 rd", "n-th", "(n+1)th": a suffix standing apart from what it counts.
        before = end - 2 if words[end - 1] == "-" and end >= 2 else end - 1
        counted = words[before]
        if counted.isdigit():
            return int(counted), before
        if counted == ")" or (len(counted) == 1 and counted.isalpha()):
            return None, before
    return _NONE_HERE, end


def _orders_before(words: list[str], at: int) -> list[int | None]:
    """The ordinals listed straight before the word at ``at``: "the first, second and third
    derivatives", "the fourth-order derivative", "the second partial derivative"."""
    end = at - 1
    if end >= 0 and words[end] == "partial":
        end -= 1
    if end >= 0 and words[end] == "order":
        end -= 2 if end >= 1 and words[end - 1] == "-" else 1
    found: list[int | None] = []
    while True:
        value, start = _ordinal_at(words, end)
        if value is _NONE_HERE:
            break
        found.append(value if isinstance(value, int) else None)
        end = start - 1
        # "first and second", "first, second", "first, second, and third"
        joined = end
        if joined >= 0 and words[joined] in {"and", "or"}:
            joined -= 1
        if joined >= 0 and words[joined] == ",":
            joined -= 1
        if joined == end:
            break
        end = joined
    return found[::-1]


def derivative_orders(text: str) -> tuple[int | None, ...]:
    """Every order the text names, in its order; ``None`` for one no number gives, and
    nothing when it names none (a plain "derivative" is the first)."""
    spaced = " ".join(text.lower().split())
    words = _WORDS.findall(spaced)
    orders: list[int | None] = []
    for at, word in enumerate(words):
        if word.startswith("deriv"):
            orders.extend(_orders_before(words, at))
    for match in _LEIBNIZ_ORDER.finditer(spaced):
        orders.append(int(match.group("digits")) if match.group("digits") else None)
    primes = lagrange_prime_order(text)
    if primes:
        orders.append(primes)
    return tuple(orders)


def asked_derivative_order(text: str) -> int | None:
    """The order a derivative question asks for: the highest it names, 1 when it names
    none, and ``None`` when one it names is no number."""
    orders = derivative_orders(text)
    if not orders:
        return 1
    if None in orders:
        return None
    return max(order for order in orders if order is not None)
