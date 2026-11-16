"""The server's answer to a question a model wrote down as maths, as a card draws it."""

from __future__ import annotations

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
        return f"{_number_latex(self.value)}\\ {unit_latex(self.unit)}".rstrip("\\ ")


def _number_latex(value: float) -> str:
    """Four significant figures; a power of ten for very large or small values."""
    if value == 0 or 1e-3 <= abs(value) < 1e6:
        return f"{value:.4g}"
    mantissa, exponent = f"{value:.3e}".split("e")
    return f"{mantissa}\\times 10^{{{int(exponent)}}}"


# Unit spellings pint reads, as a card draws them.
_UNIT_LATEX = {
    "degC": "^\\circ\\mathrm{C}",
    "delta_degC": "^\\circ\\mathrm{C}",
    "degF": "^\\circ\\mathrm{F}",
    "degree": "^\\circ",
    "ohm": "\\Omega",
    "percent": "\\%",
}


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
