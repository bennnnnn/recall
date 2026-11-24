"""Which piece of a line the next line worked out: the two sides lined up token by token.

"t = \\frac{14.339 + \\sqrt{205.6 + 882.9}}{9.81}" then "t = \\frac{14.339 + 33.11}{9.81}": the
second line is the first with one piece, the root, written as the number 33.11. Held as two
whole sides, the lines differ by 0.25%, inside the 1% a rounding chain may drift; held piece
by piece, the root is 32.99 and 33.11 is a slip (live, 2026-11-23). Each piece is judged on
its own, and the wrong number is the one to put right.

The pieces must be the line's own sub-expressions: the second line, with each number put
back to its piece's exact value, must equal the first. "2 \\times 3 + 4" then "2 \\times 7"
lines up "3 + 4" with 7, but 2 * 7 is not 2 * 3 + 4, so no pieces are read and the two
sides are held whole.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.modules.chat.tex_arithmetic import evaluate, plain_arithmetic

# A TeX token: a command, a number (its thousands commas with it), or one character.
_TOKEN = re.compile(r"\\[A-Za-z]+|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\\.|\S")
# Spacing and sizing that are no part of the maths.
_SPACING = frozenset({"\\,", "\\;", "\\:", "\\!", "\\ ", "\\left", "\\right", "\\quad"})
# A number a piece is written as: 33.11, -1.9, 1,224.7.
NUMBER = re.compile(r"-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
_BRACKETS = {"(": ")", "{": "}", "[": "]"}


@dataclass(frozen=True)
class Piece:
    """A piece of the earlier side (``tex``) the later side writes as ``number``, at
    ``start:end`` in the later side."""

    tex: str
    number: str
    start: int
    end: int
    value: float


def pieces(left_tex: str, right_tex: str) -> list[Piece] | None:
    """The pieces of ``left_tex`` that ``right_tex`` writes as numbers, everything else the
    same token for token; None when the sides differ in any other way, or the pieces are not
    the left side's own sub-expressions (the module docstring)."""
    left, right = _tokens(left_tex), _tokens(right_tex)
    if not left or not right:
        return None
    matcher = SequenceMatcher(None, [t[0] for t in left], [t[0] for t in right], autojunk=False)
    found: list[Piece] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag != "replace":
            return None
        tex = left_tex[left[i1][1] : left[i2 - 1][2]]
        start, end = right[j1][1], right[j2 - 1][2]
        number = right_tex[start:end]
        plain = plain_arithmetic(tex)
        value = evaluate(plain) if plain is not None and _balanced(tex) else None
        if value is None or NUMBER.fullmatch(number.replace(" ", "")) is None:
            return None
        found.append(Piece(tex, number, start, end, value))
    return found if found and _faithful(left_tex, right_tex, found) else None


def _faithful(left_tex: str, right_tex: str, found: list[Piece]) -> bool:
    """The later side with each number put back to its piece's value is the earlier side."""
    rebuilt = right_tex
    for piece in reversed(found):
        rebuilt = f"{rebuilt[: piece.start]}({piece.value!r}){rebuilt[piece.end :]}"
    whole, again = plain_arithmetic(left_tex), plain_arithmetic(rebuilt)
    first = evaluate(whole) if whole is not None else None
    second = evaluate(again) if again is not None else None
    return (
        first is not None
        and second is not None
        and math.isclose(first, second, rel_tol=1e-9, abs_tol=1e-12)
    )


def _tokens(tex: str) -> list[tuple[str, int, int]]:
    return [
        (match.group(0), match.start(), match.end())
        for match in _TOKEN.finditer(tex)
        if match.group(0) not in _SPACING
    ]


def _balanced(tex: str) -> bool:
    """Every bracket the piece opens it closes, in order."""
    stack: list[str] = []
    for char in tex:
        if char in _BRACKETS:
            stack.append(_BRACKETS[char])
        elif char in _BRACKETS.values() and (not stack or stack.pop() != char):
            return False
    return not stack
