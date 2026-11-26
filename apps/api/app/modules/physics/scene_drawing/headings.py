"""The directions a question states, each read as an angle and tied to the value it goes with.

A vector picture's arrows point where the question says: "20 m/s due North", "16 m/s to the
left", "moving left at 3 m/s", "12 m/s on a heading 30° east of north", "a force of 20 N at
30° above the horizontal", "a bearing of 060°". Each direction the question writes is read
as the angle the arrow points (degrees counter-clockwise from east, which is also "to the
right"; north is up). A wind or a current is named for where it comes from: "a wind from
the west", "a west wind", "a westerly" all point east (review, #2593). Each direction is
given to the stated quantity it describes (``owner``): the nearest one in its own clause
("Car B travels due West along the other road at 16 m/s"), else in its sentence ("swims due
north at 1.5 m/s across a river flowing due east at 2 m/s" gives north to 1.5 m/s and east
to 2 m/s); "20 m/s and 16 m/s due north and due west respectively" pairs them in order. The
same tie holds a body's mass and name to its own value (``vectors``). A direction a
description names for an arrow is drawn only when it is one the question gives that arrow's
value. A description's own direction is read by the same grammar (``read_heading``), and may
also name an angle to an earlier arrow ("90° to F1"), which the question must state ("at
right angles", "perpendicular", "90°").
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.services.law_binding.givens import Given

_POINTS = {"east": 0.0, "north": 90.0, "west": 180.0, "south": 270.0}
_LETTERS = {"e": "east", "n": "north", "w": "west", "s": "south"}
# A number starts where its digits start, never inside a run of them: a long run is read once.
_NUMBER = r"(?<![\d.])(\d+(?:\.\d+)?)\s*(?:°|º|˚|deg(?:rees?)?\b)"
_POINT = r"(north|south|east|west)"
# What may lead a compass point and still name where the arrow points: "due north", "to the
# north", "towards the east", "heading north" (a description copies the question's words).
_LEAD = r"(?:(?:to|towards?)\s+(?:the\s+)?|heading\s+(?:due\s+)?|due\s+)?"
# "30° north of east": from east, turned 30° toward north.
_OF = re.compile(rf"{_NUMBER}\s*(?:to\s+the\s+)?{_POINT}\s+of\s+(?:due\s+)?{_POINT}", re.I)
# "N 30° E", "S45°W": from north, turned 30° toward east.
_LETTERED = re.compile(rf"\b([NS])\s*{_NUMBER}\s*([EW])\b", re.I)
# "a bearing of 060°", "on a heading of 120°": clockwise from north.
_BEARING = re.compile(rf"\b(?:bearing|heading)\s+(?:of\s+)?{_NUMBER}", re.I)
# "30° above the horizontal", "15° below the horizontal": to the right unless it says left.
_HORIZONTAL = re.compile(
    rf"{_NUMBER}\s*(above|below)\s+the\s+horizontal(\s+(?:to\s+the\s+|towards?\s+the\s+)?left)?",
    re.I,
)
# "north-east" (any dash), "northwest": halfway between two points. An "-erly" is where
# a wind comes from, or where a body goes ("in a westerly direction"): ``_erly`` reads which.
_BETWEEN = re.compile(
    rf"\b{_LEAD}(north|south)[\s\-\u2013\u2011]?(east|west)(?:wards?|ern|(erly))?\b", re.I
)
# Three points run together ("north-north-east"): a direction this grammar does not draw.
_COMPOUND = re.compile(
    r"\b(?:north|south|east|west)(?:[\s\-\u2013\u2011]+(?:north|south|east|west)){2,}\b",
    re.I,
)
_HALFWAY = {
    ("north", "east"): 45.0,
    ("north", "west"): 135.0,
    ("south", "west"): 225.0,
    ("south", "east"): 315.0,
}
# "due North", "northward", "to the north", "west"; "northerly" as ``_BETWEEN`` reads it.
_COMPASS = re.compile(rf"\b{_LEAD}(north|south|east|west)(?:wards?|bound|(erly))?\b", re.I)
# A wind or a current named for where it comes from: "from the west", "a north wind".
_FROM = re.compile(r"\bfrom\s+(?:the\s+)?(?:due\s+)?$", re.I)
_WIND = re.compile(r"\s*(?:winds?|breezes?|gales?)\b", re.I)
# What an "-erly" names: a body's own way ("in a westerly direction", "on a southerly
# course"), else a wind's source ("a westerly wind"); with neither word it is unread.
_ERLY_WAY = re.compile(r"\s*(?:direction|course|heading|route|path|bearing)\b", re.I)
_SCREEN = re.compile(
    r"\b(?:to(?:wards)?\s+the\s+(right|left)|(right|left)wards?|(up|down)wards?"
    r"|(?:vertically|straight)\s+(up|down)(?:wards?)?)\b",
    re.I,
)
# A bare side after a verb of motion: "a ball moving left at 3 m/s", "rolls right".
_MOVES_SIDE = re.compile(
    r"\b(?:mov(?:e|es|ed|ing)|travel(?:s|led|ling|ed|ing)?|roll(?:s|ed|ing)?|go(?:es|ing)?"
    r"|head(?:s|ed|ing)?|slid(?:e|es|ing)|run(?:s|ning)?|drift(?:s|ed|ing)?|fl(?:y|ies|ying)"
    r"|swim(?:s|ming)?|walk(?:s|ed|ing)?|driv(?:e|es|ing)|push(?:es|ed)?|pull(?:s|ed)?)"
    r"\s+(left|right)(?:wards?)?\b",
    re.I,
)
_SCREEN_ANGLES = {"right": 0.0, "up": 90.0, "left": 180.0, "down": 270.0}
_SIDES = frozenset({"left", "right"})
# A right angle the question states between two arrows.
_RIGHT_ANGLE = re.compile(r"\bright[\s-]angles?\b|\bperpendicular\b", re.I)
# A description's arrow turned from an earlier one: "90° to F1", "at right angles to Car A".
_RELATIVE = re.compile(
    rf"^(?:at\s+)?(?:{_NUMBER}|(right\s+angles?|perpendicular))\s+(?:to|from)\s+(.+)$", re.I
)
# Where a clause ends inside a sentence: a comma, a semicolon, a joining word.
_CLAUSE = re.compile(r"[,;:]|\b(?:and|while|whilst|whereas|but|then)\b", re.I)
# Where a sentence ends: a stop not inside a number, or a blank line. A single line break is
# a pasted question's hard wrap, inside its sentence.
_SENTENCE = re.compile(r"[.?!](?!\d)|\n\s*\n")
_RESPECTIVELY = re.compile(r"\brespectively\b", re.I)
# Words a description's direction may carry beside it: "a wind from the west", "a gale from
# the north", "blowing from the east".
_SPARE_WORDS = r"\b(?:an?|from|the|winds?|breezes?|gales?|blowing|blows)\b"


@dataclass(frozen=True)
class Mention:
    """One direction the question writes: the angle it points, where it is, and whether it
    names a compass point (north is up) or a side of the page (right, up)."""

    angle: float
    start: int
    end: int
    compass: bool
    # "side" (left, right), "elevation" (an angle above or below the horizontal, to the right
    # unless a side in its clause says left), or "other".
    form: str = "other"
    # False for a direction the grammar cannot read for sure ("a westerly", "north-north-
    # east", two ways for one value): an arrow of its value is never drawn.
    readable: bool = True


@dataclass(frozen=True)
class Relative:
    """A description's arrow at ``angle`` degrees to the earlier arrow named ``to``."""

    angle: float
    to: str


