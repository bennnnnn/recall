"""Values a reply solves equations for, put back into those equations.

A slip in solving simultaneous equations is no slip in any one line: "8I₁ + 6I₂ = 10" and
"6I₁ + 10I₂ = 6" were right, and "I₁ = 15/13 A, I₂ = 1/13 A" followed, which satisfies
neither (they are 1.45 A and -0.27 A; live, 2026-11-21, two batteries in parallel). Here the
equations a reply writes in two or more unknowns are kept, and when every one of their unknowns
is later given a value of plain numbers, each equation must still hold.

Only equations of numbers and single-letter unknowns (``I_1``, ``x``, ``T_{2}``) are read; a
formula with a function, a unit or a word is left alone, and so is an unknown given two
different values (a name reused for another part).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

# An unknown: one letter, with a subscript ("I_1", "T_{2}", "x").
_UNKNOWN = re.compile(r"(?<![\\A-Za-z])([A-Za-z])(?:_\{?([A-Za-z0-9]{1,3})\}?)?(?![A-Za-z{])")
_TOLERANCE = 0.005
_TRAILING_UNIT = re.compile(
    r"(?:\s|\\[,;! ])*(?:\\(?:mathrm|text)\s*\{[^{}]*\}|[A-Za-zΩ]{1,3})\s*$"
)
_UNIT_MARK = re.compile(r"\\[,;! ]|\\(?:mathrm|text|operatorname)\b|[Ω°]")


@dataclass(frozen=True)
class UnheldEquation:
    """An equation the reply wrote, and the values it gave that do not satisfy it."""

    equation: str
    values: dict[str, float]


def unheld_equations(reply: str) -> list[UnheldEquation]:
    """Each equation in two or more unknowns that the values the reply gives them break."""
    from app.modules.chat.working_check import _INLINE_MATH, _evaluate, _plain

    equations: list[tuple[str, str, str, list[str]]] = []
    values: dict[str, set[float]] = {}
    for match in _INLINE_MATH.finditer(reply):
        segment = match.group(1)
        if segment.count("=") != 1 or "\\approx" in segment:
            continue
        left, right = (side.strip() for side in segment.split("="))
        unknown_left = _UNKNOWN.fullmatch(left)
        # A value may end in its unit ("I_1 = \\frac{15}{13} A", "7.2\\,\\mathrm{V}").
        bare = _TRAILING_UNIT.sub("", right)
        value = _evaluate(plain) if (plain := _plain(bare)) is not None else None
        if unknown_left is not None and value is not None:
            key = unknown_left.group(1) + (
                f"_{unknown_left.group(2)}" if unknown_left.group(2) else ""
            )
            values.setdefault(key, set()).add(round(value, 9))
            continue
        # An equation with a unit or a word in it is a formula, not a system to hold.
        if _UNIT_MARK.search(segment):
            continue
        found = _template(left, right)
        if found is not None:
            equations.append((segment, *found))
    out: list[UnheldEquation] = []
    for segment, left, right, unknowns in equations:
        if len(set(unknowns)) < 2 or any(len(values.get(name, ())) != 1 for name in unknowns):
            continue
        given = {name: next(iter(values[name])) for name in unknowns}
        held_left = _evaluate(_put(left, given))
        held_right = _evaluate(_put(right, given))
        if held_left is None or held_right is None:
            continue
        scale = max(abs(held_left), abs(held_right), 1.0)
        if not math.isclose(held_left, held_right, rel_tol=_TOLERANCE, abs_tol=_TOLERANCE * scale):
            out.append(UnheldEquation(segment, given))
    return out


def _template(left: str, right: str) -> tuple[str, str, list[str]] | None:
    """Both sides with each unknown as ``{name}``, when they are numbers and unknowns only."""
    from app.modules.chat.working_check import _plain

    unknowns: list[str] = []
    sides: list[str] = []
    for side in (left, right):
        parts: list[str] = []
        at = 0
        for match in _UNKNOWN.finditer(side):
            key = match.group(1) + (f"_{match.group(2)}" if match.group(2) else "")
            unknowns.append(key)
            parts += [side[at : match.start()], " (1) "]
            at = match.end()
        parts.append(side[at:])
        probe = _plain("".join(parts))
        if probe is None:
            return None
        sides.append(side)
    return (sides[0], sides[1], unknowns) if unknowns else None


def _put(side: str, given: dict[str, float]) -> str:
    """``side`` as plain arithmetic, each unknown replaced by its value."""
    from app.modules.chat.working_check import _plain

    def value(match: re.Match[str]) -> str:
        key = match.group(1) + (f"_{match.group(2)}" if match.group(2) else "")
        return f" ({given[key]!r}) "

    return _plain(_UNKNOWN.sub(value, side)) or ""
