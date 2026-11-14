"""What a value is, as the words that introduce it name it: an amplitude, a period, a change.

``fit`` reads a question's values by dimension, so any length could fill any length input.
A question names some values by what they are, and such a value is that quantity alone:
"an amplitude of 0.1 m" is no distance travelled, "a period of 2 s" no time taken, and
"increases its speed by 10 m/s" no final speed. Read as v = d/t's d and t, a spring's
amplitude and period were verified as a maximum speed of 0.05 m/s for 0.314 m/s, and a
pendulum's length and period as its bob's speed (audit 2026-11-13).

A value so labelled fills only an input that is that quantity (``holds``): one the catalog
names for it or whose words name it (an oscillator's amplitude, a wave law's wavelength),
and, for a change, an input written as one (ΔT). A value no input holds leaves the law
unfilled, so the question declines rather than answer with another quantity.
"""

from __future__ import annotations

import re
from functools import lru_cache

from app.services.law_binding.spec import VariableSpec

CHANGE = "change"

# Each quantity a value can be named as, and the words that name it, written before the
# value ("a period of 2 s") or after it ("4 s per cycle").
LABELS: dict[str, tuple[str, ...]] = {
    "amplitude": ("amplitude",),
    "period": (
        "period",
        "per cycle",
        "each cycle",
        "per oscillation",
        "each oscillation",
        "per vibration",
        "per swing",
        "each swing",
    ),
    "wavelength": ("wavelength",),
    # An average speed is no speed at either end of a change.
    "average speed": ("average speed", "average velocity", "mean speed", "mean velocity"),
}
# The kind of value each quantity is (``fit.given_labels``).
LABEL_UNITS: dict[str, str] = {
    "amplitude": "meter",
    "period": "second",
    "wavelength": "meter",
    "average speed": "meter / second",
}
# A stretch of time said as "a period" is a duration, not an oscillation's period: "over a
# period of 5 s", "a time period of 5 s".
_DURATION = re.compile(r"(?:\btime|\b(?:over|during|in|for|within)\s+an?)\s+$")
# The label's link to its value: "of", "is", "=", a symbol assigned ("amplitude A = 0.1 m")
# or a hedge ("about").
_LINK = (
    r"(?:\s+[^\s\d.,;:?!=]{1,3}(?=\s*[=:]))?"
    r"(?:\s*(?:of|is|was|equals?|equal\s+to|=|:|≈|about|approximately|roughly|around))*\s*$"
)
# A value said as the size of a change: "increases its speed by 10 m/s", "the temperature
# rises by 20 °C". Only "by" right before the value: "heated by a 2 kW heater" names the
# heater.
_CHANGED_BY = re.compile(
    r"(?<![\w])(?:increas|decreas|ris(?:e|es|en|ing)\b|rose\b|drop|fall|fell\b|chang|gain"
    r"|los(?:e|es|t|ing)\b|grow|grew\b|shrink|slow|speed(?:s|ed|ing)?\s+up\b|warm|cool)"
    r"[^.;:?!]{0,40}?\bby\s*(?:about\s+|approximately\s+|roughly\s+)?$"
)


@lru_cache(maxsize=64)
def _before(word: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w]){re.escape(word)}{_LINK}")


@lru_cache(maxsize=64)
def _after(word: str) -> re.Pattern[str]:
    return re.compile(rf"\s*(?:a\s+|the\s+)?{re.escape(word)}(?![\w])")


def value_label(before: str, after: str) -> str | None:
    """The quantity the words around a value name it as, or None: ``before`` is the
    value's own words before it, ``after`` the words that still describe it."""
    if _CHANGED_BY.search(before):
        return CHANGE
    for label, words in LABELS.items():
        for word in words:
            found = _before(word).search(before)
            if found is not None and not _DURATION.search(before, 0, found.start()):
                return label
            if _after(word).match(after):
                return label
    return None


def holds(variable: VariableSpec, label: str | None) -> bool:
    """This input can take a value named as ``label``: any input can take an unnamed one."""
    if label is None:
        return True
    if label == CHANGE:
        # The catalogs write a change as Δ, or name it one (chemistry's ``delta_t``, "dT").
        return variable.symbol.startswith(("\\Delta", "Δ")) or variable.name.startswith("delta")
    return variable.name == label or any(word in variable.words for word in LABELS[label])
