"""Which body a mass or a name belongs to, and what a question says of its collision.

A vector picture labels each body with its own mass and name, and draws the bodies moving off
together only when the question says they do. A mass or a name is tied to a body's value only
when the question ties them without doubt (review, #2593); otherwise it is tied to none, and a
description that gives it to a body is refused: no picture is better than a wrong one.

- In the mass's own clause, the one value there ("Car A of mass 1000 kg travels north at 20 m/s").
- In its sentence, when the sentence holds one value ("Car B of mass 1300 kg, travels due West
  ... at 16 m/s").
- Through a body's letter: "Car A (1000 kg) and car B (1300 kg) collide: A was travelling north
  at 20 m/s and B west at 16 m/s" ties 1300 kg to the value whose clause names B.
- In order, in a sentence that says "respectively"; a list of masses that does not ("masses of
  2 kg and 3 kg move at 4 m/s and 1 m/s") ties none.
- A sentence of its own, before the body's value ("Car A has a mass of 1000 kg. It travels north
  at 20 m/s."), when that value's sentence states no other mass.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.modules.physics.scene_drawing.headings import clause_at, sentence_at
from app.services.law_binding.givens import Given

# A body's letter or number just before its mass or in its name: "Car A (", "car B of mass ",
# "ball 2 has a mass of ", "Car A".
_LABEL_BEFORE = re.compile(
    r"(?<![\w])([A-Z]|\d)\s*(?:\(|,|of\s+mass|has\s+a\s+mass\s+of|with\s+a\s+mass\s+of"
    r"|of|is|has)?\s*$"
)
_LABEL_END = re.compile(r"(?<![\w])([A-Z]|\d)\s*$")
_RESPECTIVELY = re.compile(r"\brespectively\b", re.IGNORECASE)
# What joins a list of values: "2 kg and 3 kg", "2 kg, 3 kg".
_JOINED = r"\s*(?:,|\band\b|\bor\b|&)\s*"
# The bodies stick after their collision. General words ("join", "lock", "combined") are
# not: the roads join, the wheels lock, their combined mass is asked.
_TOGETHER = re.compile(
    r"\b(?:together|stick(?:s|ing)?|stuck|coalesce[sd]?|as\s+one|embed(?:s|ded)?"
    r"|hold(?:s|ing)?\s+on\s+to\s+each\s+other|cling(?:s|ing)?\s+to\s+each\s+other)\b",
    re.IGNORECASE,
)
_COLLIDES = re.compile(r"\b(?:collid\w*|collision|crash\w*|impact|hits?|strikes?)\b", re.I)
_APART = re.compile(r"\b(?:bounce\w*|rebound\w*|apart|separate\w*)\b", re.IGNORECASE)
# A value stated once the bodies have collided: "After the collision the first ball moves at
# 1 m/s", "... and then rebounds at 2 m/s".
_AFTER = re.compile(
    r"\b(?:after(?:wards)?|subsequently|rebound\w*|bounces?\s+back|recoils?|final(?:ly)?)\b",
    re.IGNORECASE,
)
_SETS_UP = re.compile(r"\b(?:when|if|given|where|whereby|before)\b", re.IGNORECASE)
_OPENS_AFTER = re.compile(r"^\W*(?:after(?:wards)?|subsequently|finally)\b", re.IGNORECASE)


def _within(givens: Sequence[Given], low: int, high: int) -> list[Given]:
    return [given for given in givens if low <= given.start < high]


def tie(
    text: str,
    start: int,
    end: int,
    givens: Sequence[Given],
    label: str | None = None,
    rivals: Sequence[Given] = (),
    unit: str = "",
) -> Given | None:
    """The body value (one of ``givens``) the words at ``start:end`` belong to, or None when
    the question does not say for sure. ``label`` is the body's letter when the words carry
    one; ``rivals`` the other words of their kind (the other masses), in ``unit``."""
    listed = _is_listed(text, start, end, unit)
    sentence = sentence_at(text, start)
    paired = _respective(text, start, givens, rivals, sentence)
    if paired is not None or listed:
        return paired
    clause = clause_at(text, start)
    in_clause = _within(givens, *clause)
    if len(in_clause) == 1:
        return in_clause[0]
    in_sentence = _within(givens, *sentence)
    if len(in_sentence) == 1:
        return in_sentence[0]
    if len(in_sentence) > 1:
        alternate = _alternating(start, in_sentence, _within(rivals, *sentence))
        if alternate is not None or in_clause:
            return alternate
    if label is not None:
        named = [g for g in givens if _names(text, g, label)]
        if len(named) == 1:
            return named[0]
    if in_sentence:
        return None
    later = next((g for g in givens if g.start >= end), None)
    if later is not None and not _within(rivals, *sentence_at(text, later.start)):
        return later
    return None


def _alternating(start: int, values: Sequence[Given], rivals: Sequence[Given]) -> Given | None:
    """In a sentence that writes each body's mass and value in turn ("a 1000 kg car at 25 m/s
    hits a 3000 kg truck at 10 m/s"), the value in this mass's turn: the one after it when
    each mass leads its value, the one before when each follows; None when they do not
    take turns."""
    marks = sorted([(start, "mass"), *((r.start, "mass") for r in rivals)])
    items = sorted([*marks, *((v.start, "value") for v in values)])
    kinds = [kind for _at, kind in items]
    if len(kinds) % 2 or any(a == b for a, b in zip(kinds, kinds[1:], strict=False)):
        return None
    at = [position for position, _kind in items].index(start)
    partner = at + 1 if kinds[0] == "mass" else at - 1
    return next(v for v in values if v.start == items[partner][0])


def _is_listed(text: str, start: int, end: int, unit: str) -> bool:
    """The words are one of a list of their unit ("masses of 2 kg and 3 kg"): only
    "respectively" ties it. ``end`` is where the words' unit ends."""
    if not unit:
        return False
    word = re.escape(unit)
    after = re.match(rf"{_JOINED}\d+(?:\.\d+)?\s*{word}(?![\w])", text[end : end + 24])
    before = re.search(rf"\d\s*{word}{_JOINED}$", text[max(0, start - 24) : start])
    return after is not None or before is not None


