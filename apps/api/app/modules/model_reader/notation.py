"""The numbers a question writes, each read once with its language's notation.

A translation check compares values, so each original number must have one value: Spanish
"3,5" is 3.5, French "1 200" and "1.200" are 1200, Arabic's own decimal and thousands marks
are read as such, and Ethiopic numerals are added up (two-hundred is 2 x 100). A number
its language writes two ways has none: Spanish "1.200" is 1200 in Spain and 1.2 in Mexico,
so the check declines it. English is read strictly: "." is the decimal mark and "," only a
thousands mark before exactly three digits; anything else is not English notation, so
"0,125 kg" is never 125 kg. A sign is kept, as a minus sign or as words ("5 C bajo cero").
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.modules.model_reader.checks import plain_text
from app.modules.model_reader.words import below_zero_words


@dataclass(frozen=True, slots=True)
class Notation:
    """How a language marks decimals and groups thousands.

    A mark in both sets is a decimal mark unless exactly three digits follow it, and then
    the number is either: Spanish "1.5" is 1.5, "1.200" is no one value.
    """

    decimal: str
    thousands: str
    # Indian grouping: "1,20,000".
    lakh: bool = False


_SPACES = " \u00a0\u202f"
# Arabic's own thousands mark, kept apart from ",": it is never a decimal mark.
_ARABIC_THOUSANDS = "\u066c"
_KEPT_THOUSANDS = "'"
# The app's locales and the translated corpus's (Arabic, Hindi).
NOTATIONS: dict[str, Notation] = {
    "en": Notation(".", ","),
    "am": Notation(".", ","),
    "hi": Notation(".", ",", lakh=True),
    # Arabic with Western digits: "1,5" in the Maghreb, "1,200" in the Mashriq.
    "ar": Notation(".,", "," + _KEPT_THOUSANDS),
    # Spain writes "1.200,5", Mexico "1,200.5".
    "es": Notation(",.", ".," + _SPACES),
    "pt": Notation(",.", ".," + _SPACES),
    "fr": Notation(",", "." + _SPACES),
    "it": Notation(",", "." + _SPACES),
    "de": Notation(",", "." + _SPACES),
    "tr": Notation(",", "." + _SPACES),
    "ru": Notation(",.", _SPACES),
}

# A minus sign that is a sign: not "5-10" or "x-5".
_SIGN_BEFORE = re.compile(r"(?:\A|[\s(=:;,\[])\Z")
_MINUS = "-\u2212\u2012\u2013"
# Ethiopic numerals: one to nine, ten to ninety, then hundred and ten thousand.
_ETHIOPIC_RUN = re.compile("[\u1369-\u137c]+")
_ETHIOPIC_HUNDRED, _ETHIOPIC_MYRIAD = "\u137b", "\u137c"


def _ethiopic_value(run: str) -> int:
    total = group = current = 0
    for char in run:
        if char == _ETHIOPIC_HUNDRED:
            group += (current or 1) * 100
            current = 0
        elif char == _ETHIOPIC_MYRIAD:
            total = ((total + group + current) or 1) * 10_000
            group = current = 0
        else:
            current += int(unicodedata.numeric(char))
    return total + group + current


def with_ascii_numerals(text: str) -> str:
    """``text`` with each run of Ethiopic numerals as its ASCII number."""
    return _ETHIOPIC_RUN.sub(lambda run: str(_ethiopic_value(run.group(0))), text)


@dataclass(frozen=True, slots=True)
class Written:
    """One value the text writes, and where it ends (its unit follows)."""

    value: float
    start: int
    end: int


def _token_pattern(notation: Notation) -> re.Pattern[str]:
    marks = "".join(sorted(set(notation.decimal + notation.thousands) - set(_SPACES)))
    spaced = "".join(sorted(set(notation.thousands) & set(_SPACES)))
    joiner = rf"[{re.escape(marks)}]"
    if spaced:
        joiner = rf"(?:{joiner}|[{spaced}](?=\d{{3}}(?!\d)))"
    # A digit after a Latin letter is a name ("H2O", "v0"); after "^" a power.
    return re.compile(rf"(?<![A-Za-z\d.,'^])[{_MINUS}]?\d+(?:{joiner}\d+)*")


_TOKENS = {code: _token_pattern(notation) for code, notation in NOTATIONS.items()}
# "3 x 10^8" (a times sign or an x), "3e8": one value.
_POWER_AFTER = re.compile(r"\s?(?:[\u00d7x*\u00b7]\s?10\^|e)([-\u2212]?\d+)", re.IGNORECASE)


def _grouped(groups: list[str], mark: str, notation: Notation) -> bool:
    """Whether ``groups`` split by ``mark`` are one number's thousands."""
    if mark not in notation.thousands or groups[0].startswith("0"):
        return False
    if not 1 <= len(groups[0]) <= 3 or len(groups[-1]) != 3:
        return False
    lakh = notation.lakh and mark == "," and all(len(group) == 2 for group in groups[1:-1])
    return lakh or all(len(group) == 3 for group in groups[1:])


