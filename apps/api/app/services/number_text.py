# ruff: noqa: RUF001, RUF002, RUF003 -- the point of this module is the Unicode times and minus signs.
"""One grammar for a number written in a message, for every subject.

A number is a run of digits with an optional fraction (``12``, ``3.5``, ``.5``),
an optional sign, and optionally an ``e`` exponent. Every subject reads its
numbers with the named patterns here, so ``.5`` is one half everywhere and
never a 5 with a stray full stop.

People also write one number many ways: ``2 × 10^-6``, ``2x10^-6``,
``2*10**-6``, ``2·10⁻⁶``, ``2 \\times 10^{-6}``, ``−3``. A scanner that only
knows ``2e-6`` reads the first of those as two numbers, the 2 and the -6, and
binds whichever one sits next to a unit: "a charge of 2 × 10^-6 C" became a
charge of -6 C. ``fold_scientific`` writes the notation as one literal first,
so a coefficient and its exponent are never mistaken for two quantities.

Subject-neutral and lexical: nothing is calculated, and text that is not a
power of ten is left exactly as written. Every pattern is linear-time: no
quantifier repeats over characters the piece after it could also take.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from app.services.glyphs import SUPERSCRIPT_SIGNED

# 12, 3.5 or .5. A leading point is part of the number: skipping it once turned a
# radius of .5 into a verified radius of 5.
DECIMAL = r"(?:\d+(?:\.\d+)?|\.\d+)"
_EXPONENT = r"(?:[eE][+-]?\d+)?"
# A value that stands alone, after "=" or a label: "p = +0.5", "-3".
SIGNED_DECIMAL = rf"[+-]?{DECIMAL}"
SIGNED_DECIMAL_SCI = rf"{SIGNED_DECIMAL}{_EXPONENT}"
# A value as a student types it: its sign may stand apart ("x = - 3"), and it may be
# a fraction ("-1/2", "3/1.5"). The space is read only after a sign, so the pattern
# never competes with the "\s*" before it.
FRACTION_OR_DECIMAL = rf"(?:[+-]\s*)?{DECIMAL}(?:\s*/\s*{DECIMAL})?"
# A number in running text. A minus is its sign ("-3 °C"); a plus is the operator of
# "5+20% of 80", never part of the number. It starts where its digit run starts: a
# search that retries from every digit of a long run backtracks the rest of it each
# time, and a match that starts mid-run is only a suffix of the real number.
TEXT_DECIMAL = rf"-?(?<![\d.]){DECIMAL}"
TEXT_NUMBER = rf"{TEXT_DECIMAL}{_EXPONENT}"

DECIMAL_LITERAL = re.compile(TEXT_DECIMAL)
NUMERIC_LITERAL = re.compile(SIGNED_DECIMAL_SCI)
# Where a plain literal starts: not inside a word ("H2") or a decimal (the "5" of "1.5").
LITERAL_START = re.compile(r"(?<![\w.])(?=[+-]?(?:\d|\.\d))")


# A count written as a word: zero to twenty and the tens, one table for every reader.
# Nine private copies stopped at six, ten, twelve or fourteen, so "six notebooks" was a
# change-from-payment problem and "seven notebooks" was not (code-health audit DUP-06).
NUMBER_WORDS: dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}  # fmt: skip


def number_word_value(word: str) -> int | None:
    """``seven`` → 7; None for a word that is no count."""
    return NUMBER_WORDS.get(word.lower())


def count_word_pattern(*, low: int = 1, high: int = 20) -> str:
    """A regex alternation (no group) of the count words from ``low`` to ``high``.

    Longest first, so ``fourteen`` is tried before ``four`` where no boundary follows.
    A reader narrows the range here; it keeps no table of its own.
    """
    words = [word for word, value in NUMBER_WORDS.items() if low <= value <= high]
    return "|".join(sorted(words, key=len, reverse=True))


def bounded_decimal(max_digits: int, *, exponent_digits: int = 0) -> str:
    """``SIGNED_DECIMAL`` with at most ``max_digits`` digits on each side of the point.

    A reader that hands its number straight to a solver caps it: no one asks
    about a 40-digit value, and a bounded run keeps a failing search linear.
    ``exponent_digits`` allows an ``e`` exponent of up to that many digits.
    """
    run = f"[0-9]{{1,{max_digits}}}"
    pattern = rf"[+-]?(?:{run}(?:\.{run})?|\.{run})"
    if exponent_digits:
        pattern += rf"(?:[eE][+-]?[0-9]{{1,{exponent_digits}}})?"
    return pattern


def finite_match_value(match: re.Match[str], group: int = 0) -> float | None:
    """The matched number (or that group of it) as a float, None unless finite."""
    try:
        value = float(match.group(group))
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


def number_immediately_before(text: str, idx: int) -> re.Match[str] | None:
    """The number that ends at ``idx``, spaces aside: the 5 of ``5 %``."""
    end = idx
    while end > 0 and text[end - 1].isspace():
        end -= 1
    found = None
    for match in DECIMAL_LITERAL.finditer(text[:end]):
        found = match
    if found is None or found.end() != end:
        return None
    return found


def numeric_spans(text: str) -> list[tuple[int, int]]:
    """Complete literal spans in already-normalized solver input."""
    spans: list[tuple[int, int]] = []
    for start in LITERAL_START.finditer(text):
        if spans and start.start() < spans[-1][1]:
            continue
        match = NUMERIC_LITERAL.match(text, start.start())
        if match is not None:
            spans.append(match.span())
    return spans


_MINUS_SIGNS = "−–"  # − (minus sign) and – (en dash, OCR and phones)
_SUPERSCRIPTS = SUPERSCRIPT_SIGNED

# Thin spaces and the LaTeX spacing commands people paste from a typeset page.
_GAP = r"(?:\s|\\[,;:! ])*"
_TIMES = r"(?:[x×X*·⋅]|\\times|\\cdot)"
# A space may follow the sign ("10^- 5") but never stands in for one, so it never
# competes with the gap before it: a run of spaces is tried once, not once per split.
_SIGNED = rf"(?:[-+{_MINUS_SIGNS}]\s*)?\d{{1,3}}"
_POWER = (
    rf"(?:\^|\*\*){_GAP}"
    rf"(?:\{{\s*(?P<braced>{_SIGNED})\s*\}}|\(\s*(?P<paren>{_SIGNED})\s*\)|(?P<plain>{_SIGNED}))"
    r"|(?P<sup>[⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]{1,3})"
)
_MANTISSA = rf"[-+{_MINUS_SIGNS}]?(?:\d{{1,3}}(?:,\d{{3}})+|\d+)(?:\.\d+)?"

# A literal starts after a non-number: "x10^5" is a variable times 10^5, and
# the "000" of "6,000" is not a mantissa of its own.
_SCIENTIFIC = re.compile(
    rf"(?<![\w.,^])(?:(?P<mantissa>{_MANTISSA}){_GAP}{_TIMES}{_GAP})?"
    # A decimal exponent ("10^5.5") is not one; a full stop ending the sentence is fine.
    rf"10{_GAP}(?:{_POWER})(?!\d|\.\d)"
)


def _sign(text: str) -> str:
    text = re.sub(r"\s+", "", text)
    for minus in _MINUS_SIGNS:
        text = text.replace(minus, "-")
    return text


def _parts(match: re.Match[str]) -> tuple[str | None, int]:
    raw_exponent = (
        match.group("braced")
        or match.group("paren")
        or match.group("plain")
        or match.group("sup").translate(_SUPERSCRIPTS)
    )
    mantissa = match.group("mantissa")
    if mantissa is not None:
        mantissa = _sign(mantissa).replace(",", "")
    return mantissa, int(_sign(raw_exponent))


def _e_literal(match: re.Match[str]) -> str:
    mantissa, exponent = _parts(match)
    return f"{mantissa or '1'}e{exponent}"


def _product(match: re.Match[str]) -> str:
    mantissa, exponent = _parts(match)
    power = f"10^({exponent})" if exponent < 0 else f"10^{exponent}"
    return power if mantissa is None else f"{mantissa}*{power}"


def fold_scientific(text: str, style: Literal["e", "product"] = "e") -> str:
    """Rewrite every ``a × 10^n`` (or a bare ``10^n``) as one number.

    ``style="e"`` writes the float literal physics and chemistry read:
    ``2 × 10^-6`` → ``2e-6``, ``10^8`` → ``1e8``. ``style="product"`` writes the
    product maths hands SymPy, which keeps it exact: ``1.8·10⁻⁵`` →
    ``1.8*10^(-5)``. Exponents have at most three digits; anything else stays.
    """
    if "10" not in text:
        return text
    return _SCIENTIFIC.sub(_e_literal if style == "e" else _product, text)


# A quantity written in words: "ten metres", "a hundred metres", "two and a half kg". A
# reader that sees only digits skips "ten metres" and binds whatever value of that kind
# it can see: "A ball is dropped from ten metres onto a 1 m table" fell 1 m. A number in
# words beside a unit is therefore either read as its number or left for the caller to
# refuse the whole question (``spelled_quantities``), never skipped while another value
# is used. The caller says where a unit starts.
_SCALES = {"hundred": 100, "thousand": 1_000, "million": 1_000_000}
_WORD = "|".join(sorted((*NUMBER_WORDS, *_SCALES), key=len, reverse=True))
# Words that say an amount without saying it exactly: "a few metres", "several kg".
# "How many kWh" asks for a number: "many" and "some" are not amounts.
_VAGUE = r"few|several|couple(?:\s+of)?|dozens?(?:\s+of)?|quarter"
# "half a second", "half an hour".
_HALF = re.compile(r"(?<![\w-])half\s+an?(?![\w-])", re.IGNORECASE)
# One run of number words: "twenty-five", "two hundred and fifty", "a hundred", with an
# optional "and a half". Words are joined by a space, a hyphen or "and"; each word is
# tried once from its own start, so a failing search stays linear.
_SPELLED = re.compile(
    rf"(?<![\w-])(?:(?P<article>an?)\s+(?=(?:hundred|thousand|million)\b))?"
    rf"(?P<words>(?:{_WORD})(?:(?:\s+and\s+|\s+|-)(?:{_WORD}))*)"
    r"(?P<half>\s+and\s+a\s+half)?(?!\w)",
    re.IGNORECASE,
)
_VAGUE_RE = re.compile(rf"(?<![\w-])(?:an?\s+)?(?:{_VAGUE})(?![\w-])(?:\s+an?(?![\w-]))?", re.I)
_PARTS = re.compile(r"\s+and\s+|\s+|-", re.IGNORECASE)


def spelled_value(words: str) -> int | None:
    """The number a run of number words says, or None when it says none clearly.

    "twenty five" is 25 and "two hundred and fifty" 250; "five ten" and "twenty
    thirty" say no one number.
    """
    total = current = 0
    last: int | None = None
    for word in (part.lower() for part in _PARTS.split(words) if part):
        scale = _SCALES.get(word)
        if scale is not None:
            if scale == 100:
                if current >= 100:
                    return None
                current = (current or 1) * 100
            else:
                total += (current or 1) * scale
                current = 0
            last = scale
            continue
        value = NUMBER_WORDS[word]
        # A count follows a scale ("hundred and five") or a ten ("twenty five"), once.
        if last is not None and last < 100 and not (last % 10 == 0 and last >= 20 and value < 10):
            return None
        current += value
        last = value
    return total + current


@dataclass(frozen=True, slots=True)
class Spelled:
    """The text with every spelled quantity written as digits, and whether one was not."""

    text: str
    unread: bool


def spelled_quantities(text: str, unit_at: Callable[[str, int], object | None]) -> Spelled:
    """Write each number in words that a unit follows as its digits.

    ``unit_at(text, end)`` says whether a unit is written at ``end`` (after any spaces).
    A spelled or vague amount beside a unit that cannot be read ("a few metres",
    "five ten metres") sets ``unread``: the caller declines rather than skip it.
    """
    pieces: list[str] = []
    cursor = 0
    unread = False
    for match in _SPELLED.finditer(text):
        end = match.end()
        # "a ten-metre ladder" is 10 m too.
        hyphen = text.startswith("-", end)
        if unit_at(text, end + 1 if hyphen else _after_spaces(text, end)) is None:
            continue
        value = spelled_value(match.group("words"))
        if value is None:
            unread = True
            continue
        number = value + 0.5 if match.group("half") else value
        pieces.append(text[cursor : match.start()])
        pieces.append(f"{number:g} " if hyphen else f"{number:g}")
        cursor = end + 1 if hyphen else end
    pieces.append(text[cursor:])
    read = _HALF.sub(
        lambda match: "0.5" if unit_at(text, _after_spaces(text, match.end())) else match.group(),
        "".join(pieces),
    )
    for match in _VAGUE_RE.finditer(read):
        if unit_at(read, _after_spaces(read, match.end())) is not None:
            unread = True
    return Spelled(read, unread)


def _after_spaces(text: str, end: int) -> int:
    while end < len(text) and text[end] == " ":
        end += 1
    return end
