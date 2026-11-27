# ruff: noqa: RUF002 -- the module reads ° and √ as replies write them.
"""The exact value behind a rounded number the working wrote: a standard value of its own.

A working writes cos 30° as 0.8660 and √3 as 1.732, then multiplies on: "10 × 9.81 × 0.8660 =
84.96" is right, since 10 × 9.81 × cos 30° is 84.957, though 10 × 9.81 × 0.8660 is 84.955
(live, 2026-11-27: the check said "84.95, not 84.96" and wrote 84.95 into the working). A
decimal is such a value when it is within half its last place of one: a sine, cosine or
tangent of an angle the question or the reply writes in degrees, a square root of a number
the reply writes under a root (and half of it: √3/2), or π where π is written. A decimal of
under three figures is too coarse to be sure of (3.1 is no π). The check then holds a line to
the exact value as well as to the digits written, so a right line is never called a slip.

Only values of the reply's own angles and roots are tried, never a table of numbers: 0.8660
is cos 30° only where 30° is written.
"""

from __future__ import annotations

import math
import re

from app.modules.chat.tex_arithmetic import INLINE_MATH, masked

# An angle in degrees: 30°, 30^\circ, 30^{\circ}, 30\degree.
_DEGREES = re.compile(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*(?:°|\^\s*\{?\s*\\circ\s*\}?|\\degree\b)")
# A number under a square root: \sqrt{3}, \sqrt 3, √3.
_ROOT = re.compile(r"(?:\\sqrt\s*\{\s*(\d+(?:\.\d+)?)\s*\}|\\sqrt\s+(\d+)|√\s*(\d+(?:\.\d+)?))")
# A decimal as working writes it, never inside another number or a power.
_DECIMAL = re.compile(r"(?<![\d.^])(\d+\.\d+)(?!\d)")
# Past this a tangent is no school value (tan 89.9° is 573).
_LARGEST_TANGENT = 1e3
# A decimal of fewer figures is too coarse to name one value: 3.1 is π, or 3.1.
_LEAST_FIGURES = 3
_PI = re.compile(r"\\pi(?![A-Za-z])|π")


def standard_values(reply: str, question: str = "") -> dict[str, float]:
    """Each decimal of the reply's maths that rounds one of its standard values, with that
    value (the module docstring). A decimal that rounds two different values, or one the
    question writes (a given is exact as written), is left out."""
    candidates = _candidates(f"{question}\n{reply}")
    if not candidates:
        return {}
    given = set(_DECIMAL.findall(question))
    found: dict[str, float] = {}
    ambiguous: set[str] = set()
    for line in INLINE_MATH.findall(masked(reply)):
        for written in _DECIMAL.findall(line):
            if written in given or written in ambiguous or _figures(written) < _LEAST_FIGURES:
                continue
            value = _rounded_from(written, candidates)
            if value is None:
                continue
            if written in found and not math.isclose(found[written], value, rel_tol=1e-12):
                ambiguous.add(written)
                del found[written]
                continue
            found[written] = value
    return found


def _rounded_from(written: str, candidates: list[float]) -> float | None:
    """The one candidate ``written`` rounds, not being it already; None for none or two."""
    number = float(written)
    half = 0.5 * 10.0 ** -len(written.partition(".")[2])
    near = {
        candidate
        for candidate in candidates
        if abs(abs(candidate) - number) <= half * (1 + 1e-9) and abs(candidate) != number
    }
    if len({round(abs(value), 12) for value in near}) != 1:
        return None
    return abs(near.pop())


def _figures(written: str) -> int:
    return len(written.replace(".", "").lstrip("0"))


def _candidates(text: str) -> list[float]:
    """The standard values of ``text``'s own angles and roots, and π where it writes π."""
    values = [math.pi, 2 * math.pi, math.pi / 2] if _PI.search(text) else []
    for angle in {float(match) for match in _DEGREES.findall(text)}:
        radians = math.radians(angle)
        values += [math.sin(radians), math.cos(radians)]
        if abs(math.cos(radians)) > 1e-12 and abs(math.tan(radians)) < _LARGEST_TANGENT:
            values.append(math.tan(radians))
    for groups in _ROOT.findall(text):
        number = float(next(group for group in groups if group))
        values += [math.sqrt(number), math.sqrt(number) / 2]
    return [value for value in values if value != 0]