def _respective(
    text: str,
    start: int,
    givens: Sequence[Given],
    rivals: Sequence[Given],
    sentence: tuple[int, int],
) -> Given | None:
    """In a sentence that says "respectively", the words' value by order."""
    if not _RESPECTIVELY.search(text, *sentence):
        return None
    mine = sorted([*(g.start for g in _within(rivals, *sentence)), start])
    values = sorted(_within(givens, *sentence), key=lambda given: given.start)
    if len(mine) != len(values) or start not in mine:
        return None
    return values[mine.index(start)]


def _names(text: str, given: Given, label: str) -> bool:
    """The clause of ``given`` names the body by its letter: "B west at 16 m/s"."""
    low, high = clause_at(text, given.start)
    return re.search(rf"(?<![\w]){re.escape(label)}(?![\w])", text[low:high]) is not None


def label_before(text: str, start: int) -> str | None:
    """The body's letter written just before a mass: "Car A (1000 kg)" is A."""
    found = _LABEL_BEFORE.search(text[max(0, start - 24) : start])
    return found.group(1) if found else None


def label_of(name: str) -> str | None:
    """The body's letter a name ends on: "Car B" is B."""
    found = _LABEL_END.search(name)
    return found.group(1) if found else None


def stated_after(text: str, given: Given) -> bool:
    """``given`` is a value the bodies have once they collided: its own clause says so
    ("the first ball then rebounds at 1 m/s"), or its sentence opens with it ("After the
    collision, the first ball moves at 1 m/s"); "Find the final velocity when a car moving
    at 20 m/s ..." says it of no stated value."""
    low, _high = clause_at(text, given.start)
    said = [m.end() for m in _AFTER.finditer(text, low, given.start)]
    first, _end = sentence_at(text, given.start)
    opens = _OPENS_AFTER.match(text, first)
    if opens is not None:
        said.append(opens.end())
    # "the final velocity when a car moving at 20 m/s ...", "the velocity after the collision
    # if a car ...": the after word is the asked quantity's, and the stated value comes after
    # a "when" or an "if" that sets up the question.
    return any(_SETS_UP.search(text, end, given.start) is None for end in said)


def stick_together(text: str) -> bool:
    """The question says the bodies stick together after colliding: in the sentence that
    states the collision, or the one after it, and never beside "bounce apart"."""
    for found in _TOGETHER.finditer(text):
        low, high = sentence_at(text, found.start())
        if _APART.search(text, low, high):
            continue
        before = sentence_at(text, max(0, low - 2)) if low > 0 else (low, low)
        if _COLLIDES.search(text, low, high) or _COLLIDES.search(text, *before):
            return True
    return False
