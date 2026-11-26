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

from app.modules.chat.reply_language import line_language

# The digits of a number: thousands commas, then a decimal part.
NUMBER_BODY = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
# Its power of ten, a calculator's or written out, in TeX or in prose: "1.77e-10",
# "1.8 \times 10^{-5}", "6.02 × 10^23", "1.8 x 10^-5", "3*10^8", "1.8 × 10⁻⁵". An exponent
# without braces is every digit it has ("10^23" is 10 to the 23rd, not 10^2 and 3), ending
# where the number does (a sentence's full stop may follow).
_SUPERSCRIPTS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
# A space, or TeX's: "1.8\,\times\,10^{-5}" is one number (review of #2592).
_GAP = r"(?:\s|\\[,;:! ])*"
_POWER = (
    r"(?:[eE](?P<calculator>[-+]?\d+)"
    rf"|{_GAP}(?P<times>\\times|\\cdot|[×x*·]){_GAP}10\s*"
    r"(?:\^\s*(?:\{\s*(?P<braced>[-+−]?\d+)\s*\}|(?P<bare>[-+−]?\d+)(?!\w|\.\d))"
    rf"|\^?(?P<sup>[⁻⁺]?[{_SUPERSCRIPTS}]+)))"
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
# The same where the reply's language writes a decimal comma: a comma or TeX's {,} before
# one or two digits is its decimal point ("3,7 m/s" is 3.7); before three it still groups
# thousands ("1,000"), as ``services.formal.solve.parse_number`` reads it.
_ANY_NUMBER_DECIMAL_COMMA = re.compile(
    rf"(?P<number>(?P<decimal>\d+(?:,|\{{,\}})\d{{1,2}}(?!\d))|{NUMBER_BODY}){_POWER}?"
)
# The app's languages that write a decimal comma.
DECIMAL_COMMA_LANGUAGES = frozenset({"es", "fr", "pt", "ru", "tr"})
_FROM_SUPERSCRIPT = str.maketrans(_SUPERSCRIPTS + "⁻⁺", "0123456789-+")
# A signed value as a card writes it: "-7", "−1,200", "3.85".
SIGNED_NUMBER = re.compile(rf"[-−]?(?:{NUMBER_BODY})")


def power_of(match: re.Match[str]) -> str | None:
    """The power of ten a number is written with, or None."""
    exponent = match.group("calculator") or match.group("braced") or match.group("bare")
    if exponent is None and match.group("sup") is not None:
        exponent = match.group("sup").translate(_FROM_SUPERSCRIPT)
    return None if exponent is None else exponent.replace("−", "-")


def in_tex(match: re.Match[str]) -> bool:
    """The number is written as TeX writes it: plain, or its power ``\\times 10^{n}`` (one
    unsigned digit may go unbraced). A calculator's "e", a superscript, "x", "*" or an
    unbraced "10^-3" is prose's: TeX would draw that last one 10⁻3."""
    if power_of(match) is None:
        return True
    bare = match.group("bare")
    return (
        match.group("calculator") is None
        and match.group("sup") is None
        and match.group("times") in ("\\times", "\\cdot", "×")
        and (bare is None or (bare.isdigit() and len(bare) == 1))
    )


def number_key(match: re.Match[str]) -> str:
    """The number as one key, whichever way it is written: "1,200" is 1200, "1.77e-10" and
    "1.77 \\times 10^{-10}" are both 1.77e-10. Its digits otherwise as written ("2.50")."""
    decimal = match.groupdict().get("decimal")
    if decimal is not None:
        digits = decimal.replace("{,}", ".").replace(",", ".")
    else:
        digits = match.group("number").replace(",", "")
    power = power_of(match)
    return digits if power is None else f"{digits}e{int(power)}"


def any_numbers(text: str, *, decimal_comma: bool = False) -> set[str]:
    """Every number ``text`` writes, by its ``number_key``. ``decimal_comma``: the reply's
    language writes one (``DECIMAL_COMMA_LANGUAGES``); "3,7" is then 3.7, not 3 and 7."""
    grammar = _ANY_NUMBER_DECIMAL_COMMA if decimal_comma else _ANY_NUMBER
    return {number_key(match) for match in grammar.finditer(text)}


def writes_decimal_comma(question: str, locale: str | None) -> bool:
    """Whether the reply to ``question`` writes a decimal comma: its language's, the
    message's own when it is plainly one of the app's languages, else the app's."""
    return line_language(question, locale) in DECIMAL_COMMA_LANGUAGES


def first_number(text: str) -> str | None:
    """The first number ``text`` writes, by its ``number_key``."""
    match = _ANY_NUMBER.search(text)
    return None if match is None else number_key(match)
