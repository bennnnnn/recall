"""The temperature a chemistry question states, however it is written.

"E° = 0.80 V, n = 1, Q = 0.010 at 350 K. Use the Nernst equation to find E." was answered
0.92 V, verified: the Nernst reader knew only "T = …", so the question's 350 K went unread
and the law took 25 °C (0.94 V is right; audit 2026-11-13). A temperature is read here once,
labelled or not ("T = 310 K", "at 350 K", "at 25 °C", "a temperature of 310 K", "98.6 °F"),
for every law that has one. A question that states none is at standard conditions, 25 °C; one
that states a temperature this reader cannot take as the one temperature declines, never 25 °C.
"""

from __future__ import annotations

import math
import re

from app.modules.chemistry.schemas import ChemistryIntent
from app.modules.chemistry.solvers.constants import STANDARD_TEMPERATURE_K
from app.services.number_text import TEXT_NUMBER
from app.services.units import CELSIUS_OFFSET_K

# A number and a temperature unit. A capital K alone is kelvin; "2 K + Cl2" and "2 K(s)" are
# potassium. A unit that goes on ("°C/m", "K·kg/mol", "K^-1") is a constant's, not a temperature.
_LITERAL = re.compile(
    rf"(?<![\w.^])(?P<value>{TEXT_NUMBER})\s*(?:"
    r"(?P<kelvin>(?-i:K)(?![A-Za-z0-9(])(?!\s*(?:\+|->|→|⟶|⇌))|kelvins?\b)"
    r"|(?P<celsius>[°º]\s*C|deg(?:rees?)?\.?\s*C(?:elsius)?|celsius)"
    r"|(?P<fahrenheit>[°º]\s*F|deg(?:rees?)?\.?\s*F(?:ahrenheit)?|fahrenheit))"
    r"(?![A-Za-z/·*^⁻])(?!\s*\^)(?!\s*(?:kg|mol|m)\b)",
    re.IGNORECASE,
)
# A change of temperature, not a temperature: "ΔT = 2.5 °C", "rises by 5 K".
_DIFFERENCE = re.compile(
    r"(?:Δ\s*T|\bdelta\s*T|\bchange|\bris(?:e|es|en)|\braised|\bincreas\w*|\bdecreas\w*|"
    r"\bdrops?|\bfalls?|\bby)\s*(?:of|is|=|:)?\s*(?:about\s+)?$",
    re.IGNORECASE,
)
_DIFFERENCE_WINDOW = 24
# "T = 310" with no unit: a temperature stated, but in no unit this reader can take.
_LABELLED = re.compile(rf"(?<![A-Za-z0-9Δ])(?<!delta\s)(?-i:T)\s*=\s*(?={TEXT_NUMBER})")
# A temperature named in words ("at body temperature", "at a higher temperature"). Room and
# standard temperature are 25 °C, as the textbooks take them.
_NAMED = re.compile(r"(?<!room\s)(?<!standard\s)(?<!ambient\s)\btemp(?:erature)?s?\b", re.I)
# The kinds whose solvers hold water at 25 °C (Kw = 1.0e-14, pKw = 14).
_AT_25_C_KINDS = frozenset({"acid_base"})


def _kelvin(match: re.Match[str]) -> float:
    value = float(match.group("value"))
    if match.group("kelvin"):
        return value
    if match.group("celsius"):
        return value + CELSIUS_OFFSET_K
    return (value - 32) * 5 / 9 + CELSIUS_OFFSET_K


def _written(text: str) -> list[float]:
    found = []
    for match in _LITERAL.finditer(text):
        before = text[max(0, match.start() - _DIFFERENCE_WINDOW) : match.start()]
        if not _DIFFERENCE.search(before):
            found.append(_kelvin(match))
    return found


def stated_temperature(text: str) -> float | bool | None:
    """The one temperature ``text`` states, in kelvin.

    None when it states none, so a law may take standard conditions; False when it states a
    temperature that is not one value this reader can take (two different values, "T = 310"
    with no unit, "at body temperature"), so the law declines rather than take 25 °C.
    """
    if any(_LITERAL.match(text, label.end()) is None for label in _LABELLED.finditer(text)):
        return False
    written = _written(text)
    if len({round(value, 6) for value in written}) > 1:
        return False
    if written:
        return written[0]
    return False if _NAMED.search(text) else None


def holds_stated_temperature(text: str, intent: ChemistryIntent) -> bool:
    """Whether ``intent`` was read at the temperature ``text`` states.

    A law's temperature is the one stated, or 25 °C when none is; a solver that holds water at
    25 °C answers no question about another temperature.
    """
    stated = stated_temperature(text)
    if stated is None:
        return True
    params = intent.params
    if "temperature" in params:
        used = params["temperature"]
    elif "temperature_c" in params:
        used = params["temperature_c"] + CELSIUS_OFFSET_K
    elif intent.kind in _AT_25_C_KINDS:
        used = STANDARD_TEMPERATURE_K
    else:
        return True
    return stated is not False and math.isclose(used, float(stated), abs_tol=0.5)