def number_value(token: str, notation: Notation) -> float | None:
    """The one value ``token`` means in ``notation``, or None when it means none or two."""
    sign = -1.0 if token[:1] in _MINUS else 1.0
    body = token.lstrip(_MINUS)
    marks = [char for char in body if not char.isdigit()]
    groups = re.split(r"\D", body)
    if not marks:
        return sign * float(body)
    if len(set(marks)) == 1:
        thousands = _grouped(groups, marks[0], notation)
        decimal = len(marks) == 1 and marks[0] in notation.decimal
        if thousands == decimal:
            return None  # either reading, or neither
        whole = "".join(groups) if thousands else f"{groups[0]}.{groups[1]}"
        return sign * float(whole)
    last, first = marks[-1], marks[0]
    if last not in notation.decimal or len(set(marks[:-1])) != 1 or first == last:
        return None
    if not _grouped(groups[:-1], first, notation):
        return None
    return sign * float("".join(groups[:-1]) + "." + groups[-1])


def plain_for(text: str) -> str:
    """``text`` as the readers take it: ASCII digits (Ethiopic numerals added up), Arabic's
    thousands mark kept apart, superscript powers as ``^n``, spaces single."""
    kept = with_ascii_numerals(text).replace(_ARABIC_THOUSANDS, _KEPT_THOUSANDS)
    return plain_text(kept).replace("\u00a0", " ").replace("\u202f", " ")


def written_values(text: str, language: str) -> tuple[str, list[Written]] | None:
    """The plain text and every value it writes, read in ``language``'s notation; None
    when a number there has no one value ("0,125" in English, "1.200" in Spanish)."""
    plain = plain_for(text)
    found = values_in(plain, language)
    return None if found is None else (plain, found)


def values_in(plain: str, language: str) -> list[Written] | None:
    """Every value ``plain`` (from ``plain_for``) writes; None when one has no one value."""
    notation = NOTATIONS.get(language, NOTATIONS["en"])
    found: list[Written] = []
    for token in _TOKENS.get(language, _TOKENS["en"]).finditer(plain):
        if found and found[-1].end > token.start():
            continue  # a power's own digits
        start, written = token.start(), token.group(0)
        if written[:1] in _MINUS and not _SIGN_BEFORE.search(plain[:start]):
            start, written = start + 1, written[1:]  # an operator, no sign
        value = number_value(written, notation)
        if value is None:
            return None
        end = token.end()
        power = _POWER_AFTER.match(plain, end)
        if power is not None:
            value *= 10.0 ** int(power.group(1).replace("\u2212", "-"))
            end = power.end()
        found.append(Written(value, start, end))
    return found


def below_zero(plain: str, end: int, language: str) -> bool:
    """Whether words right after a value (and its unit) put it below zero."""
    return below_zero_words(language).match(plain[end:]) is not None
