# ruff: noqa: RUF001 -- the module reads the minus and times signs as a reply writes them.
"""The working's last line shows the card's rounding, as textbooks write it.

The working ends on its value unrounded and the card rounds it once (the owner's rule,
2026-11-13). A student reading ``t = 4.82488 s`` above a card of ``4.82 s`` saw two answers
(the owner's phone, 2026-11-23), so the line now ends on the rounding step:
``t = 4.82488 s ≈ 4.82 s``, the card unchanged. Every card, whoever wrote the working: a
subject's solver, the worked layout or the model.

A card pairs with the last maths above it, inline or display, with only blank lines and
bold headings between them (``working_cards.only_headings``). That line gets
``\\approx`` and the card's number, in the line's own unit and sign, only when it ends
``= <number> [unit]``, names what the card names (or nothing), and its number rounds to the
card's in the same unit (``card_numbers.rounding_of``, a power of ten's mantissa
included). A line already equal to the card, one already ending on ≈, one the card does
not round (a disagreement is another pass's), and a card the rule leaves as written
(several values, an expression, a sum of money, a pH: ``card_numbers.plain_numbers``) are
left as they are.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.modules.chat.card_numbers import (
    ROUNDED_TO,
    WRITTEN_NUMBER,
    line_value,
    plain_numbers,
    rounding_of,
)
from app.modules.chat.tex_arithmetic import INLINE_MATH
from app.modules.chat.working_cards import only_headings
from app.services.answer_check import Number, read_verified_value
from app.services.answer_fence import ANSWER_FENCE_LANGS
from app.services.md_fence_scan import iter_fences

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

_DISPLAY_MATH = re.compile(r"\$\$(?P<dollars>.+?)\$\$|\\\[(?P<brackets>.+?)\\\]", re.DOTALL)
# What may close the line after its maths: a full stop or a comma.
_CLOSING_MARK = re.compile(r"[ \t]*[.,]")
# What may stand before the line's number: its sign.
_SIGN = re.compile(r"[-−+]?\s*")


def round_working_ends(state: FinalizeState) -> str:
    return rounded_ends(state.text)


def rounded_ends(text: str) -> str:
    """``text`` with each card's working ending on the card's rounding (the docstring)."""
    changes: list[tuple[int, str]] = []
    previous = 0
    for fence in iter_fences(text):
        above_start, previous = previous, fence.end
        if not fence.closed or fence.lang not in ANSWER_FENCE_LANGS:
            continue
        card = _card(text[fence.body_start : fence.body_end])
        line = _last_maths(text[above_start : fence.start]) if card else None
        if card is None or line is None:
            continue
        start, end = line
        maths = text[above_start + start : above_start + end]
        approximation = _approximation(maths, *card)
        if approximation:
            changes.append((above_start + start + len(maths.rstrip()), approximation))
    for at, approximation in reversed(changes):
        text = text[:at] + approximation + text[at:]
    return text


def _card(body: str) -> tuple[Number, str, str | None] | None:
    """A card's one value: its number, the number as the card writes it, and its name."""
    plain = plain_numbers(body)
    if plain is None or len(plain[2].numbers) != 1:
        return None
    _headers, value, read = plain
    written = WRITTEN_NUMBER.search(value)
    if written is None or written.group("calculator") is not None:
        return None  # "1.77e-10" is a calculator's, not a line of maths
    return read.numbers[0], written.group(0).replace("×", "\\times "), read.label


def _last_maths(above: str) -> tuple[int, int] | None:
    """Where the last maths above a card is (its inside), when only blank lines and bold
    headings stand between it and the card."""
    spans = [
        (match.start(group), match.end(group), match.end())
        for match in _DISPLAY_MATH.finditer(above)
        for group in ("dollars", "brackets")
        if match.group(group) is not None
    ]
    # Display maths blanked, so its "$$" is never read as two inline lines.
    blanked = _DISPLAY_MATH.sub(lambda match: " " * len(match.group(0)), above)
    spans += [
        (match.start(1), match.end(1), match.end()) for match in INLINE_MATH.finditer(blanked)
    ]
    if not spans:
        return None
    start, end, outer_end = max(spans, key=lambda span: span[2])
    after = above[outer_end:]
    closing = _CLOSING_MARK.match(after)
    if not only_headings(after[closing.end() :] if closing else after):
        return None
    return start, end


def _approximation(maths: str, card: Number, shown: str, label: str | None) -> str | None:
    """`` \\approx <card's number>`` in the line's own sign and unit, or None to leave it."""
    side = maths.rpartition("=")[2].strip()
    if not side or ROUNDED_TO.search(side):
        return None
    worked = line_value(maths)
    if worked is None or worked.value == card.value or not rounding_of(card, worked):
        return None
    named = read_verified_value(maths)
    if label and named is not None and named.label and named.label != label:
        return None  # another quantity's line: v_y above a card of v_x
    number = WRITTEN_NUMBER.search(side)
    if number is None or not _SIGN.fullmatch(side[: number.start()]):
        return None  # a number inside a wrapper (\boxed{…}) is not the line's own end
    return f" \\approx {side[: number.start()]}{shown}{side[number.end() :]}"
