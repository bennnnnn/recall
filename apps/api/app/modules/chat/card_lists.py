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
from app.services.rounding_rule import PLACES, format_places

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
# A side that is one number once read ("43.9", "2.4\,\mathrm{m/s}", "43.9\,^\circ"): no working
# out, so no precision of its own. Decided on the side as read, units and TeX spaces gone
# (review, #2591: "v = 2.4 m/s" over a card of 2.4 m/s padded it to 2.40).
_BARE = re.compile(r"\(*[-+]?\d+(?:\.\d+)?\)*")


# The symbol a card writes its number for: "x = 1.5" is x's, read plain ("\theta" is θ).
_CARD_SYMBOL = re.compile(r"(?P<symbol>[^\s=,;:()]+)\s*=\s*$")


def known_value(number: str, after: str, above: str, before: str = "") -> float | None:
    """The value a card's ``number`` stands for, worked out from the working above it: an
    expression on a line for the symbol the working gave that number ("θ = tan⁻¹(8.695652 /
    9.043478)" over "θ = 43.9°" is 43.879°). None when no line works it out: the card then
    keeps the figures written, never a padded digit (43.9° is no 43.90°; owner, 2026-11-25).
    ``after`` is the card's text after the number: a degree mark there reads an inverse
    tangent in degrees. ``before`` is the card's text before it: a number the card writes for
    a symbol ("x = 1.5") is known only from that symbol's lines, and one it writes for none
    only when a single symbol's working ends on it (review, #2591: "x = 1.5 m" was padded to
    1.50 from "t = 3/2 = 1.5")."""
    target = float(number)
    places = len(number.partition(".")[2])
    degrees = _DEGREE_MARK.match(after.lstrip()) is not None
    lines = [[side.strip() for side in line.split("=")] for line in _INLINE.findall(above)]
    symbols = {
        sides[0] for sides in lines if len(sides) > 1 and _read(sides[-1], degrees) == target
    }
    named = _CARD_SYMBOL.search(before)
    if named is not None:
        own = _symbol(named["symbol"])
        symbols = {symbol for symbol in symbols if _symbol(symbol) == own}
    elif len({_symbol(symbol) for symbol in symbols}) > 1:
        return None
    for sides in reversed(lines):
        if len(sides) < 2 or sides[0] not in symbols:
            continue
        for side in sides[1:]:
            plain = _plain(side, degrees)
            if plain is None or _BARE.fullmatch(plain):
                continue  # no arithmetic, or a number as written: no working out
            value = evaluate(plain)
            if value is None or abs(value - target) > 0.5 * 10**-places * (1 + 1e-9):
                continue
            return value if _rounds_one_way(value, plain) else None
    return None


# A decimal the working wrote: its figures bound how far off it may be.
_DECIMAL = re.compile(r"(?<![\d.])\d*\.\d+")


def _rounds_one_way(value: float, plain: str) -> bool:
    """The value, worked from decimals that may themselves be rounded, is known to the
    rule's places: every value within its error bound (each decimal off by up to half its
    last figure, relatively, added up) rounds to the same two places. 1/0.008333 is 120.0048,
    but 0.008333 may be 1/120, so 120.0 is no 120.00 (review, #2591)."""
    error = 0.0
    for decimal in _DECIMAL.findall(plain):
        digits = decimal.replace(".", "").lstrip("0")
        if digits:
            error += 0.5 * 10 ** (1 - len(digits))
    spread = abs(value) * error
    shown = format_places(value, PLACES)
    return all(format_places(edge, PLACES) == shown for edge in (value - spread, value + spread))


def _symbol(text: str) -> str:
    """A symbol as read plain: ``\theta`` and θ, ``v_{x}`` and v_x are one."""
    return re.sub(r"[\s{}]", "", plain_text(text))


def _read(side: str, degrees: bool) -> float | None:
    """One side of a line of working worked out, or None when it is no plain arithmetic."""
    plain = _plain(side, degrees)
    return None if plain is None else evaluate(plain)


def _plain(side: str, degrees: bool) -> str | None:
    """One side of a line of working as plain arithmetic, units and TeX spaces gone."""
    tex = _DEGREE_MARK.sub("", side)
    prefix = "a" if degrees else "ra"
    tex = _INVERSE_TRIG.sub(
        lambda match: f" {prefix}{match['arc'] or match['name']}{'d' if degrees else ''} ", tex
    )
    return plain_arithmetic(tex)
