# ruff: noqa: RUF001, RUF002, RUF003 -- the module reads × and − as a card writes them.
"""Every answer card's number shown by the one rule (``services.rounding_rule``), whoever
wrote the card: a subject's solver, the worked layout, the formal check or the model.

A card that states plain values (``P = 109324.04\\,\\mathrm{Pa}``, ``x = 2 or x = -3``,
``1.09 \\times 10^{5}\\,\\mathrm{Pa}``) has each number written again by the rule, in the
precision the question asks for. A card holding one value the working above it reached
unrounded (the working's last line, the card's value a rounding of it, in the same unit)
shows the working's value rounded once: the model's own "3 significant figures" made
109324.04 Pa a card of 1.09 × 10⁵ (the owner's chat, 2026-11-18). An expression, a fraction,
a sum of money and a pH are left as written: a pH keeps the decimals its concentration's
figures give it, the one place a chemistry answer's precision is its correctness.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.services.answer_check import Number, read_verified_value
from app.services.answer_fence import (
    ANSWER_FENCE_LANGS,
    CHEMISTRY_NOTATION_LINE,
    answer_header_and_value,
)
from app.services.md_fence_scan import iter_fences
from app.services.rounding_rule import (
    RULE,
    Precision,
    asked_precision,
    number_latex,
    number_parts,
)
from app.services.school_rounding import round_places

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

# A number the card writes, its power of ten with it; never a script's (m^{2}) or a
# fraction's part (\frac{1}{2}), nor a digit inside a word.
_WRITTEN = re.compile(
    r"(?<![\^_{\w.,])(?P<number>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:\s*(?:\\times|\\cdot|×)\s*10\s*\^\s*(?:\{\s*(?P<braced>[-+−]?\d+)\s*\}|(?P<bare>[-+]?\d)))?"
    r"(?![\w.])"
)
# Left as written: money, a decimal comma, a pH, pOH or pK.
_KEPT = re.compile(r"\\\$|[€£¥]|\{,\}|\bp(?:H|OH|K[ab]?)\b")
_INLINE_MATHS = re.compile(r"\$([^$\n]+)\$")


def format_card_numbers(state: FinalizeState) -> str:
    """The reply with each card's numbers by the rule (the module docstring)."""
    precision = asked_precision(state.ctx.user_message_content or "")
    return card_numbers(state.text, precision)


def card_numbers(text: str, precision: Precision) -> str:
    changes: list[tuple[int, int, str]] = []
    previous = 0
    for fence in iter_fences(text):
        if not fence.closed or fence.lang not in ANSWER_FENCE_LANGS:
            continue
        above, previous = text[previous : fence.start], fence.end
        body = text[fence.body_start : fence.body_end]
        shown = _shown(body, above, precision)
        if shown is not None and shown != body:
            changes.append((fence.body_start, fence.body_end, shown))
    for start, end, body in reversed(changes):
        text = text[:start] + body + text[end:]
    return text


def _shown(body: str, above: str, precision: Precision) -> str | None:
    """The card's body with its numbers by the rule, or None to leave it as written."""
    headers, value = answer_header_and_value(body)
    if not value or "\n" in value or CHEMISTRY_NOTATION_LINE in headers or _KEPT.search(value):
        return None
    read = read_verified_value(body)
    written = list(_WRITTEN.finditer(value))
    if read is None or len(written) != len(read.numbers):
        return None
    numbers = list(read.numbers)
    if any(number.places is None for number in numbers):
        return None  # an exact fraction
    if any(_money(number.unit) for number in numbers):
        return None  # a sum of money, to the cent as written
    worked = _unrounded(numbers[0], above) if len(numbers) == 1 else None
    pieces, at = [], 0
    for match, number in zip(written, [worked] if worked else numbers, strict=True):
        own = precision if worked is not None else _no_new_figures(match, number, precision)
        # The sign stays where the card wrote it, before the match.
        pieces += [value[at : match.start()], number_latex(abs(number.value), own)]
        at = match.end()
    shown = "".join([*pieces, value[at:]])
    return "\n".join([*headers, shown]) + ("\n" if body.endswith("\n") else "")


def _figures(text: str) -> int:
    return len(text.replace(",", "").replace(".", "").lstrip("0")) or 1


def _no_new_figures(match: re.Match[str], number: Number, precision: Precision) -> Precision:
    """The card's own value, with no working to take it from: in three figures or in powers
    of ten the rule shows no more figures than the card wrote. A Kp of 1.2 x 10^-4 (two
    figures, from 1.242 x 10^-4) as 1.20 x 10^-4 claimed a precision it never had."""
    if precision != RULE:
        return precision
    mantissa, exponent = number_parts(abs(number.value), precision)
    if exponent is None and abs(number.value) >= 1:
        return precision  # two places, zeros kept: 2.4 is 2.40
    written = _figures(match.group("number"))
    return Precision(figures=written) if _figures(mantissa) > written else precision


def _money(unit: str) -> bool:
    from app.services.subjects.registry import MONEY

    return bool(unit) and MONEY.names_currency(unit)


def _unrounded(card: Number, above: str) -> Number | None:
    """The value the working above the card reached, when the card's value is a rounding
    of it in the same unit: its last line of maths, the side after its last "="."""
    lines = _INLINE_MATHS.findall(above)
    if not lines or "=" not in lines[-1]:
        return None
    read = read_verified_value(lines[-1].rsplit("=", 1)[1])
    if read is None or len(read.numbers) != 1:
        return None
    worked = read.numbers[0]
    # A whole card ("3" buses for 2.67, "816" for 816.33) may be a count rounded up or
    # down as the question needs: only a card with decimals, or in powers of ten, is
    # known to be a rounding of its working (review).
    if worked.places is None or worked.unit != card.unit or card.places in (None, 0):
        return None
    if round_places(worked.value, card.places) != round_places(card.value, card.places):
        return None
    if worked.places is not None and worked.places <= card.places:
        return None  # the working says no more than the card: nothing to take back
    sign = -1 if card.value < 0 else 1
    return Number(abs(worked.value) * sign, worked.places, card.unit)
