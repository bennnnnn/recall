r"""A value's unit in a worked block's maths, on the side of the number a reader writes it.

A unit follows its number, upright: ``3.33\,\mathrm{m/s}``. A currency sign is the one a
reader writes before it: "a 2000 W heater for 3 h at 15¢/kWh" got the card ``0.90 $``
(live, 2026-11-05), the dollar laid out after the value as a unit is. Any sign Unicode
counts as a currency symbol ($, €, £, ¥, ₹, …) that the block puts after a number moves in
front of it, whoever wrote it: the given and answer records' unit field, or the model's
own LaTeX in a substitution line. What follows the sign stays after the number
(``\$0.15\mathrm{/kWh}``). The cent sign is written after its amount (15¢), and a currency
named in letters (USD, birr) is a unit like any other: both stay where they are.
"""

from __future__ import annotations

import re
import unicodedata

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


def unit_tex(unit: str) -> str:
    """The unit after a number, upright: ``m/s^2`` → ``\\,\\mathrm{m/s²}``."""
    text = unit.strip()
    wrapped = _TEXT_WRAP.match(text)
    if wrapped is not None:
        text = wrapped.group("unit").strip()
    if not text:
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
