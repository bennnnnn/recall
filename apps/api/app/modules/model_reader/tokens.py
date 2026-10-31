"""Every token a translation must keep: quantities, formulas, operators and powers.

A translation is checked token by token (docs/MODEL_READER.md). The server reads both
texts itself: each quantity as its signed value with its whole unit ("72 km por hora" is
72 km/h; "medio kilómetro" 0.5 km; "300 mil" 300000), each chemical formula as written
(C6H12O6 is not C6H6), and each operator and power of an expression ("8\u22123" is not "8+3",
x² not x³). A compound unit with a part the tables cannot read is ``UNREAD``, which no
English matches. Exercise and page numbers are labels, not values.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from functools import cache

from app.modules.chemistry.species_facts import formula_spans
from app.modules.model_reader.notation import below_zero, plain_for, values_in
from app.modules.model_reader.words import number_words, unit_word_at
from app.services.law_binding.units import UnitTable

# A unit the tables cannot read whole ("km por hora" without "hora"): no English matches it.
UNREAD = "?"
_OPERATORS = {"+": "+", "-": "-", "\u2212": "-", "*": "*", "\u00d7": "*", "\u00b7": "*"}
_OPERATORS |= {"/": "/", "\u00f7": "/", "=": "=", "<": "<", ">": ">"}
_POWER = re.compile(r"\^\(?(-?\d+)\)?")
_UNIT_POWER = re.compile(r"\^(-?\d)|(?<=[^\W\d_])(\d)(?![\d.,])")
# A list number at the start: "2. A car ...", "(3) ...".
_LIST_NUMBER = re.compile(r"\A\s*\(?\d{1,3}[.)]\s")


@dataclass(frozen=True, slots=True)
class Quantity:
    value: float
    unit: str | None


@dataclass(frozen=True, slots=True)
class Tokens:
    quantities: tuple[Quantity, ...]
    formulas: Counter[str]
    operators: Counter[str]
    powers: Counter[str]


def _masked(text: str, spans: Sequence[tuple[int, int]], mark: str) -> str:
    out = list(text)
    for start, end in spans:
        out[start:end] = mark * (end - start)
    return "".join(out)


@cache
def _labels(language: str) -> re.Pattern[str]:
    words = number_words("labels", language)
    names = "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True))
    return re.compile(
        rf"(?<!\w)(?:{names})\.?\s*(?:n[°ºo]\.?\s*|no\.?\s*|#\s*)?(\d+(?:[.\-]\d+)*[a-z]?)(?!\d)",
        re.IGNORECASE,
    )


def _label_spans(plain: str, language: str) -> list[tuple[int, int]]:
    spans = [found.span(1) for found in _labels(language).finditer(plain)]
    listed = _LIST_NUMBER.match(plain)
    if listed is not None:
        spans.append((listed.start(), listed.end() - 1))
    return spans


def _unit_at(
    text: str, end: int, tables: Sequence[UnitTable], language: str
) -> tuple[str | None, int]:
    """One unit right after ``end``, the longer of a table's symbol and a word."""
    best: tuple[str | None, int] = (None, end)
    for table in tables:
        read = table.at(text, end)
        if read is not None:
            stop = text.index(read[0], end) + len(read[0])
            if stop > best[1]:
                best = (read[1], stop)
    word = unit_word_at(text, end, language)
    if word is not None and word[1] > best[1]:
        best = word
    if best[0] is not None:
        power = _UNIT_POWER.match(text, best[1])
        if power is not None and "^" not in text[end : best[1]]:
            # A power closes the unit's last factor: "م/ث٢" is m/s², "ሜ²" m².
            raised = best[0] if " / " in best[0] else f"({best[0]})"
            best = (f"{raised} ** {power.group(1) or power.group(2)}", power.end())
    return best


@cache
def _per(language: str) -> re.Pattern[str]:
    words = [*number_words("per", "en"), *number_words("per", language)]
    names = "|".join(re.escape(word) for word in sorted(set(words), key=len, reverse=True))
    attached = r"\s*" if language in {"am", "ar"} else r"\s+"
    return re.compile(rf"\s*(?:/|(?:{names}){attached})(?:(?:the|el|la|le|l'|al)\s+)?", re.I)


