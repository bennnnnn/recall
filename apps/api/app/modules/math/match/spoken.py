"""Maths said in words, in the notation the readers take: "what is 3 squared".

Dictation and casual typing write maths out: "what is 3 squared", "solve x squared minus
4 equals 0", "what is seven plus eight", "graph y equals x squared". The readers take
symbols, so these went to the model unchecked and the graph drew nothing. This turns the
spoken words into symbols. ``extract_math_intent`` tries it only when the message as
written gave no reading, and keeps it only when it gives one, so "plus I'm over it" stays
chat. A number word becomes a digit only beside an operator: "which one" stays words.
"""

from __future__ import annotations

import re

from app.services.text_normalize import collapse_ws

_ORDINAL_POWERS = {
    "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6, "seventh": 7,
    "eighth": 8, "ninth": 9, "tenth": 10,
}  # fmt: skip
_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19,
}  # fmt: skip
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90,
}  # fmt: skip
_UNIT = "|".join(_UNITS)
_TEN = "|".join(_TENS)
# "seven", "twenty one", "twenty-one", "one hundred", "a hundred and five".
_NUMBER_WORDS = re.compile(
    rf"\b(?:(?P<h>{_UNIT}|a)\s+hundred(?:\s+and)?\s*)?"
    rf"(?:(?P<t>{_TEN})(?:[\s-](?P<tu>{_UNIT}))?|(?P<u>{_UNIT}))?\b",
    re.IGNORECASE,
)
_ORDINAL = "|".join(_ORDINAL_POWERS)
_PHRASES: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern, re.IGNORECASE), replacement)
    for pattern, replacement in (
        (r"\bis\s+equal\s+to\b|\bequal\s+to\b|\bequals\b", "="),
        (r"\bmultiplied\s+by\b", "*"),
        (r"\bdivided\s+by\b", "/"),
        (rf"\b(?:raised\s+)?to\s+the\s+({_ORDINAL})(?:\s+power)?\b", r"^\1"),
        (r"\b(?:raised\s+)?to\s+the\s+power\s+of\b|\braised\s+to\b", "^"),
        (r"\bsquared\b", "^2"),
        (r"\bcubed\b", "^3"),
        (r"\b(?:the\s+)?square\s+root\s+of\b", "sqrt"),
        (r"\bpercent\b", "%"),
        (r"\bplus\b", "+"),
        (r"\bminus\b", "-"),
        (r"\btimes\b", "*"),
        (r"\bnegative\s+(?=\d|[a-z]\b)", "-"),
        (r"\bsine\b", "sin"),
        (r"\bcosine\b", "cos"),
        (r"\btangent\b", "tan"),
    )
)
# "3 over 4", "x over 2": a fraction only between two operands.
# A number starts after a non-word (``\b``) or after a letter, which the match takes and puts
# back (``_fraction``): ``\d+`` alone read a run of digits again from each digit (CodeQL
# py/polynomial-redos). The one change: a denominator's later digits no longer start the next
# fraction ("1 over 23 over 4" was "1 / 23 / 4", and is "1 / 23 over 4" as with one digit).
_OVER = re.compile(
    r"(?:(?:\b|(?P<lead>[^\W\d]))(?P<number>\d+(?:\.\d+)?)|(?P<term>\b[a-z]\b|\)))"
    r"\s+over\s+(?P<under>\d|[a-z]\b|\()",
    re.IGNORECASE,
)
_OPERATOR = r"[-+*/^=%]"
_ORDINAL_EXPONENT = re.compile(rf"\^({_ORDINAL})\b", re.IGNORECASE)


def _fraction(match: re.Match[str]) -> str:
    """ "3 over 4" as "3 / 4"; a letter the number follows stays in front of it."""
    over = match["number"] or match["term"]
    return f"{match['lead'] or ''}{over} / {match['under']}"


def _number(match: re.Match[str]) -> str:
    hundreds = match.group("h")
    value = 0
    if hundreds:
        value += 100 * (1 if hundreds.lower() == "a" else _UNITS[hundreds.lower()])
    if match.group("t"):
        value += _TENS[match.group("t").lower()]
        if match.group("tu"):
            value += _UNITS[match.group("tu").lower()]
    elif match.group("u"):
        value += _UNITS[match.group("u").lower()]
    return str(value)


def _numbers_beside_operators(text: str) -> str:
    """Number words next to an operator or a digit become digits; the rest stay words."""
    out: list[str] = []
    last = 0
    for match in _NUMBER_WORDS.finditer(text):
        if not match.group(0).strip():
            continue
        before = text[: match.start()].rstrip()
        after = text[match.end() :].lstrip()
        beside = re.search(rf"(?:{_OPERATOR}|\d|\(|\bsqrt)$", before) or re.match(
            rf"(?:{_OPERATOR}|\d|\))", after
        )
        if not beside:
            continue
        out.append(text[last : match.start()])
        out.append(_number(match))
        last = match.end()
    out.append(text[last:])
    return "".join(out)


def _tight_carets(text: str) -> str:
    r"""``x ^ 2`` as ``x^2``: no whitespace either side of a caret.

    ``re.sub(r"\s*\^\s*", "^", text)`` as a split: that pattern rescanned a long run of
    spaces from each of its characters (CodeQL py/polynomial-redos).
    """
    if "^" not in text:
        return text
    parts = text.split("^")
    inner = [part.strip() for part in parts[1:-1]]
    return "^".join([parts[0].rstrip(), *inner, parts[-1].lstrip()])


def spoken_math_to_plain(text: str) -> str:
    """``text`` with its spoken maths as symbols; unchanged when it says none."""
    plain = text
    for pattern, replacement in _PHRASES:
        plain = pattern.sub(replacement, plain)
    plain = _ORDINAL_EXPONENT.sub(lambda m: f"^{_ORDINAL_POWERS[m.group(1).lower()]}", plain)
    plain = _OVER.sub(_fraction, plain)
    plain = _numbers_beside_operators(plain)
    plain = re.sub(r"\bsqrt\s+(\d+(?:\.\d+)?|[a-z]\b)", r"sqrt(\1)", plain)
    plain = _tight_carets(plain)
    plain = re.sub(r"(\d)\s+%", r"\1%", plain)
    return collapse_ws(plain) if plain != text else text
