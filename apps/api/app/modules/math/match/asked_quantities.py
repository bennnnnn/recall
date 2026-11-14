"""The quantities a question asks for: "the gcd and lcm of 252 and 198", "the circumference
and area of a circle of radius 3", "Find the circumference of a circle of radius 3 and its
area", "its volume, surface area and diagonal".

A card stands for the whole question only when it carries each of them. "gcd and lcm"
carried 18 alone, and a complete correct reply lost its check; "circumference and area"
carried ≈18.85 alone, the area left in the working (2026-11-13 audit, MATH-04). An ask
need not list them: "A circle has radius 3. Find its area and circumference." and "the gcd of
12 and 18, and the lcm of 4 and 6" carded one value too (2026-11-14 review).
"""

from __future__ import annotations

import re

# Each quantity by its canonical name; a longer phrase claims its words first ("surface
# area" before "area", "greatest common factor" before "factor").
_NAMES: tuple[tuple[str, str], ...] = (
    ("surface_area", r"(?:total\s+)?surface\s+area"),
    ("arc_length", r"arc\s+length|length\s+of\s+the\s+arc"),
    ("gcd", r"greatest\s+common\s+(?:divisor|factor)|highest\s+common\s+factor|gcd|gcf|hcf"),
    ("lcm", r"l(?:ea|owe)st\s+common\s+multiple|lcm"),
    ("area", r"area"),
    ("perimeter", r"perimeter"),
    ("circumference", r"circumference"),
    ("diameter", r"diameter"),
    ("radius", r"radius"),
    ("diagonal", r"diagonal"),
    ("hypotenuse", r"hypotenuse"),
    ("volume", r"volume"),
)
_NAME = re.compile(
    "|".join(rf"(?P<{name}>\b(?:{pattern})\b)" for name, pattern in _NAMES), re.IGNORECASE
)
# A measure set to a value is a given, not an ask: "radius 3", "the radius is 3", "area =
# 12". A gcd or lcm "of 12 and 18" names what it is taken of.
_GIVEN_AFTER = re.compile(r"\s*(?:[-+\d=:]|\.\d|(?:is|are|was|equals|of)\s+[-+\d.])", re.IGNORECASE)
_TAKEN_OF = frozenset({"gcd", "lcm"})
# The sentences that ask: "… Find its area and circumference.", "What is …?". A statement
# before them ("A circle has radius 3.") holds givens, never an ask.
_SENTENCE = re.compile(r"(?:[^.?!\n]|\.(?=\d))+[.?!]?")
_ASKS = re.compile(
    r"\?|\b(?:find|calculate|compute|determine|work\s+out|give|state|what|how|evaluate|"
    r"estimate)\b",
    re.IGNORECASE,
)


def quantity_mentions(text: str) -> list[tuple[str, int, int]]:
    """``(quantity, start, end)`` of each quantity the asking sentences of ``text`` ask
    for, in order; a quantity set to a value there is a given and left out."""
    if len(text) > 2000:
        return []
    sentences = [match for match in _SENTENCE.finditer(text) if _ASKS.search(match.group())]
    spans = [(match.start(), match.end()) for match in sentences] or [(0, len(text))]
    return [
        (match.lastgroup or "", match.start(), match.end())
        for begin, end in spans
        for match in _NAME.finditer(text, begin, end)
        if match.lastgroup in _TAKEN_OF or _GIVEN_AFTER.match(text, match.end()) is None
    ]


def asked_quantities(text: str) -> list[str]:
    """The quantities ``text`` asks for, each once, in its order, when it asks for two or
    more: "the gcd and lcm of …", "A circle has radius 3. Find its area and circumference.",
    "the circumference of a circle of radius 3 and its area". Empty when it asks for one
    ("The area of a square is 16. Find its perimeter.")."""
    asked = list(dict.fromkeys(name for name, _start, _end in quantity_mentions(text)))
    return asked if len(asked) >= 2 else []