def whole_unit(
    text: str, end: int, tables: Sequence[UnitTable], language: str
) -> tuple[str | None, int]:
    """The whole unit after a number: "km por hora" is km/h, "غ/مول" g/mol. A unit joined
    by "/" to a word the tables cannot read is ``UNREAD``."""
    unit, stop = _unit_at(text, end, tables, language)
    if unit is None:
        return None, end
    while True:
        joined = _per(language).match(text, stop)
        if joined is None:
            return unit, stop
        other, after = _unit_at(text, joined.end(), tables, language)
        if other is None:
            slash = "/" in text[stop : joined.end()]
            return (UNREAD, joined.end()) if slash else (unit, stop)
        unit, stop = f"({unit}) / ({other})", after


def _scale(text: str, end: int, language: str) -> tuple[float, int]:
    """A scale word right after a number ("300 mil", "3 हज़ार"): its factor and end."""
    for word, factor in sorted(
        number_words("scales", language).items(), key=lambda item: -len(item[0])
    ):
        found = re.compile(rf"\s+{re.escape(word)}(?!\w)", re.IGNORECASE).match(text, end)
        if found is not None:
            return float(factor), found.end()
    return 1.0, end


def _fractions(
    text: str, tables: Sequence[UnitTable], language: str
) -> list[tuple[int, int, Quantity]]:
    """Fraction words as values ("medio kilómetro", "un tercio de 90", "आधा")."""
    lower = text.lower()
    nots = [
        found.span()
        for word in number_words("not", language)
        for found in re.finditer(re.escape(word), lower)
    ]
    need_unit = set(number_words("need_unit", language))
    found: list[tuple[int, int, Quantity]] = []
    words = number_words("fractions", language)
    for word, value in sorted(words.items(), key=lambda item: -len(item[0])):
        for match in re.finditer(rf"(?<!\w){re.escape(word)}(?!\w)", lower):
            start, end = match.span()
            if any(s < end and start < e for s, e in nots) or any(
                s < end and start < e for s, e, _ in found
            ):
                continue
            unit, stop = whole_unit(text, end, tables, language)
            if word in need_unit and unit is None:
                continue
            found.append((start, stop if unit else end, Quantity(float(value), unit)))
    return found


def _operand(text: str, index: int, step: int) -> bool:
    """Whether the nearest written character from ``index`` (going ``step``) is an operand:
    a value with no unit, a formula, a bracket, a power, or a one-letter variable."""
    while 0 <= index < len(text) and text[index] == " ":
        index += step
    if not 0 <= index < len(text):
        return False
    char = text[index]
    if char in "#@" or char in (")" if step < 0 else "("):
        return True
    if not char.isalpha() or not char.isascii():
        return False
    neighbour = index + step
    return not (0 <= neighbour < len(text) and text[neighbour].isalpha())


def _operators(text: str) -> Counter[str]:
    found: Counter[str] = Counter()
    for index, char in enumerate(text):
        operator = _OPERATORS.get(char)
        if operator == "-" and 0 < index < len(text) - 1:
            if text[index - 1].isalpha() and text[index + 1].isalpha():
                continue  # a hyphen: "y a-t-il", "x-ray"
        if operator and _operand(text, index - 1, -1) and _operand(text, index + 1, 1):
            found[operator] += 1
    return found


def read_tokens(text: str, tables: Sequence[UnitTable], language: str) -> Tokens | None:
    """The tokens ``text`` writes; None when a number has no one value in its language."""
    plain = plain_for(text)
    masked = _masked(plain, _label_spans(plain, language), " ")
    spans = formula_spans(masked)
    formulas = Counter(masked[start:end] for start, end in spans)
    masked = _masked(masked, spans, "@")
    fractions = _fractions(masked, tables, language)
    masked = _masked(masked, [(start, end) for start, end, _ in fractions], " ")
    written = values_in(masked, language)
    if written is None:
        return None
    quantities = [quantity for _, _, quantity in fractions]
    marks: list[tuple[int, int, str]] = []
    for item in written:
        if marks and item.start < marks[-1][1]:
            continue  # a unit's own digit: the "2" of "م/ث2"
        factor, end = _scale(masked, item.end, language)
        unit, stop = whole_unit(masked, end, tables, language)
        value = item.value * factor
        if below_zero(masked, stop, language):
            value = -abs(value)
        quantities.append(Quantity(value, unit))
        marks.append((item.start, stop, "#" if unit is None else "%"))
    for start, end, mark in marks:
        masked = _masked(masked, [(start, end)], mark)
    powers = Counter(found.group(1) for found in _POWER.finditer(masked))
    masked = _POWER.sub(lambda found: "#" * len(found.group(0)), masked)
    return Tokens(tuple(quantities), formulas, _operators(masked), powers)
