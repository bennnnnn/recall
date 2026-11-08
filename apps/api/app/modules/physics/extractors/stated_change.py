"""A change in one quantity, read from the words that state it."""

from __future__ import annotations

import re

from app.modules.physics.extractors.unit_patterns import NUMBER

# A value the words call the change itself: "increases by 3 A", "a change of 2 A".
_CHANGE_BEFORE = re.compile(r"\b(?:by|change\s+(?:in\s+(?:the\s+)?\w+\s+)?of)\s*\Z", re.I)
_VERBS = (
    r"(?:ris(?:e|es|ing)|rose|fall(?:s|ing)?|fell|drop(?:s|ped|ping)?|increas(?:e|es|ed|ing)"
    r"|decreas(?:e|es|ed|ing)|chang(?:e|es|ed|ing)|rais(?:e|es|ed|ing)|lower(?:s|ed|ing)?"
    r"|reduc(?:e|es|ed|ing)|go(?:es)?|went|grow(?:s|n)?|grew|mov(?:e|es|ed|ing)|turn(?:s|ed)?)"
)
# A value with its unit, where a change's first end is written.
_VALUE = re.compile(rf"(?:{NUMBER})\s*[^\s\d.,;]+")
# Up to a few words, then "to", "into" or an arrow before the second end: " up to ",
# ", going to ", " field into a ", " to a region of ". A word may be another quantity's
# value ("1 A in a 2 H inductor moves up to 4 A"); a bare number is the start of a range.
_WORD = r"[\s,]+(?:[A-Za-z']+|\d+(?:\.\d+)?\s*(?-i:[A-Za-zµμΩ]*[A-ZµμΩ][A-Za-zµμΩ]*))"
_TO_SECOND = re.compile(
    rf"(?:{_WORD}){{0,6}}?\s*(?:\s(?:up\s+|down\s+)?(?:in)?to|→|->)\s+"
    r"(?:(?:a|an|the|its|their)\s+)?(?:(?:rated|full|maximum|peak|final|new)\s+)?"
    r"(?:[A-Za-z]+\s+of\s+)?",
    re.I,
)
# A rating, not an end: "a fuse rated to 5 A" (review 2026-11-07).
_RATED_TO = re.compile(r"\b(?:rated|limited|fused|set)\s+(?:up\s+)?to\s+\Z", re.I)
# The next sentence naming the same thing changing: "Its current is raised to", "It falls
# to". Another current ("The current in a nearby wire rises to") is no end of this one.
_SAME_THING = re.compile(
    rf"\s+(?:(?:its|the|this)\s+(?:current|field)|it)\s+(?:then\s+)?(?:is\s+|was\s+)?{_VERBS}\b",
    re.I,
)
_ARROW = re.compile(r"\s*(?:→|->)\s*")
_FROM = re.compile(r"\bfrom\s+(?:a\s+|an\s+)?\Z", re.I)
_VERB_TO = re.compile(rf"\b{_VERBS}\s+(?:up\s+|down\s+)?to\s+\Z", re.I)
_BETWEEN = re.compile(r"\bbetween\s+\Z", re.I)
# "X initially and Y later": nothing else is said between the two ends. "1 A at first, and a
# second coil carries 4 A after" is two coils (review 2026-11-07).
_AT_FIRST = re.compile(
    r"\s+(?:at\s+first|initially|at\s+the\s+start)\s*,?\s*(?:and\s+)?(?:then\s+)?", re.I
)
_LATER = re.compile(
    rf"{_VALUE.pattern}(?:\s+(?:{NUMBER})\s*\S+)?\s+(?:after|later|finally)\b", re.I
)
# The second end closes the change: its own quantity's noun at most, then a time, a break or
# a word that carries on. "2 A that goes through it to a 5 A fuse" is a fuse's rating, not
# where the current went (review 2026-11-07).
_SECOND_END = re.compile(
    rf"{_VALUE.pattern}(?:\s+(?:field|current|region))?(?:\s+(?:in|over|within|during|after|later"
    rf"|and|then|before|when|while)\b|\s+(?:{NUMBER})|\s*[,.;!?)]|\s*\Z)",
    re.I,
)


def change_ends(text: str, first: int, second: int) -> bool:
    """The values at ``first`` and ``second`` are one change's two ends, as English says it.

    "From X (up|down) to Y", "from a X field into a Y field", "X → Y", "to Y from X",
    "between X and Y", "X at first (or initially) ... Y after (or later)", or "raised to
    Y" after an X; a sentence break ends a change, and the second end closes it. Read only
    as "X ... to Y", two values were two currents more often than one changing, and the
    plain ways a change is said were refused (reviews 2026-11-07).
    """
    lead = _VALUE.match(text, first)
    if lead is None or lead.end() > second or _SECOND_END.match(text, second) is None:
        return False
    between, before = text[lead.end() : second], text[max(0, first - 40) : first]
    breaks = list(re.finditer(r"[.;!?](?!\d)", between))
    if breaks:
        # A sentence break ends a change, but for the next sentence naming the same thing
        # changing: "carries 1 A. Its current is raised to 4 A".
        between = between[breaks[-1].end() :]
        if not _SAME_THING.match(between):
            return False
        before = ""
    if _ARROW.fullmatch(between):
        return True
    if _TO_SECOND.fullmatch(between) and not _RATED_TO.search(between):
        return _FROM.search(before) is not None or re.search(_VERBS, between, re.I) is not None
    if re.fullmatch(r"\s+from\s+(?:a\s+|an\s+)?", between, re.I):
        return _VERB_TO.search(before) is not None
    if re.fullmatch(r"\s+and\s+", between):
        return _BETWEEN.search(before) is not None
    return _AT_FIRST.fullmatch(between) is not None and _LATER.match(text, second) is not None


def stated_change(text: str, values: list[tuple[int, float, str]]) -> float | None:
    """The change a question states in one quantity, from its values in written order.

    "Increases by 3 A" is the change itself, whatever the current was; two values that are
    one change's ends (``change_ends``) give the change between them; one value alone is
    the change. Two values otherwise are two currents, not a change: "a steady 500 mA ...
    increases by 3 A" was read as 3 A - 500 mA, and an inductor gave 50 V for 60 V (review
    2026-11-07).
    """
    changes = [value for start, value, _unit in values if _CHANGE_BEFORE.search(text, 0, start)]
    if changes:
        return changes[0] if len(changes) == 1 else None
    if len(values) == 1:
        return values[0][1]
    if len(values) == 2 and change_ends(text, values[0][0], values[1][0]):
        return abs(values[1][1] - values[0][1])
    return None
