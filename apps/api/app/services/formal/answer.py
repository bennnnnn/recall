"""The server's answers to a question a model wrote down as maths, as a card draws them."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class FormalValue:
    """The server's value for one part the question asks ("" for the whole question)."""

    part: str
    symbol: str
    value: float
    unit: str
    # The value with each standard constant it uses anywhere in its tolerance (g as 9.8
    # or 10): a reply in that range made an assumption, not an error.
    low: float
    high: float
    # The numbers, as the question writes them, this value is worked out from.
    uses: tuple[float, ...]
    # The setup's own answer agrees; None when it gave none.
    agrees: bool | None = None

    @property
    def card_value(self) -> str:
        """The value as card maths: "31.07\\ \\mathrm{m}"."""
        return card_maths_of(self.value, self.unit)


@dataclass(frozen=True)
class StatedConflict:
    """A relation the question's values must keep and do not (a lever said to balance whose
    moments differ): ``left`` and ``right`` are its two sides as card maths, ``broken`` the
    relation they stand in ("\\neq", ">", "<")."""

    meaning: str
    left: str
    broken: str
    right: str


@dataclass(frozen=True)
class FormalAnswer:
    """What the server worked out from the model's setup: each part's value whose setup
    answer agrees with it, and the checks the question's own values break."""

    values: tuple[FormalValue, ...] = ()
    conflicts: tuple[StatedConflict, ...] = ()


def card_maths_of(value: float, unit: str) -> str:
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


def unit_latex(unit: str) -> str:
    """``m/s^2`` as ``\\mathrm{m/s^{2}}``; "" for a pure number."""
    text = unit.strip()
    if not text or text == "dimensionless":
        return ""
    if text in _UNIT_LATEX:
        return _UNIT_LATEX[text]
    text = re.sub(r"\*\*|\^", "^", text)
    text = re.sub(r"\^(-?\d+)", r"^{\1}", text)
    # One backslash: two are a LaTeX line break (N*m showed a break, then "cdot").
    product = re.sub(r"\s*\*\s*", "\\\\cdot ", text)
    return f"\\mathrm{{{product}}}"
