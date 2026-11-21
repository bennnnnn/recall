"""A picture under its own part: right after that part is answered.

Owner (2026-11-21): a question in parts that needs a picture for each part gets each one
right after the part it belongs to is answered, never every picture together at the end of
the reply. A part is found by its letter (or number): under its ``**Answer (b)**`` heading,
after that heading's card; else at the end of its own section (``**(b) …**`` up to the next
part, a ``---`` rule or the end). Headings inside a fence are not headings. A part the reply
does not have places nothing: its picture stays where it was.
"""

from __future__ import annotations

import json
import math
import re

from app.services.answer_fence import ANSWER_FENCE_LANGS
from app.services.md_fence_scan import Fence, block_end, iter_fences

# A part's letter or number as a reply writes it: "b", "(b)", "Part b", "2".
_KEY = re.compile(r"^(?:part\s*)?\(?([a-h]|[1-8])\)?$", re.IGNORECASE)
_ANY = r"(?:[a-h]|[1-8])"
_RULE = re.compile(r"^[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*$", re.MULTILINE)


def part_key(value: object) -> str | None:
    """A part's letter or number, lower case, from what a description or a list says."""
    if isinstance(value, bool) or not isinstance(value, str | int):
        return None
    match = _KEY.match(str(value).strip().rstrip(".:"))
    return match.group(1).lower() if match else None


def _answer_heading(key: str) -> re.Pattern[str]:
    return re.compile(
        rf"^[ \t]*(?:#{{1,4}}[ \t]*)?\*\*Answer[ \t]*\(?{key}\)?\*\*[ \t]*$",
        re.MULTILINE | re.IGNORECASE,
    )


# A part's own heading is bold or a markdown heading: a plain "(b) …" line is the Required
# list's, not where part (b) is worked.
_HEADING = r"^[ \t]*(?:[^\w\s*#]{1,3}[ \t]*)?(?:#{1,4}[ \t]*(?:\*\*)?|\*\*)[ \t]*"


def _part_heading(key: str) -> re.Pattern[str]:
    # "**(b) Area**", "### b) Area", "📐 **Part b: Area**".
    return re.compile(
        rf"{_HEADING}(?:Part[ \t]+\(?{key}\)?[ \t.:*]|\(?{key}\))", re.MULTILINE | re.IGNORECASE
    )


def _outside(fences: list[Fence], at: int) -> bool:
    return not any(fence.start <= at < fence.end for fence in fences)


def _first(pattern: re.Pattern[str], text: str, fences: list[Fence], start: int = 0) -> int:
    """Where ``pattern`` first matches outside a fence at or after ``start``, or -1."""
    for match in pattern.finditer(text, start):
        if _outside(fences, match.start()):
            return match.start()
    return -1


def _after_card(text: str, heading: int, fences: list[Fence]) -> int | None:
    """Past the answer card right under the heading at ``heading``, or None."""
    line_end = text.find("\n", heading)
    if line_end < 0:
        return None
    card = next((fence for fence in fences if fence.start > line_end), None)
    if card is None or card.lang not in ANSWER_FENCE_LANGS or text[line_end : card.start].strip():
        return None
    return block_end(text, card)


def _section_end(text: str, key: str, start: int, fences: list[Fence]) -> int:
    """The end of the part that starts at ``start``: the next other part, a rule, or the end."""
    line_end = text.find("\n", start)
    if line_end < 0:
        return len(text)
    others = re.compile(
        rf"{_HEADING}(?:(?:Part|Answer)[ \t]+\(?(?!{key}\b){_ANY}\b|\(?(?!{key}\)){_ANY}\))",
        re.MULTILINE | re.IGNORECASE,
    )
    ends = [
        at
        for at in (_first(others, text, fences, line_end), _first(_RULE, text, fences, line_end))
        if at >= 0
    ]
    return min(ends) if ends else len(text)


def place_after_part(text: str, key: str, picture: str) -> str | None:
    """``text`` with ``picture`` right after part ``key`` is answered; None when the reply
    has no such part."""
    fences = list(iter_fences(text))
    at: int | None = None
    heading = _first(_answer_heading(key), text, fences)
    if heading >= 0:
        at = _after_card(text, heading, fences)
    if at is None:
        start = heading if heading >= 0 else _first(_part_heading(key), text, fences)
        if start < 0:
            return None
        at = _section_end(text, key, start, fences)
    before, after = text[:at].rstrip(), text[at:].lstrip("\n")
    middle = f"\n\n{picture.strip()}\n"
    return f"{before}{middle}\n{after}" if after.strip() else f"{before}{middle}"


# Pictures the server draws under a reply.
_PICTURE_LANGS = frozenset({"geometry", "graph", "simulation", "chart", "molecule3d", "smiles"})
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")
# A sampled path (a trajectory's points, a curve's samples) is no value the question states.
_SAMPLES = 4


def _picture_numbers(node: object) -> list[float]:
    """The values a picture states: its numbers and the numbers in its labels, never a path."""
    if isinstance(node, bool):
        return []
    if isinstance(node, int | float):
        return [float(node)]
    if isinstance(node, str):
        return [float(number) for number in _NUMBER.findall(node)]
    if isinstance(node, dict):
        return [value for child in node.values() for value in _picture_numbers(child)]
    if isinstance(node, list) and len(node) <= _SAMPLES:
        return [value for child in node for value in _picture_numbers(child)]
    return []


def _part_of_picture(body: str, parts: dict[str, str]) -> str | None:
    """The one lettered part of the question whose own numbers the picture states the most."""
    try:
        stated = _picture_numbers(json.loads(body))
    except ValueError:
        return None
    holding = {
        label: sum(
            1
            for number in {float(n) for n in _NUMBER.findall(words)}
            if any(math.isclose(number, value, rel_tol=1e-9) for value in stated)
        )
        for label, words in parts.items()
    }
    best = max(holding.values(), default=0)
    winners = [label for label, count in holding.items() if count == best]
    return part_key(winners[0]) if best and len(winners) == 1 else None


def pictures_follow_parts(text: str, parts: dict[str, str]) -> str:
    """Each picture under the reply that one lettered part of the question holds the values of,
    moved right after that part is answered (owner, 2026-11-21); a picture several parts share,
    or one already inside its part, stays where it is. ``parts``: the question's part words by
    label."""
    if len(parts) < 2:
        return text
    for fence in reversed(list(iter_fences(text))):
        if not fence.closed or fence.lang not in _PICTURE_LANGS:
            continue
        key = _part_of_picture(text[fence.body_start : fence.body_end], parts)
        if key is None:
            continue
        # Already inside its own part: where it would go is where it is.
        if _section_holds(text, key, fence.start):
            continue
        before, picture, after = (
            text[: fence.start],
            text[fence.start : fence.end],
            text[fence.end :],
        )
        rest = f"{before.rstrip()}\n\n{after.lstrip()}" if after.strip() else before.rstrip()
        if (moved := place_after_part(rest, key, picture)) is not None:
            text = moved
    return text


def _section_holds(text: str, key: str, at: int) -> bool:
    """``at`` lies inside part ``key``'s own section."""
    fences = list(iter_fences(text))
    start = _first(_part_heading(key), text, fences)
    if start < 0:
        start = _first(_answer_heading(key), text, fences)
    return start >= 0 and start <= at < _section_end(text, key, start, fences)
