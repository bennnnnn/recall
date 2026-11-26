# ruff: noqa: RUF001, RUF003 -- the grammar reads × and − as a reply writes them.
"""How a reply writes a number, read one way by every pass over its answer cards.

A number is its digits, thousands commas included ("1,200" is one number, not 1 and 200),
with its power of ten when it has one: a calculator's "1.77e-10" and "1.77 \\times
10^{-10}" are one number each, and the same one. The lead and tail passes read
"1.77e-10" as 1.77 and 10 (audit, 2026-11-25), so a sentence stating another power of ten
read as the card's numbers, and the card's own numbers as two the working never wrote.

``WRITTEN_NUMBER`` finds a value a card shows (never a script's 2 in m^{2}, a fraction's
part, or a digit inside a word); ``any_numbers`` finds every number a text writes, scripts
and fraction parts included, each as its ``number_key``.
"""

from __future__ import annotations

import re

# The digits of a number: thousands commas, then a decimal part.
NUMBER_BODY = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
# Its power of ten, a calculator's or written out.
_POWER = (
    r"(?:[eE](?P<calculator>[-+]?\d+)"
    r"|\s*(?:\\times|\\cdot|×)\s*10\s*\^\s*(?:\{\s*(?P<braced>[-+−]?\d+)\s*\}|(?P<bare>[-+]?\d)))"
)
# A number the card writes, its power of ten with it (also a calculator's "1.77e-10": its
# 10 read as a number of its own was rewritten "1.77e-1.77 \times 10^{-10}", 2026-11-21);
# never a script's (m^{2}, s^{-2}) or a fraction's part (\frac{1}{2}), nor a digit inside
# a word.
WRITTEN_NUMBER = re.compile(
    rf"(?<![\^_{{\w.,])(?<!\^[-−])(?<!\^\{{[-−])(?P<number>{NUMBER_BODY}){_POWER}?(?![\w.])"
)
# Every number a text writes, each whole with its power of ten.
_ANY_NUMBER = re.compile(rf"(?P<number>{NUMBER_BODY}){_POWER}?")
# A signed value as a card writes it: "-7", "−1,200", "3.85".
SIGNED_NUMBER = re.compile(rf"[-−]?(?:{NUMBER_BODY})")


def power_of(match: re.Match[str]) -> str | None:
    """The power of ten a number is written with, or None."""
    exponent = match.group("calculator") or match.group("braced") or match.group("bare")
    return None if exponent is None else exponent.replace("−", "-")


def number_key(match: re.Match[str]) -> str:
    """The number as one key, whichever way it is written: "1,200" is 1200, "1.77e-10" and
    "1.77 \\times 10^{-10}" are both 1.77e-10. Its digits otherwise as written ("2.50")."""
    digits = match.group("number").replace(",", "")
    power = power_of(match)
    return digits if power is None else f"{digits}e{int(power)}"


def any_numbers(text: str) -> set[str]:
    """Every number ``text`` writes, by its ``number_key``."""
    return {number_key(match) for match in _ANY_NUMBER.finditer(text)}


def first_number(text: str) -> str | None:
    """The first number ``text`` writes, by its ``number_key``."""
    match = _ANY_NUMBER.search(text)
    return None if match is None else number_key(match)
