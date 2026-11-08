"""``a mod b`` and ``a^e mod b``, read only as a whole expression.

Reading the digits beside `` mod `` alone verified a part as the whole: ``10 mod 3 + 1`` as
10 mod 3 = 1, ``2^10 mod 7`` as 10 mod 7 = 3. A sign beside the expression makes it one
term of a longer sum, which no number-theory intent can carry, so it is left unread.
"""

from __future__ import annotations

_MOD = " mod "
# Also the minus, times, divide and middle-dot glyphs (U+2212, U+00D7, U+00F7, U+00B7).
_ARITHMETIC_SIGNS = frozenset("+-\u2212*/^\u00d7\u00f7\u00b7!")
_POWER_MARKS = ("**", "^")
# ``a^e mod m`` is worked by modular exponentiation: the power itself is never built.
_MAX_MOD_BASE = 100_000_000
_MAX_MOD_EXPONENT = 1_000_000


def _number_before(text: str, end: int) -> tuple[int, int] | None:
    """The whole number ending at ``end`` and where it starts; none after a point or sign."""
    start = end
    while start > 0 and text[start - 1].isdecimal():
        start -= 1
    if start == end or (start > 0 and text[start - 1] in ".-/"):
        return None
    return int(text[start:end]), start


def _number_after(text: str, start: int) -> tuple[int, int] | None:
    """The whole number starting at ``start`` and the index past it; not a fraction or decimal."""
    end = start
    while end < len(text) and text[end].isdecimal():
        end += 1
    if end == start:
        return None
    following = text[end : end + 2]
    if following[:1] == "/" or (following[:1] == "." and following[1:].isdecimal()):
        return None
    return int(text[start:end]), end


def _stands_alone(text: str, start: int, end: int) -> bool:
    """``10 mod 3`` itself, not one term of ``10 mod 3 + 1`` or ``2 + 10 mod 3``."""
    before = text[:start].rstrip()
    after = text[end:].lstrip()
    return not (before and before[-1] in _ARITHMETIC_SIGNS) and not (
        after and after[0] in _ARITHMETIC_SIGNS
    )


def _operands(text: str) -> tuple[tuple[int, int], tuple[int, int]] | None:
    """The numbers either side of the first `` mod ``, each with where it starts or ends."""
    at = text.lower().find(_MOD)
    if at == -1:
        return None
    left = _number_before(text, at)
    right = _number_after(text, at + len(_MOD))
    return (left, right) if left is not None and right is not None else None


def mod_signal(text: str) -> tuple[int, int] | None:
    """``17 mod 5`` → (17, 5)."""
    operands = _operands(text)
    if operands is None:
        return None
    (a, a_start), (b, b_end) = operands
    return (a, b) if _stands_alone(text, a_start, b_end) else None


def power_mod_signal(text: str) -> tuple[int, int, int] | None:
    """``2^100 mod 7`` → (2, 100, 7): a whole power of a whole number, mod a whole number."""
    operands = _operands(text)
    if operands is None:
        return None
    (exponent, exponent_start), (modulus, modulus_end) = operands
    head = text[:exponent_start].rstrip()
    mark = next((mark for mark in _POWER_MARKS if head.endswith(mark)), None)
    base = _number_before(head, len(head) - len(mark)) if mark else None
    if base is None or modulus == 0 or not _stands_alone(text, base[1], modulus_end):
        return None
    if base[0] > _MAX_MOD_BASE or exponent > _MAX_MOD_EXPONENT:
        return None
    return base[0], exponent, modulus
