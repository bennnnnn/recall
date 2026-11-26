# ruff: noqa: RUF001 -- the module reads î, ĵ and k̂ as a card writes them.
"""A card that is a list of values: each piece a number standing as a value, never maths.

"(-9.043478260869565 î + 8.695652173913043 ĵ) m/s, 12.546951… m/s, 43.9° north of west"
held a vector's two components, its size and its direction, and no reading of one value took
it, so the card kept the model's sixteen digits (owner, 2026-11-25). Such a card's numbers
are each written by the rule (``card_numbers``). A piece that is maths, a symbol times a
number or a power ("2x + 3", "x^2"), is no list of values: the card is left as written.
"""

from __future__ import annotations

import re

from app.modules.chat.tex_arithmetic import evaluate, plain_arithmetic
from app.services.answer_check import plain_text

# A unit vector, a bracket round a vector, and what separates the card's values.
_UNIT_VECTOR = re.compile(r"\\hat\s*\{?\s*[ijk]\s*\}?|[îĵ]|k\u0302")
_BRACKETS = re.compile(r"\\left|\\right|[()\[\]]")
_SEPARATORS = re.compile(r",|;|\bor\b|\band\b")
# One value: a number, or a vector's signed components, then its unit (a unit's power, as
# plain text writes it: "m/s^2") or words ("north of west"), with no sign or bracket among
# them.
_VALUE = re.compile(
    r"[-+±−]?\s*\d+(?:\.\d+)?(?:\s*[-+−]\s*\d+(?:\.\d+)?)*"
    r"(?P<unit>\s*[A-Za-zµμΩ°%/·]+(?:\^-?\d+)?(?:[/·][A-Za-zµμΩ]+(?:\^-?\d+)?)*"
    r"(?:\s+[A-Za-z°]+)*)?"
)


def listed_values(value: str) -> bool:
    """``value`` is a list of values, each a number or a vector's components, at least one
    of them a vector or a second value. A sum of money is no such list: it stays to the cent
    as written."""
    from app.services.subjects.registry import MONEY

    text = _BRACKETS.sub(" ", plain_text(_UNIT_VECTOR.sub(" ", value)))
    pieces = [piece.strip() for piece in _SEPARATORS.split(text) if piece.strip()]
    read = [_VALUE.fullmatch(piece) for piece in pieces]
    if not read or not all(read):
        return False
    if any(match["unit"] and MONEY.names_currency(match["unit"]) for match in read if match):
        return False
    return len(pieces) > 1 or _UNIT_VECTOR.search(value) is not None


# An inverse sine, cosine or tangent as working writes one: \tan^{-1}, \arctan.
_INVERSE_TRIG = re.compile(
    r"\\(?:arc(?P<arc>sin|cos|tan)|(?P<name>sin|cos|tan)\s*\^\s*(?:\{\s*-\s*1\s*\}|-1))"
    r"(?![A-Za-z])"
)
_DEGREE_MARK = re.compile(r"\^\s*\{?\s*\\circ\s*\}?|°|\\degree(?![A-Za-z])")
_INLINE = re.compile(r"\$([^$\n]+)\$")
# A side that is one number as written ("43.9"): no working out, so no precision of its own.
_BARE = re.compile(r"[-+−]?\s*\d+(?:\.\d+)?")


def known_value(number: str, after: str, above: str) -> float | None:
    """The value a card's ``number`` stands for, worked out from the working above it: an
    expression on a line for the symbol the working gave that number ("θ = tan⁻¹(8.695652 /
    9.043478)" over "θ = 43.9°" is 43.879°). None when no line works it out: the card then
    keeps the figures written, never a padded digit (43.9° is no 43.90°; owner, 2026-11-25).
    ``after`` is the card's text after the number: a degree mark there reads an inverse
    tangent in degrees."""
    target = float(number)
    places = len(number.partition(".")[2])
    degrees = _DEGREE_MARK.match(after.lstrip()) is not None
    lines = [[side.strip() for side in line.split("=")] for line in _INLINE.findall(above)]
    symbols = {
        sides[0] for sides in lines if len(sides) > 1 and _read(sides[-1], degrees) == target
    }
    for sides in reversed(lines):
        if len(sides) < 2 or sides[0] not in symbols:
            continue
        for side in sides[1:]:
            if _BARE.fullmatch(_DEGREE_MARK.sub("", side).strip()):
                continue  # a number as written is no working out
            value = _read(side, degrees)
            if value is not None and abs(value - target) <= 0.5 * 10**-places * (1 + 1e-9):
                return value
    return None


def _read(side: str, degrees: bool) -> float | None:
    """One side of a line of working worked out, or None when it is no plain arithmetic."""
    tex = _DEGREE_MARK.sub("", side)
    prefix = "a" if degrees else "ra"
    tex = _INVERSE_TRIG.sub(
        lambda match: f" {prefix}{match['arc'] or match['name']}{'d' if degrees else ''} ", tex
    )
    plain = plain_arithmetic(tex)
    return None if plain is None else evaluate(plain)
