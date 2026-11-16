"""The server's answer to a question a model wrote down as maths, as a card draws it."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FormalAnswer:
    """The server's answer to a physics question, from the model's setup: shown only when
    the setup's own answer agrees with it (``formal_answer``)."""

    value: float
    unit: str

    @property
    def card_value(self) -> str:
        """The value as card maths: "31.07\\ \\mathrm{m}"."""
        return _card(self.value, self.unit)

    @property
    def same_answers(self) -> list[str]:
        """The card value and the other ways a reply may state the same answer: a pure
        number as a percentage or a percentage as a fraction (an efficiency, 0.9 or 90%),
        and a negative value's size (a braking force's sign is the reply's convention)."""
        forms = [self.card_value]
        if unit_latex(self.unit) == "":
            forms.append(_card(self.value * 100, "percent"))
        elif self.unit.strip() in _PERCENT:
            forms.append(_card(self.value / 100, ""))
        if self.value < 0:
            forms += [form.replace("-", "", 1) for form in list(forms)]
        return forms


def _card(value: float, unit: str) -> str:
    return f"{_number_latex(value)}\\ {unit_latex(unit)}".rstrip("\\ ")


def _number_latex(value: float) -> str:
    """Four significant figures, written out ("12350", "0.001234"); a power of ten for very
    large or small values. Never Python's exponent form ("5e+04"), which a card shows raw."""
    rounded = float(f"{value:.4g}")
    if rounded == 0:
        return "0"
    if 1e-3 <= abs(rounded) < 1e6:
        decimals = max(0, 3 - math.floor(math.log10(abs(rounded))))
        text = f"{rounded:.{decimals}f}"
        return text.rstrip("0").rstrip(".") if "." in text else text
    mantissa, exponent = f"{value:.3e}".split("e")
    mantissa = mantissa.rstrip("0").rstrip(".")
    return f"{mantissa}\\times 10^{{{int(exponent)}}}"


# Unit spellings pint reads, as a card draws them.
_UNIT_LATEX = {
    "degC": "^\\circ\\mathrm{C}",
    "delta_degC": "^\\circ\\mathrm{C}",
    "degF": "^\\circ\\mathrm{F}",
    "degree": "^\\circ",
    "ohm": "\\Omega",
    "percent": "\\%",
    "%": "\\%",
}
_PERCENT = frozenset({"percent", "%"})


def unit_latex(unit: str) -> str:
    """``m/s^2`` as ``\\mathrm{m/s^{2}}``; "" for a pure number."""
    text = unit.strip()
    if not text or text == "dimensionless":
        return ""
    if text in _UNIT_LATEX:
        return _UNIT_LATEX[text]
    text = re.sub(r"\*\*|\^", "^", text)
    text = re.sub(r"\^(-?\d+)", r"^{\1}", text)
    return f"\\mathrm{{{text.replace('*', '\\\\cdot ')}}}"
