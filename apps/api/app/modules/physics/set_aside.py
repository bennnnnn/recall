"""What a question sets aside: a quantity it says to ignore is no given, and no law uses it."""

from __future__ import annotations

import re
from collections.abc import Mapping

from app.services.law_binding.units import UnitTable, dimension_of
from app.services.number_text import TEXT_NUMBER

_VERB = r"(?:ignor(?:e|es|ing)|neglect(?:s|ing)?|disregard(?:s|ing)?)"
_DETERMINER = r"(?:the|a|an|its|their|his|her|this|that|any)"
# A possessive names what owns the thing set aside, with its own value if it has one: "the
# Earth's", "the 12 V battery's". The owner is never set aside, only what it owns.
_OWNER = (
    rf"(?:{_DETERMINER}\s+)?(?:(?:{TEXT_NUMBER})\s*\S+\s+)?"
    r"(?:[A-Za-z]+\s+)?[A-Za-z]+['\u2019]s"
)
# The verb opens a clause, and only a determiner or an owner stands between it and the
# number: "Ignoring the Earth's 50 µT field", "Ignore its 5 Ω internal resistance". A noun
# there is the thing set aside, and the number belongs to the next clause: "Neglecting the
# wires 6 Ω and 3 Ω resistors are in parallel" dropped the 6 Ω (review 2026-11-07).
_OPENS = re.compile(
    rf"(?:\A|[.;:,!?(]|\b(?:and|but|then)\b)\s*{_VERB}\s+"
    rf"(?:{_OWNER}\s+|(?:{_DETERMINER}\s+){{0,3}})\Z",
    re.IGNORECASE,
)
# After the number the set-aside thing closes before anything else is said: a few words, no
# other number and no possessive, then a comma, a clause break or the end. Unclosed, nothing
# is set aside. A possessive after the number makes it the owner's: "Ignoring the 6 Ω
# resistor's heating" set the resistor itself aside, 4 A for 1.33 A (review 2026-11-07).
_CLOSES = re.compile(r"(?:[^\d.,;:!?'\u2019]|\^-?\d){0,40}?(?:[,;:!?]|\.(?!\d)|\Z)")


_OWNED_AFTER = re.compile(rf"(?:\A|[.;:,!?(])\s*{_VERB}\s+(?:{_DETERMINER}\s+)?\Z", re.IGNORECASE)


def set_aside_owner(text: str, start: int) -> bool:
    """The word at ``start`` owns what the question sets aside: "Ignoring the Moon's ..."."""
    return (
        _OWNED_AFTER.search(text, max(0, start - 40), start) is not None
        and re.match(r"\w+['\u2019]s\b", text[start:]) is not None
    )


# A comma then another value continues a list: "the 2 Ω, 3 Ω and 5 Ω resistors' tolerances",
# "the 2 Ω, the 3 Ω and the 5 Ω". After "a" or "an" a new clause starts: "Ignoring the
# trailer's 500 kg, a 1000 kg car accelerates".
_LIST_NEXT = re.compile(rf",\s*(?:(?:and|or)\s+)?(?:the\s+)?(?P<number>{TEXT_NUMBER})")


def set_aside(text: str, start: int, end: int, units: UnitTable) -> bool:
    """The number at ``start``..``end`` is a quantity the question says to ignore; ``units``
    reads the units of a list it may be in."""
    return (
        _OPENS.search(text, max(0, start - 100), start) is not None
        and _CLOSES.match(text, end) is not None
        and not _continues_a_list(text, end, units)
    )


def _continues_a_list(text: str, end: int, units: UnitTable) -> bool:
    """A comma after the value and its unit, then another value of its kind: a list, which
    the comma does not close. Set aside at the comma, "Ignoring the 2 Ω, 3 Ω and 5 Ω
    resistors' tolerances" summed 8 Ω for 10 Ω; a list never sets its values aside, and one
    ending in a possessive names their owners (review 2026-11-07). "Ignoring the 4 Ω, a 12 V
    battery" is closed: the next value is of another kind."""
    unit = units.at(text, end)
    if unit is None:
        return False
    after = _LIST_NEXT.match(text, text.find(unit[0], end) + len(unit[0]))
    following = None if after is None else units.at(text, after.end("number"))
    return following is not None and dimension_of(following[1]) == dimension_of(unit[1])


# A part set aside by name, and the inputs that are that part: "The coefficient of friction
# is 0.2, but neglect friction" was solved with the 0.2 (review 2026-11-07).
_SET_ASIDE_PARTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"friction(?:al\s+forces?)?", ("mu", "mu_s")),
    (r"internal\s+resistance", ("r_int",)),
    (r"air\s+resistance", ("drag_k", "drag_b")),
    (r"drag", ("drag_k", "drag_b")),
)
_PART = "|".join(pattern for pattern, _keys in _SET_ASIDE_PARTS)
# The parts set aside whole: a list after the verb that a break or the next instruction
# closes ("Neglecting air resistance and friction,", "Neglect friction and find"). Placed or
# timed it is only part of it, and negated none: "Ignore friction at the axle", "ignore drag
# for the first second", "Without ignoring friction" and "Never neglect friction" each
# refused a μ or a k the question uses (review 2026-11-07).
_SET_ASIDE_LIST = re.compile(
    rf"(?<!without\s)(?<!not\s)(?<!never\s)(?<!n't\s)\b{_VERB}\s+(?:the\s+|its\s+|any\s+|all\s+)?"
    rf"(?P<parts>(?:{_PART})(?:\s*(?:,|and|or)\s*(?:the\s+)?(?:{_PART}))*)"
    rf"\s*(?:[,.;:!?]|\Z|\b(?:and|then)\s+(?!(?:the\s+)?(?:{_PART})))",
    re.IGNORECASE,
)


def uses_set_aside_part(params: Mapping[str, float], text: str) -> bool:
    """A law would take an input for a part the question says to ignore."""
    named = [found.group("parts") for found in _SET_ASIDE_LIST.finditer(text)]
    return any(
        any(key in params for key in keys)
        and any(re.search(pattern, parts, re.IGNORECASE) for parts in named)
        for pattern, keys in _SET_ASIDE_PARTS
    )
