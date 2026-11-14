"""The quantities a question asks for together: "the gcd and lcm of 252 and 198", "the
circumference and area of a circle of radius 3", "its volume, surface area and diagonal".

A card stands for the whole question only when it carries each of them. "gcd and lcm"
carried 18 alone, and a complete correct reply lost its check; "circumference and area"
carried ≈18.85 alone, the area left in the working (2026-11-13 audit, MATH-04).
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
# What joins two names of one list: "and", a comma, "&", "as well as", "plus".
_JOIN = re.compile(
    r"\s*(?:,\s*(?:and\s+)?|\s+and\s+|\s*&\s*|\s+as\s+well\s+as\s+|\s+plus\s+)"
    r"(?:(?:the|its|their|his|her)\s+)?(?:(?:length\s+of\s+the|value\s+of\s+the)\s+)?$",
    re.IGNORECASE,
)
# A measure set to a value is a given, not an ask: "radius 3", "the radius is 3", "area =
# 12". A gcd or lcm "of 12 and 18" names what it is taken of.
_GIVEN_AFTER = re.compile(r"\s*(?:[-+\d.=:]|(?:is|are|was|equals|of)\s+[-+\d.])", re.IGNORECASE)
_TAKEN_OF = frozenset({"gcd", "lcm"})


def asked_quantities(text: str) -> list[str]:
    """The longest list of two or more quantities ``text`` asks for together, in its order;
    empty when it lists fewer. "The area of a circle, the radius is 3" asks for one."""
    if len(text) > 2000:
        return []
    found = [
        (match.start(), match.end(), match.lastgroup or "")
        for match in _NAME.finditer(text)
        if match.lastgroup in _TAKEN_OF or _GIVEN_AFTER.match(text, match.end()) is None
    ]
    best: list[str] = []
    run: list[str] = []
    for index, (start, _end, name) in enumerate(found):
        joined = index > 0 and _JOIN.match(text[found[index - 1][1] : start]) is not None
        run = [*run, name] if joined else [name]
        if len(set(run)) > len(set(best)):
            best = list(dict.fromkeys(run))
    return best if len(best) >= 2 else []
