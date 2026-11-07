"""What the server verifies for a wording of a physics problem, read as a turn reads it.

The follow-ups ask it of a problem they rewrote: a rewrite is offered only when the solver
answers it whole.
"""

from __future__ import annotations

import re

from app.modules.physics.givens import PHYSICS_UNITS
from app.services.law_binding.fit import read_givens
from app.services.law_binding.givens import Given


def verifies(text: str) -> bool:
    """True when the server answers this wording whole, as a turn would: one law, the
    laws chained, or each part."""
    return verified_display(text) is not None


def verified_display(text: str) -> str | None:
    """The verified card's answer for this wording, or None when nothing verifies it."""
    found = answers(text)
    return None if found is None else "; ".join(display for _, display in found)


def answers(text: str) -> list[tuple[str, str]] | None:
    """Each verified answer as (plain, LaTeX), in the order asked, or None."""
    from app.core.config import get_settings
    from app.modules.physics.prompt import solve_physics_request

    outcome, block = solve_physics_request(text, get_settings(), True)
    if outcome != "verified" or block is None or block.partial:
        return None
    if block.physics_parts:
        return [(part.answer, part.display_answer) for part in block.physics_parts]
    return [(block.canonical_answer or "", block.display_answer or block.canonical_answer or "")]


def results(text: str) -> list[Given] | None:
    """The previous problem's answers as values with their kinds: "-5 m/s²; 40 m"."""
    found = answers(text)
    if found is None:
        return None
    return [
        g
        for plain, _ in found
        for g in read_givens(plain_number(plain), PHYSICS_UNITS)
        if g.dimension
    ]


# A card writes a small or large number with a times sign and a raised power ("5 \u00d7
# 10⁻⁵ F"); the reader reads "5e-5 F".
_TIMES_TEN = re.compile(r"(\d(?:\.\d+)?)\s*[\u00d7x*]\s*10(?:\^\(?(-?\d+)\)?|([⁻⁰¹²³⁴⁵⁶⁷⁸⁹]+))")
_SUPERSCRIPT = str.maketrans("⁻⁰¹²³⁴⁵⁶⁷⁸⁹", "-0123456789")


def plain_number(text: str) -> str:
    def written(match: re.Match[str]) -> str:
        power = match.group(2) or (match.group(3) or "").translate(_SUPERSCRIPT)
        return f"{match.group(1)}e{power}"

    return _TIMES_TEN.sub(written, text)