def _turned(base: str, toward: str, by: float) -> float | None:
    start, end = _POINTS[base.lower()], _POINTS[toward.lower()]
    step = (end - start + 180.0) % 360.0 - 180.0
    if abs(abs(step) - 90.0) > 1e-9 or not 0.0 <= by <= 90.0:
        return None  # "30° north of south" names no turn
    return (start + math.copysign(by, step)) % 360.0


def _comes_from(text: str, match: re.Match[str]) -> bool:
    """The direction names where a wind or a current comes from, so it points the other way:
    "from the west", "a west wind", "a north-easterly wind"."""
    before = text[max(0, match.start() - 16) : match.start()]
    return _FROM.search(before) is not None or _WIND.match(text, match.end()) is not None


def _erly(text: str, match: re.Match[str]) -> bool | None:
    """An "-erly": True when it names a wind's source ("a westerly wind", "from a northerly
    direction" is no wind and reads as the way), False when a body's own way ("in a westerly
    direction"), None when its words say neither ("a westerly at 12 km/h")."""
    if _ERLY_WAY.match(text, match.end()):
        return False
    if _WIND.match(text, match.end()):
        return True
    return None


def _found(text: str) -> list[Mention]:
    """Every direction ``text`` writes, a longer form before the words inside it."""
    found: list[Mention] = []
    taken: list[tuple[int, int]] = []

    def add(
        angle: float | None,
        match: re.Match[str],
        compass: bool,
        erly: str | None = None,
        form: str = "other",
    ) -> None:
        if angle is None or any(
            match.start() < end and start < match.end() for start, end in taken
        ):
            return
        readable = True
        way = _erly(text, match) if erly else None
        if erly and way is None:
            readable = False
        if way is True or (not erly and _comes_from(text, match)):
            angle += 180.0
        # "a north wind of 3 m/s": the wind's words are the mention's, so its value is the
        # one after them, not the boat's before.
        wind = _WIND.match(text, match.end())
        end = wind.end() if wind is not None else match.end()
        taken.append((match.start(), end))
        found.append(Mention(angle % 360.0, match.start(), end, compass, form, readable))

    for m in _COMPOUND.finditer(text):
        taken.append((m.start(), m.end()))
        found.append(Mention(0.0, m.start(), m.end(), True, readable=False))

    for m in _OF.finditer(text):
        add(_turned(m.group(3), m.group(2), float(m.group(1))), m, True)
    for m in _LETTERED.finditer(text):
        add(
            _turned(_LETTERS[m.group(1).lower()], _LETTERS[m.group(3).lower()], float(m.group(2))),
            m,
            True,
        )
    for m in _BEARING.finditer(text):
        add(90.0 - float(m.group(1)), m, True)
    for m in _HORIZONTAL.finditer(text):
        up = float(m.group(1)) if m.group(2).lower() == "above" else -float(m.group(1))
        add(180.0 - up if m.group(3) else up, m, False, form="other" if m.group(3) else "elevation")
    for m in _BETWEEN.finditer(text):
        add(_HALFWAY[(m.group(1).lower(), m.group(2).lower())], m, True, m.group(3))
    for m in _COMPASS.finditer(text):
        add(_POINTS[m.group(1).lower()], m, True, m.group(2))
    for m in _SCREEN.finditer(text):
        side = next(group for group in m.groups() if group).lower()
        add(_SCREEN_ANGLES[side], m, False, form="side" if side in _SIDES else "other")
    for m in _MOVES_SIDE.finditer(text):
        add(_SCREEN_ANGLES[m.group(1).lower()], m, False, form="side")
    return sorted(found, key=lambda mention: mention.start)


