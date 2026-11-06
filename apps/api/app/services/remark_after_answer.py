"""An answer card holds the answer; what is said about it goes in a sentence under it.

"v = √(10gh/7) m/s (about 1.20sqrt{gh}; option A gives sqrt{2gh}, which is the
sliding-block result with no rotation)" filled the card (live, 2026-11-06): the line under
**Answer** went in whole. The card keeps the value up to its first clause break: a clause
mark (";", ",", a dash, a full stop, a long bracket) or a word that opens a clause
("since", "so", "which"). What the value is written with stays on it, whatever the words:
a unit ("m/s", "meters per second"), what is counted ("12 students"), a direction ("north",
"above the horizontal"), a short label in brackets ("(east)"), another value ("and
$y = 4$"). A line that opens with words ("The ball lands at …") is an answer in a
sentence, and stays as it was.

Reviews of #2303 found units and directions cut off one case at a time while the card
tried to recognise units; it now recognises the breaks instead, which are few.
"""

from __future__ import annotations

import re

# An escaped dollar inside maths ("$M = \\$1{,}073.64$") does not close it.
_MATH_SPAN = re.compile(r"\$\$.*?\$\$|\$(?:\\.|[^$\\\n])*\$|\\\(.*?\\\)|\\\[.*?\\\]", re.DOTALL)
_WORD = re.compile(r"[^\W\d_]{3,}")
# A value written without maths marks: "v = 4 m/s", "x ≈ 3", "Speed = 4 m/s".
_BARE_START = re.compile(r"\s*[^\W\d_]+(?:_\{?\w+\}?)?\s*[=\u2248]")
# Where a remark may begin: a clause mark, a bracket (a short label is skipped), or a word
# that opens a clause. "1,073.64", "3:30" and ", 30° north of east" go on with the value,
# and so do "as well as" and a range: an en dash written straight onto the next value.
_BREAK = re.compile(
    r"[;\u2014]|\u2013(?![\d$\\])|,(?!\s*\d)|:(?!\d)|\s-\s|\.(?=\s|$)|\("
    r"|\b(?:(?<!well\s)as(?!\s+well\s+as\b))\b"
    r"|\b(?:since|because|so|which|while|whereas|but|though|although|meaning|giving"
    r"|hence|thus|therefore|compared|unlike)\b",
    re.IGNORECASE,
)
_BRACKET = re.compile(r"\((?:[^()]|\([^()]*\))*\)")
# A bracket this short stays on the card: "(east)", "(to 3 s.f.)".
_LABEL_WORDS = 3
# What may stand between a comma and the next value: "$x = 2$, $x = -2$", ", or $x = 5$".
_JOIN = re.compile(r"\s*(?:(?:and|or|then)\s+)?", re.IGNORECASE)
# A connective left before a break goes with the remark: "$x = 3$ and so $y = 4$".
_TRAILING_JOIN = re.compile(r"\s+(?:and|or|then)\s*$", re.IGNORECASE)
_LEAD = re.compile(r"^[\s,;:.\u2014\u2013-]+")
_WRAPPED = re.compile(r"^\((?P<inner>[^()]*(?:\([^()]*\)[^()]*)*)\)\.?$")


def split_tail(value: str) -> tuple[str, str]:
    """``value`` as the card's text and the sentence to go under the card ("" for none)."""
    spans = list(_MATH_SPAN.finditer(value))
    if spans and not _WORD.search(value[: spans[0].start()]):
        start = spans[0].end()
    else:
        bare = _BARE_START.match(value)
        if bare is None:
            return value, ""  # no maths, or words before it: an answer written as a sentence
        start = bare.end()
    at = _break(value, start, spans)
    if at is None:
        return value, ""
    trailing = _TRAILING_JOIN.search(value[:at])
    if trailing is not None:
        at = trailing.start()
    said = _LEAD.sub("", value[at:]).strip()
    wrapped = _WRAPPED.match(said)
    if wrapped is not None:
        said = wrapped.group("inner").strip()
    if not _WORD.search(said):
        return value, ""  # a closing stop or a mark, not a remark
    sentence = said[0].upper() + said[1:]
    return value[:at].rstrip(" ,;:"), sentence if sentence[-1] in ".!?" else f"{sentence}."


def _break(value: str, pos: int, spans: list[re.Match[str]]) -> int | None:
    """Where the first remark in ``value`` after ``pos`` begins, or None for none."""
    while (found := _BREAK.search(value, pos)) is not None:
        inside = next((s for s in spans if s.start() <= found.start() < s.end()), None)
        if inside is not None:
            pos = inside.end()
            continue
        if found.group() == "(":
            bracket = _BRACKET.match(value, found.start())
            inner = bracket.group()[1:-1] if bracket is not None else ""
            if bracket is not None and len(inner.split()) <= _LABEL_WORDS and "$" not in inner:
                pos = bracket.end()
                continue
        elif found.group() == ",":
            joined = _JOIN.match(value, found.end())
            after = joined.end() if joined is not None else found.end()
            following = next((s for s in spans if s.start() == after), None)
            if following is not None:
                pos = following.end()
                continue
            # Another value written without maths marks: "x = 2, x = -2" (review of #2303).
            bare = _BARE_START.match(value, after)
            if bare is not None:
                pos = bare.end()
                continue
        return found.start()
    return None
