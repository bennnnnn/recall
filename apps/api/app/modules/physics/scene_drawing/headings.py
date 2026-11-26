"""The directions a question states, each read as an angle and tied to the value it goes with.

A vector picture's arrows point where the question says: "20 m/s due North", "16 m/s to the
left", "12 m/s on a heading 30° east of north", "a force of 20 N at 30° above the
horizontal", "a bearing of 060°". Each direction the question writes is read as an angle
(degrees counter-clockwise from east, which is also "to the right"; north is up) and given
to the stated quantity it describes: the nearest one in its own clause ("Car B travels due
West along the other road at 16 m/s"), else in its sentence ("swims due north at 1.5 m/s
across a river flowing due east at 2 m/s" gives north to 1.5 m/s and east to 2 m/s). A
direction a description names for an arrow is drawn only when it is one the question gives
that arrow's value (``vectors``). A description's own direction is read by the same grammar
(``read_heading``), and may also name an angle to an earlier arrow ("90° to F1"), which the
question must state ("at right angles", "perpendicular", "90°").
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
# "north-east", "northwest": halfway between two points.
_BETWEEN = re.compile(r"\b(north|south)[\s-]?(east|west)(?:wards?|ern|erly)?\b", re.I)
_HALFWAY = {
    ("north", "east"): 45.0,
    ("north", "west"): 135.0,
    ("south", "west"): 225.0,
    ("south", "east"): 315.0,
}
# "due North", "northward", "to the north", "west".
_COMPASS = re.compile(r"\b(?:due\s+)?(north|south|east|west)(?:wards?|bound)?\b", re.I)
_SCREEN = re.compile(
    r"\b(?:to(?:wards)?\s+the\s+(right|left)|(right|left)wards?|(up|down)wards?"
    r"|(?:vertically|straight)\s+(up|down)(?:wards?)?)\b",
    re.I,
)
_SCREEN_ANGLES = {"right": 0.0, "up": 90.0, "left": 180.0, "down": 270.0}
# A right angle the question states between two arrows.
_RIGHT_ANGLE = re.compile(r"\bright[\s-]angles?\b|\bperpendicular\b", re.I)
# A description's arrow turned from an earlier one: "90° to F1", "at right angles to Car A".
_RELATIVE = re.compile(
    rf"^(?:at\s+)?(?:{_NUMBER}|(right\s+angles?|perpendicular))\s+(?:to|from)\s+(.+)$", re.I
)
# Where a clause ends inside a sentence: a comma, a semicolon, a joining word.
_CLAUSE = re.compile(r"[,;:]|\b(?:and|while|whilst|whereas|but|then)\b", re.I)
_SENTENCE = re.compile(r"[.?!](?!\d)|\n")


@dataclass(frozen=True)
class Mention:
    """One direction the question writes: its angle, where it is, and whether it names a
    compass point (north is up) or a side of the page (right, up)."""

    angle: float
    start: int
    end: int
    compass: bool


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


def _found(text: str) -> list[Mention]:
    """Every direction ``text`` writes, a longer form before the words inside it."""
    found: list[Mention] = []
    taken: list[tuple[int, int]] = []

    def add(angle: float | None, match: re.Match[str], compass: bool) -> None:
        if angle is None or any(
            match.start() < end and start < match.end() for start, end in taken
        ):
            return
        taken.append((match.start(), match.end()))
        found.append(Mention(angle % 360.0, match.start(), match.end(), compass))

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
        add(180.0 - up if m.group(3) else up, m, False)
    for m in _BETWEEN.finditer(text):
        add(_HALFWAY[(m.group(1).lower(), m.group(2).lower())], m, True)
    for m in _COMPASS.finditer(text):
        add(_POINTS[m.group(1).lower()], m, True)
    for m in _SCREEN.finditer(text):
        side = next(group for group in m.groups() if group)
        add(_SCREEN_ANGLES[side.lower()], m, False)
    return sorted(found, key=lambda mention: mention.start)


def _bounds(text: str, at: int, pattern: re.Pattern[str]) -> tuple[int, int]:
    start = max((m.end() for m in pattern.finditer(text, 0, at)), default=0)
    after = pattern.search(text, at)
    return start, after.start() if after is not None else len(text)


def _gap(mention: Mention, given: Given, text_end: int) -> int:
    if given.start >= mention.end:
        return given.start - mention.end
    return max(0, mention.start - text_end)


def stated_headings(
    text: str, givens: Sequence[Given], ends: Sequence[int]
) -> dict[int, list[Mention]]:
    """The directions ``text`` gives each of ``givens`` (keyed by its start), each the
    nearest value in the direction's clause, else in its sentence. ``ends`` is where each
    given's unit ends."""
    heads: dict[int, list[Mention]] = {}
    spans = list(zip(givens, ends, strict=True))
    for mention in _found(text):
        sentence = _bounds(text, mention.start, _SENTENCE)
        clause = _bounds(text, mention.start, _CLAUSE)
        clause = (max(clause[0], sentence[0]), min(clause[1], sentence[1]))
        for low, high in (clause, sentence):
            near = [(g, end) for g, end in spans if low <= g.start and end <= high]
            if near:
                given, _end = min(near, key=lambda pair: _gap(mention, pair[0], pair[1]))
                heads.setdefault(given.start, []).append(mention)
                break
    return heads


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
    # The whole of it one direction: "due north", "30° east of north", never "north, then".
    if len(found) != 1 or found[0].end - found[0].start < len(words) - 1:
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