def writes_a_direction(text: str) -> bool:
    """``text`` writes any direction this grammar reads."""
    return bool(_found(text))


def _bounds(text: str, at: int, pattern: re.Pattern[str]) -> tuple[int, int]:
    start = max((m.end() for m in pattern.finditer(text, 0, at)), default=0)
    after = pattern.search(text, at)
    return start, after.start() if after is not None else len(text)


def sentence_at(text: str, at: int) -> tuple[int, int]:
    """Where the sentence holding ``at`` starts and ends."""
    return _bounds(text, at, _SENTENCE)


def clause_at(text: str, at: int) -> tuple[int, int]:
    """Where the clause holding ``at`` starts and ends, inside its sentence."""
    sentence = _bounds(text, at, _SENTENCE)
    clause = _bounds(text, at, _CLAUSE)
    return max(clause[0], sentence[0]), min(clause[1], sentence[1])


def _gap(start: int, end: int, given: Given, given_end: int) -> int:
    if given.start >= end:
        return given.start - end
    return max(0, start - given_end)


def owner(
    text: str, start: int, end: int, givens: Sequence[Given], ends: Sequence[int]
) -> Given | None:
    """The given that the words at ``start:end`` (a direction, a mass, a name) describe: the
    nearest in their clause, else in their sentence; None when their sentence has none."""
    sentence = _bounds(text, start, _SENTENCE)
    clause = _bounds(text, start, _CLAUSE)
    clause = (max(clause[0], sentence[0]), min(clause[1], sentence[1]))
    spans = list(zip(givens, ends, strict=True))
    for low, high in (clause, sentence):
        near = [(g, e) for g, e in spans if low <= g.start and e <= high]
        if near:
            return min(near, key=lambda pair: _gap(start, end, pair[0], pair[1]))[0]
    return None


