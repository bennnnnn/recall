"""An answer card holds the answer; what is said about it goes in a sentence under it.

"v = √(10gh/7) m/s (about 1.20sqrt{gh}; option A gives sqrt{2gh}, which is the
sliding-block result with no rotation)" filled the card (live, 2026-11-06): the line under
**Answer** went in whole. The card keeps the value's maths and a unit written straight
after it ("$x = 3$ m/s") and a short label in brackets ("(east)"); the words after that,
a note, a comparison or a reason, go in a sentence directly under the card. A line that
opens with words ("The ball lands at …") is an answer in a sentence, and stays as it was.
"""

from __future__ import annotations

import re

_MATH_SPAN = re.compile(r"\$\$.*?\$\$|\$[^$\n]*\$|\\\(.*?\\\)", re.DOTALL)
_WORD = re.compile(r"[^\W\d_]{3,}")
# One word written straight after the maths, alone or before a clause mark, stays on the
# card: it is the unit ("m/s", "°C", "meters/second") or what is counted ("12 students",
# "5 birr"). A one-word qualifier ("approximately") stays with it, harmless there; read
# through the unit table, "students" would have gone under the card (review of #2303).
_UNIT = re.compile(r"[^\s,;:()\u2014\u2013]+(?=\s*(?:$|[,;:(\u2014\u2013]))")
# The marks that open what is said about the value: ", since …", "; option A …", "— so …".
_LEAD = re.compile(r"^[\s,;:.\u2014\u2013-]+")
# A bracketed label this short stays on the card: "(east)", "(to 3 s.f.)".
_LABEL_WORDS = 3
# What may stand between two values the card keeps: marks, or one bare "and", "or" or
# "then" ("$x = 3$ and $y = 4$", review of #2303).
_JOINS = re.compile(r"[\s,;]*(?:(?:and|or|then)\b[\s,;]*)?", re.IGNORECASE)
_WRAPPED = re.compile(r"^\((?P<inner>[^()]*(?:\([^()]*\)[^()]*)*)\)\.?$")


# A unit of several words ("square meters", "miles per hour") is one the unit table reads;
# "so it works" is not (review of #2303).
_UNIT_WORDS = re.compile(r"(?:[^\W\d_]+\s+){1,3}[^\W\d_]+(?=\s*(?:$|[,;:(\u2014\u2013]))")


def _unit_end(text: str) -> int:
    """Where the unit written straight after the maths ends in ``text``, or 0 for none."""
    words = _UNIT_WORDS.match(text)
    if words is not None and _reads_as_unit(words.group()):
        return words.end()
    unit = _UNIT.match(text)
    return unit.end() if unit is not None else 0


def _reads_as_unit(words: str) -> bool:
    from pint.errors import PintError

    from app.services.units import get_unit_registry

    try:
        quantity = get_unit_registry()(words.replace(" per ", "/"))
    except (PintError, ValueError, TypeError, AttributeError, SyntaxError):
        return False  # not a unit the table knows: the words are a remark
    return not getattr(quantity, "dimensionless", True)


def split_tail(value: str) -> tuple[str, str]:
    """``value`` as the card's maths and the sentence to go under the card ("" for none)."""
    spans = list(_MATH_SPAN.finditer(value))
    if not spans or _WORD.search(value[: spans[0].start()]):
        return value, ""  # no maths, or words before it: an answer written as a sentence
    # The maths the value opens with, its spans joined by marks or a bare "and" ("$x = 2$,
    # $x = -2$"); maths inside what follows ("about $1.20\sqrt{gh}$") belongs to the sentence.
    end = spans[0].end()
    for span in spans[1:]:
        if not _JOINS.fullmatch(value[end : span.start()]):
            break
        end = span.end()
    rest = value[end:]
    unit_end = _unit_end(rest.lstrip())
    if unit_end:
        end += len(rest) - len(rest.lstrip()) + unit_end
        rest = value[end:]
    said = _LEAD.sub("", rest).strip()
    wrapped = _WRAPPED.match(said)
    if wrapped is not None:
        said = wrapped.group("inner").strip()
        if len(said.split()) <= _LABEL_WORDS and "$" not in said:
            return value, ""  # a label of the value ("east", "to 3 s.f."), not a remark
    if not _WORD.search(said):
        return value, ""
    sentence = said[0].upper() + said[1:]
    return value[:end].rstrip(" ,;:"), sentence if sentence[-1] in ".!?" else f"{sentence}."
