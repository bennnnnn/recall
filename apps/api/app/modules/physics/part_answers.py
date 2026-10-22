"""A question in parts: each part's verified card under that part's own Answer heading.

One card holding every value ("v = 10 m/s; s = 25 m") under the last part's heading read
as that part's answer. When the reply answers part by part (``**Answer (a)**``,
``**Answer (b)**``) and the server solved the same parts, each heading gets its own
card, and the value lines a model wrote under it go: the card states them.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.services.answer_fence import verified_answer_fence

_PART_ANSWER = re.compile(r"^\s*(?:#{1,4}\s+)?\*\*Answer \((?P<letter>[a-h])\):?\*\*:?\s*$")
# A line that only restates a value: maths, "t = 2.04 s", "Answer: 2.04 s".
_RESTATED = re.compile(
    r"^\s*(?:\$[^$]+\$|\\\(.+\\\)|[A-Za-z_\\{}' ]{1,20}\s*[=≈].{0,60}|(?:\*\*)?answer\s*:.*)$",
    re.IGNORECASE,
)


def land_part_cards(text: str, cards: Sequence[str]) -> str | None:
    """``text`` with each part's card under its Answer heading; None when its part answers
    are not the parts the server solved, one for one and in order."""
    lines = text.split("\n")
    found = [
        (number, match.group("letter"))
        for number, line in enumerate(lines)
        if (match := _PART_ANSWER.match(line)) is not None
    ]
    if [letter for _, letter in found] != list("abcdefgh"[: len(cards)]) or len(cards) < 2:
        return None
    headings = [number for number, _ in found]
    out: list[str] = []
    number = 0
    while number < len(lines):
        line = lines[number]
        number += 1
        if number - 1 not in headings:
            out.append(line)
            continue
        card = cards[headings.index(number - 1)]
        while number < len(lines) and (not lines[number].strip() or _RESTATED.match(lines[number])):
            number += 1
        out.extend([line.strip(), "", verified_answer_fence(card)])
        if number < len(lines):
            out.append("")
    return "\n".join(out)
