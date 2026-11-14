"""A question asks for a value at a point: "the gradient at x = 3", "f'(3)", "at (3, 4)".

Such a question asks a number, so an answer with its variable still in it (f'(x) = 2x - 1
for f'(3)) answers another question. "when" and "where" also introduce the function a
derivative is taken of ("dy/dx when y = 2x^3 - 5x"), whose formula is no point: that
relation opens a formula, and its letter is the one differentiated (2026-11-14).
"""

from __future__ import annotations

import re

_MAX_TEXT = 2000
_AT = re.compile(
    r"\b(?:at|when|where)\s+(?:the\s+point\s+)?"
    r"(?:(?P<letter>[a-z])\s*=\s*-?(?P<number>\d+(?:\.\d+)?)|\(\s*-?\d)",
    re.IGNORECASE,
)
# A formula goes on after the number: "2x^3", "3 + x^2".
_FORMULA_ON = re.compile(r"[\w(^]|\.\d|\s*[-+*/^]")
# f'(3), y''(0): a derivative written at a number.
_PRIME_AT_NUMBER = re.compile(r"(?<![A-Za-z])[a-zA-Z]'{1,3}\(\s*-?\d")
# The letters a derivative is taken of: y in dy/dx or y', f in f'(x).
_DIFFERENTIATED = re.compile(
    r"(?<![A-Za-z])d\s*(?:\^\s*\{?\d\}?\s*)?([a-zA-Z])\s*/\s*d\s*[a-zA-Z](?![A-Za-z])"
    r"|(?<![A-Za-z])([a-zA-Z])'"
)


def differentiated_letters(text: str) -> frozenset[str]:
    """The letters ``text`` writes a derivative of, lowercase: y for dy/dx or y'', f for
    f'(x); none for "the derivative of", d/dx."""
    text = text[:_MAX_TEXT].translate({0x2019: "'", 0x2032: "'", 0x2033: "''"})
    return frozenset(
        (match.group(1) or match.group(2)).lower() for match in _DIFFERENTIATED.finditer(text)
    )


def asks_at_a_point(text: str) -> bool:
    """``text`` asks for a value at a point, not a function."""
    text = text[:_MAX_TEXT].translate({0x2019: "'", 0x2032: "'", 0x2033: "''"})
    if _PRIME_AT_NUMBER.search(text):
        return True
    differentiated = differentiated_letters(text)
    for match in _AT.finditer(text):
        letter = match.group("letter")
        defines = (
            letter is not None
            and letter.lower() in differentiated
            and _FORMULA_ON.match(text, match.end("number")) is not None
        )
        if not defines:
            return True
    return False
