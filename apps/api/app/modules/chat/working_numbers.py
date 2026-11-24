"""A number as working writes it: read with its rounding, and written back the same way.

The working check (``working_check``) reads each result a step shows with how far its own
rounding reaches, and the fix it makes (``working_fix``) writes the right value to the same
places.
"""

from __future__ import annotations

import math
import re
from decimal import InvalidOperation

from app.modules.chat.tex_arithmetic import MAX_EXPONENT, plain_arithmetic
from app.services.school_rounding import round_places

# A written result: 14.8, -3, or 1.204 * 10^24 once it is plain text.
_SHOWN = re.compile(
    r"\(?(?P<mantissa>-?\d+(?:\.(?P<decimals>\d+))?)"
    r"(?:(?:\*10\*\*\(?|e)(?P<power>[-+]?\d+)\)?)?\)?"
)
# A whole number with this many figures before its zeros reads as rounded to them.
_ROUNDED_FIGURES = 3


def shown_number(plain: str, *, coarse: bool = False) -> tuple[float, float] | None:
    """A written result and half its last place: ``14.8`` → (14.8, 0.05). ``coarse``: said
    to be near ("≈ 1000" for 2^10), so any whole number's zeros are its rounding."""
    match = _SHOWN.fullmatch(plain)
    if match is None:
        return None
    power = int(match.group("power") or 0)
    if abs(power) > MAX_EXPONENT:
        return None
    mantissa = match.group("mantissa")
    places = len(match.group("decimals") or "")
    digits = mantissa.lstrip("-").rstrip("0")
    if not places and digits and (coarse or len(digits) >= _ROUNDED_FIGURES):
        # A large whole number's trailing zeros are its rounding: 1670 is 1666.67 to three
        # figures, its last place the tens (review, #2520). A short one is held as written:
        # "120 * 0.3 = 40" is a slip for 36.
        places = -(len(mantissa.lstrip("-")) - len(digits))
    value = float(mantissa) * 10.0**power
    return value, 0.5 * 10.0 ** (power - places)


def shown_like(value: float, shown: str) -> str:
    """``value`` written the way ``shown`` was: same places, or the same power of ten."""
    plain = plain_arithmetic(shown) or ""
    match = _SHOWN.fullmatch(plain)
    # An exact value shown ("\\frac{\\sqrt{3}}{2}") has no places of its own: two, or three
    # figures for a small one, never a whole number (review, #2520).
    places = len(match.group("decimals") or "") if match else _places_for(value)
    if match and match.group("power") is not None:
        power = math.floor(math.log10(abs(value))) if value else 0
        mantissa = value / 10.0**power
        return f"{mantissa:.{places}f} \\times 10^{{{power}}}"
    unit = (
        shown[len(match.group("mantissa")) :]
        if match and shown.startswith(match.group("mantissa"))
        else ""
    )
    try:
        number = str(round_places(value, places))
    except InvalidOperation:
        number = f"{value:.{places}f}"
    if "," in shown:
        whole, _dot, decimals = number.partition(".")
        number = f"{int(whole):,}" + (f".{decimals}" if decimals else "")
    return number + unit


def _places_for(value: float) -> int:
    """Two decimal places, or three significant figures for a value under 0.01."""
    if value == 0 or abs(value) >= 0.01:
        return 2
    return 2 - math.floor(math.log10(abs(value)))
