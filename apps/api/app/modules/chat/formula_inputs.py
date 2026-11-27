# ruff: noqa: RUF001, RUF003 -- the module reads × as replies write it.
"""Which number a line of working puts in for each name of its formula.

"$\\omega = 2\\pi N$", then "$\\omega = 2\\pi \\times 250$": the second line is the first with N
written as 250. The two are lined up token by token; each name of the formula replaced by
one number is that name's input, and nothing else may differ. A formula with a number of
its own that may be a conversion (the 60 of "2\\pi N / 60", a 3.6, a 1000) gives no inputs: its
units are not the names' alone. Pure: no IO.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.modules.chat.working_check import NAME
from app.modules.chat.working_claims import plain_name

# A formula's own number that converts nothing: a small count or factor (2πr, ½mv²).
_PURE_FACTOR = 4
_BRACKETS = frozenset("()")
_TEX_TOKEN = re.compile(rf"{NAME.pattern}|\d+(?:\.\d+)?(?:e[-+]?\d+)?|\S")
# "1.087 \times 10^{-3}" is one number put in, as "1.087e-3".
_SCIENTIFIC = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:\\times|\\cdot|×)\s*10\s*\^\s*(?:\{\s*([-+−]?\d+)\s*\}|([-+−]?\d+))"
)
_NO_MATHS = frozenset({"\\times", "\\cdot", "*", "×", "\\,", "\\;", "\\left", "\\right"})


def aligned_names(formula: str, method: str) -> dict[str, str] | None:
    """Each name of ``formula`` with the number ``method`` puts in for it ("2\\pi N" and
    "2\\pi \\times 250" give N: 250); None when the two differ in any other way, or the
    formula holds a number of its own that may be a conversion (60, 3.6, 1000)."""
    left = _tokens(formula)
    right = _tokens(_SCIENTIFIC.sub(lambda m: f"{m[1]}e{(m[2] or m[3]).replace('−', '-')}", method))
    if not left or not right:
        return None
    found: dict[str, str] = {}
    matcher = SequenceMatcher(None, left, right, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            if not all(_pure(token) for token in left[i1:i2]):
                return None
            continue
        names = left[i1:i2]
        numbers = [piece for piece in right[j1:j2] if piece not in _BRACKETS]
        if tag != "replace" or len(names) != 1 or len(numbers) != 1:
            return None
        if not numbers[0][:1].isdigit() or NAME.fullmatch(names[0]) is None:
            return None
        found[plain_name(names[0])] = numbers[0]
    return found or None


def _tokens(tex: str) -> list[str]:
    return [token for token in _TEX_TOKEN.findall(tex) if token not in _NO_MATHS]


def _pure(token: str) -> bool:
    """A formula's own number that converts nothing: a small count or factor."""
    if not token[:1].isdigit():
        return True
    return float(token) <= _PURE_FACTOR and float(token) == int(float(token))