def _respective(text: str, mentions: list[Mention], givens: Sequence[Given]) -> dict[int, Given]:
    """In a sentence that says "respectively", its directions paired with its values in
    order ("20 m/s and 16 m/s due north and due west respectively"), when they are as many:
    each direction's start to its value."""
    paired: dict[int, Given] = {}
    for found in _RESPECTIVELY.finditer(text):
        low, high = _bounds(text, found.start(), _SENTENCE)
        here = [m for m in mentions if low <= m.start < high]
        kinds: dict[str | None, list[Given]] = {}
        for given in sorted((g for g in givens if low <= g.start < high), key=lambda g: g.start):
            kinds.setdefault(given.dimension, []).append(given)
        # The one kind with as many values as the sentence has directions ("masses of 2 kg
        # and 3 kg move at 4 m/s and 1 m/s east and west respectively": the speeds).
        matching = [values for values in kinds.values() if len(values) == len(here) > 1]
        if len(matching) == 1:
            paired.update({m.start: g for m, g in zip(here, matching[0], strict=True)})
    return paired


def stated_headings(
    text: str, givens: Sequence[Given], ends: Sequence[int]
) -> dict[int, list[Mention]]:
    """The directions ``text`` gives each of ``givens`` (keyed by its start). ``ends`` is
    where each given's unit ends."""
    heads: dict[int, list[Mention]] = {}
    mentions = _found(text)
    respective = _respective(text, mentions, givens)
    for mention in mentions:
        given = respective.get(mention.start) or owner(
            text, mention.start, mention.end, givens, ends
        )
        if given is not None:
            heads.setdefault(given.start, []).append(mention)
    return {start: _one_way(found) for start, found in heads.items()}


def _one_way(mentions: list[Mention]) -> list[Mention]:
    """One value's directions as one heading: a side and an angle above or below the
    horizontal are one ("to the left with a force of 40 N at 30° above the horizontal" is
    150°); two that still disagree ("north ... east") leave the value unreadable."""
    sides = [m for m in mentions if m.form == "side"]
    rises = [m for m in mentions if m.form == "elevation"]
    if len(rises) == 1 and sides and len({m.angle for m in sides}) == 1:
        rise = rises[0]
        angle = (180.0 - rise.angle) % 360.0 if sides[0].angle == 180.0 else rise.angle
        rest = [m for m in mentions if m not in sides and m is not rise]
        mentions = [*rest, Mention(angle, rise.start, rise.end, False, "elevation")]
    if len({round(m.angle, 6) for m in mentions}) > 1 or not all(m.readable for m in mentions):
        first = mentions[0]
        return [Mention(first.angle, first.start, first.end, first.compass, readable=False)]
    return mentions


def read_heading(written: str) -> Mention | Relative | None:
    """A description's direction: an angle (counter-clockwise from east, or right), an angle
    to an earlier arrow, or None when it is no direction this grammar reads."""
    words = written.strip().strip(".")
    relative = _RELATIVE.match(words)
    if relative is not None:
        angle = 90.0 if relative.group(2) else float(relative.group(1))
        return Relative(angle, relative.group(3).strip()) if 0.0 < angle < 180.0 else None
    side = _SCREEN_ANGLES.get(words.lower())
    if side is not None:  # "left", "up": a side of the page, as a description writes it
        return Mention(side, 0, len(words), compass=False)
    found = _found(words)
    # The whole of it one direction: "due north", "30° east of north", "from the west",
    # never "north, then east".
    if len(found) != 1:
        return None
    spare = words[: found[0].start] + words[found[0].end :]
    leftover = re.sub(_SPARE_WORDS, "", spare, flags=re.I)
    if leftover.strip(" ,") or not found[0].readable:
        return None
    return found[0]


def states_angle(text: str, angle: float) -> bool:
    """The question states ``angle`` between arrows: as a number of degrees, or a right
    angle in words."""
    if math.isclose(angle, 90.0) and _RIGHT_ANGLE.search(text):
        return True
    return any(
        math.isclose(float(m.group(1)), angle) for m in re.finditer(_NUMBER, text, re.IGNORECASE)
    )
