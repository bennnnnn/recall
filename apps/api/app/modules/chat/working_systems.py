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

import re
from collections import Counter
from dataclasses import dataclass

from app.modules.chat.tex_arithmetic import evaluate, math_statements, plain_arithmetic

# An unknown: one letter, with a subscript ("I_1", "T_{2}", "x").
_UNKNOWN = re.compile(r"(?<![\\A-Za-z])([A-Za-z])(?:_\{?([A-Za-z0-9]{1,3})\}?)?(?![A-Za-z{])")
_TOLERANCE = 0.005
# A value's unit: \\mathrm or \\text, or a bare symbol after a space ("15/13 A"); "2k" is a
# product, never 2 in kelvins (review, #2520).
_TRAILING_UNIT = re.compile(
    r"(?:(?:\s|\\[,;! ])*\\(?:mathrm|text)\s*\{[^{}]*\}|(?:\s|\\[,;! ])+[A-Za-zΩ]{1,3})\s*$"
)
_UNIT_MARK = re.compile(r"\\[,;! ]|\\(?:mathrm|text|operatorname)\b|[Ω°]")


@dataclass(frozen=True)
class UnheldEquation:
    """An equation the reply wrote, and the values it gave that do not satisfy it."""

    equation: str
    values: dict[str, float]


def unheld_equations(reply: str) -> list[UnheldEquation]:
    """Each equation in two or more unknowns that the values the reply gives them break."""

    equations: list[tuple[str, str, str, list[str], int]] = []
    values: dict[str, set[float]] = {}
    # Each value's unit as written: 6770000 m and 400 km are no terms of one sum.
    units: dict[str, set[str]] = {}
    # Each value's decimal places as written: 0.76 may be 22/29 to two (review, #2520).
    places: dict[str, int] = {}
    # Where each value is first given: a system's values are its solution, written after it.
    first_given: dict[str, int] = {}
    for at, segment in enumerate(math_statements(reply)):
        if segment.count("=") != 1 or "\\approx" in segment:
            continue
        left, right = (side.strip() for side in segment.split("="))
        unknown_left = _UNKNOWN.fullmatch(left)
        # A value may end in its unit ("I_1 = \\frac{15}{13} A", "7.2\\,\\mathrm{V}").
        bare = _TRAILING_UNIT.sub("", right)
        value = evaluate(plain) if (plain := plain_arithmetic(bare)) is not None else None
        if unknown_left is not None and value is not None:
            key = unknown_left.group(1) + (
                f"_{unknown_left.group(2)}" if unknown_left.group(2) else ""
            )
            values.setdefault(key, set()).add(round(value, 9))
            units.setdefault(key, set()).add(_unit_of(right, bare))
            places[key] = max(places.get(key, 0), _places(bare))
            first_given.setdefault(key, at)
            continue
        # An equation with a unit or a word in it is a formula, not a system to hold.
        if _UNIT_MARK.search(segment):
            continue
        found = _template(left, right)
        if found is not None:
            equations.append((segment, *found, at))
    # A system is two or more equations in the same unknowns, written before the values that
    # solve it: a point given beside a line ("2x + 3y = 7", x = 1, y = 4) solves nothing.
    equations = [
        found
        for found in equations
        if all(found[4] < first_given.get(name, -1) for name in found[3])
    ]
    systems = Counter(frozenset(found[3]) for found in equations)
    out: list[UnheldEquation] = []
    for segment, left, right, unknowns, _at in equations:
        if len(set(unknowns)) < 2 or systems[frozenset(unknowns)] < 2:
            continue
        if any(len(values.get(name, ())) != 1 for name in unknowns):
            continue
        if len({unit for name in unknowns for unit in units.get(name, set())}) > 1:
            continue
        given = {name: next(iter(values[name])) for name in unknowns}
        if not _holds(left, right, given, places):
            out.append(UnheldEquation(segment, given))
    return out


def _holds(left: str, right: str, given: dict[str, float], places: dict[str, int]) -> bool:
    """``left = right`` with ``given`` put in, within what the values' own rounding moves it:
    each value up to half its last place, times how much the equation moves with it."""
    off = _difference(left, right, given)
    if off is None:
        return True
    slack = 0.0
    for name, value in given.items():
        if places.get(name, 0) <= 0:
            continue
        moved = _difference(left, right, {**given, name: value + 0.5 * 10.0 ** -places[name]})
        if moved is None:
            return True
        slack += abs(moved - off)
    held_left = evaluate(_put(left, given)) or 0.0
    held_right = evaluate(_put(right, given)) or 0.0
    scale = max(abs(held_left), abs(held_right), 1.0)
    return abs(off) <= slack * (1 + 1e-9) + _TOLERANCE * scale


def _difference(left: str, right: str, given: dict[str, float]) -> float | None:
    """``left - right`` with ``given`` put in, or None when a side cannot be worked out."""
    held_left, held_right = evaluate(_put(left, given)), evaluate(_put(right, given))
    return None if held_left is None or held_right is None else held_left - held_right


_DECIMALS = re.compile(r"\d\.(\d+)")


def _places(value: str) -> int:
    """The most decimal places a written value shows: 0 for an exact one (15/13, 3)."""
    return max((len(found) for found in _DECIMALS.findall(value)), default=0)


_UNIT_WORD = re.compile(r"\\(?:mathrm|text)\s*\{([^{}]*)\}")


def _unit_of(right: str, bare: str) -> str:
    """The unit a value is written in: its \\mathrm/\\text words and a bare unit after it."""
    words = _UNIT_WORD.findall(right)
    tail = right[len(bare) :].strip()
    if tail and not tail.startswith("\\"):
        words.append(tail)
    return " ".join(sorted("".join(word.split()) for word in words))


def _template(left: str, right: str) -> tuple[str, str, list[str]] | None:
    """Both sides with each unknown as ``{name}``, when they are numbers and unknowns only."""

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
        probe = plain_arithmetic("".join(parts))
        if probe is None:
            return None
        sides.append(side)
    return (sides[0], sides[1], unknowns) if unknowns else None


def _put(side: str, given: dict[str, float]) -> str:
    """``side`` as plain arithmetic, each unknown replaced by its value."""

    def value(match: re.Match[str]) -> str:
        key = match.group(1) + (f"_{match.group(2)}" if match.group(2) else "")
        return f" ({given[key]!r}) "

    return plain_arithmetic(_UNKNOWN.sub(value, side)) or ""
