r"""A value's unit in a worked block's maths, on the side of the number a reader writes it.

A unit follows its number, upright: ``3.33\,\mathrm{m/s}``. A currency sign is the one a
reader writes before it: "a 2000 W heater for 3 h at 15¢/kWh" got the card ``0.90 $``
(live, 2026-11-05), the dollar laid out after the value as a unit is. Any sign Unicode
counts as a currency symbol ($, €, £, ¥, ₹, …) that the block puts after a number moves in
front of it, whoever wrote it: the given and answer records' unit field, or the model's
own LaTeX in a substitution line. What follows the sign stays after the number
(``\$0.15\mathrm{/kWh}``). The cent sign is written after its amount (15¢), and a currency
named in letters (USD, birr) is a unit like any other: both stay where they are. A unit
the records name, written by the model after a number in its working (``L = 8 gal``), is
set upright as the records' own lines set it (``units_upright``).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence

from app.services.latex_groups import map_groups

_SUPERSCRIPTS = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")
_POWER = re.compile(r"\^\{?(-?\d+)\}?")
_TEXT_WRAP = re.compile(r"^\\(?:text|mathrm)\s*\{(?P<unit>[^{}]*)\}$")
_UNIT_SYMBOLS = {
    "°": r"^\circ",
    "deg": r"^\circ",
    "degree": r"^\circ",
    "degrees": r"^\circ",
    "°C": r"\,^\circ\mathrm{C}",
    "℃": r"\,^\circ\mathrm{C}",
    "degC": r"\,^\circ\mathrm{C}",
    "°F": r"\,^\circ\mathrm{F}",
    "%": r"\,\%",
}
# A number ending on a digit ("5, \$3" is two items, not "5," then its dollar), then the
# spacing before a sign that may be its currency: bare (``\$``, ``€``)
# or opening an upright unit (``\mathrm{\$/kWh}``). Whether it is a currency sign is
# Unicode's call (``_currency``), so the pattern takes any one symbol there.
_SIGN_AFTER_NUMBER = re.compile(
    r"(?<![\w.])(?P<number>\d(?:(?:[\d.,]|\{,\})*\d)?)(?:\s|\\[,;:! ]|~)*"
    r"(?:\\(?P<command>mathrm|text)\s*\{\s*(?P<wrapped>\\\$|[^\w\s\\{}])(?P<rest>[^{}]*)\}"
    r"|(?P<sign>\\\$|[^\w\s\\{}]))"
)
# Signs written after the amount: a fraction of a currency's unit.
_WRITTEN_AFTER = frozenset("¢")
# What a model writes in the unit field of a pure number, a fraction or a count: a dash,
# or a word for none ("f | \frac{1}{2} | —" drew "½ —", 2026-11-11). A pure number has
# no unit to show.
_NO_UNIT = frozenset({"none", "unitless", "dimensionless", "no unit", "no units"})
# Marks that are a unit on their own, though Unicode files them as punctuation.
_UNIT_MARKS = frozenset("%\u2030\u2032\u2033'\"")  # %, per mille, prime, double prime


def _names_no_unit(text: str) -> bool:
    """A unit field that holds no unit: a placeholder word, or marks with no letter,
    digit or symbol in them (a dash or a hyphen)."""
    # "n/a" in lower case only: "N/A" is newtons per ampere.
    if text.lower() in _NO_UNIT or text == "n/a":
        return True
    return not any(unicodedata.category(char)[0] in "LNS" or char in _UNIT_MARKS for char in text)


def unit_tex(unit: str) -> str:
    """The unit after a number, upright: ``m/s^2`` → ``\\,\\mathrm{m/s²}``."""
    text = unit.strip()
    wrapped = _TEXT_WRAP.match(text)
    if wrapped is not None:
        text = wrapped.group("unit").strip()
    if not text or _names_no_unit(text):
        return ""
    if text in _UNIT_SYMBOLS:
        return _UNIT_SYMBOLS[text]
    if "\\" in text:
        return rf"\,{text}"  # written in LaTeX already
    plain = _POWER.sub(lambda match: match.group(1).translate(_SUPERSCRIPTS), text)
    plain = plain.replace("*", "·").replace("{", "").replace("}", "")
    # A bare $ would close the maths around it.
    plain = plain.replace("%", r"\%").replace("$", r"\$")
    return rf"\,\mathrm{{{plain}}}"


def _currency(sign: str) -> bool:
    mark = sign.removeprefix("\\")
    return unicodedata.category(mark) == "Sc" and mark not in _WRITTEN_AFTER


def _sign_first(match: re.Match[str]) -> str:
    sign = match.group("wrapped") or match.group("sign")
    if not _currency(sign):
        return match.group(0)
    shown = r"\$" if sign.removeprefix("\\") == "$" else rf"\mathrm{{{sign}}}"
    rest = (match.group("rest") or "").strip()
    after = rf"\{match.group('command')}{{{rest}}}" if rest else ""
    return f"{shown}{match.group('number')}{after}"


def currency_first(tex: str) -> str:
    """Each currency sign laid after a number put before it: ``0.90\\,\\mathrm{\\$}`` →
    ``\\$0.90``, ``0.15\\,\\mathrm{\\$/kWh}`` → ``\\$0.15\\mathrm{/kWh}``."""
    return _SIGN_AFTER_NUMBER.sub(_sign_first, tex)


def quantity_tex(value: str, unit: str) -> str:
    """A value and its unit in maths, the unit where a reader writes it."""
    return currency_first(f"{value}{unit_tex(unit)}")


# A group whose letters are set upright, words or a unit: what it holds is not maths.
WORD_GROUP = re.compile(r"\\(?P<command>text|textrm|mathrm|mbox|operatorname)\s*\{")
# A unit word: two letters or more in a row ("gal", "Birr", "km/h").
_UNIT_WORD = re.compile(r"[A-Za-z]{2,}")
# What a unit is written in: letters, a slash, a power, a dot between two units.
_PLAIN_UNIT = re.compile(r"[A-Za-z/·^\-\d]+")


def declared_units(fields: Iterable[str]) -> tuple[str, ...]:
    """The units a block's given and answer records name in their unit fields, as a number
    in its working may carry them: a unit word, singular or plural, longest first. A unit
    of one letter is left out: it may be a symbol, and "4s" in ``4s + 20 = 2(s + 20)`` is
    4 times s, never 4 seconds (the phone sets a spaced one at the end of a value upright)."""
    units: set[str] = set()
    for field in fields:
        wrapped = _TEXT_WRAP.match(field.strip())
        unit = wrapped.group("unit").strip() if wrapped else field.strip()
        if not _PLAIN_UNIT.fullmatch(unit) or not _UNIT_WORD.search(unit) or _names_no_unit(unit):
            continue
        units.add(unit)
        # A unit word's other number: "year" and "years", "hours" and "hour" ("ms" stays).
        if unit.isalpha() and not unit.endswith("s"):
            units.add(f"{unit}s")
        elif unit.isalpha() and len(unit) > 3:
            units.add(unit[:-1])
    return tuple(sorted(units, key=lambda unit: (-len(unit), unit)))


def units_upright(tex: str, units: Sequence[str]) -> str:
    """Each of ``units`` written after a number in the model's maths set as the answer line
    sets it: ``L = 8 gal`` → ``L = 8\\,\\mathrm{gal}``. Read as maths, "8 gal" was 8 times
    g, a and l, drawn as italic letters with no space ("8gal", 2026-11-12). Only a unit
    that ends the number's value is one: a letter, script, bracket or slash after it
    makes it part of something else, and a word group's text is words, not maths."""
    if not units:
        return tex
    pattern = re.compile(
        r"(?<![\w.^_\\])(?P<number>\d+(?:\.\d+)?)(?:\s|\\[,;:! ]|~)*"
        rf"(?P<unit>{'|'.join(re.escape(unit) for unit in units)})(?![\w^{{(/·])"
    )
    return map_groups(
        tex,
        WORD_GROUP,
        lambda maths: pattern.sub(lambda match: match["number"] + unit_tex(match["unit"]), maths),
        lambda opened, text: f"{opened.group(0)}{text}}}",
    )
