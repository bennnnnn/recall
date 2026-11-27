# ruff: noqa: RUF001, RUF003 -- the module reads the minus and times signs as a reply writes them.
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
included). A line that already ends on ≈ (the model may write it) keeps its rounding when
it is the card's and takes the card's number when it is not, so the two never differ. A
line already equal to the card, one the card does not round (a disagreement is another
pass's), and a card the rule leaves as written (several values, an expression, a sum of
money, a pH: ``card_numbers.plain_numbers``) are left as they are.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING

from app.modules.chat.card_numbers import (
    ROUNDED_TO,
    line_value,
    plain_numbers,
    rounding_of,
)
from app.modules.chat.card_walk import answer_cards
from app.modules.chat.tex_arithmetic import DISPLAY_MATH, INLINE_MATH
from app.modules.chat.working_cards import only_headings, without_closing_headings
from app.modules.chat.written_numbers import WRITTEN_NUMBER, in_tex
from app.services.answer_check import Number, read_verified_value

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

# What may close the line after its maths: a full stop or a comma.
_CLOSING_MARK = re.compile(r"[ \t]*[.,]")
# What may stand before the line's number: its sign.
_SIGN = re.compile(r"[-−+]?\s*")


def round_working_ends(state: FinalizeState) -> str:
    return rounded_ends(state.text)


def rounded_ends(text: str) -> str:
    """``text`` with each card's working ending on the card's rounding (the docstring)."""
    changes: list[tuple[int, int, str]] = []
    for answer in answer_cards(text):
        fence, above_start = answer.fence, answer.since_fence
        card = _card(answer.body(text))
        line = _last_maths(text[above_start : fence.start]) if card else None
        if card is None or line is None:
            continue
        start, end = line
        rounded = _rounded(text[above_start + start : above_start + end], *card)
        if rounded is not None:
            changes.append((above_start + start, above_start + end, rounded))
    for start, end, rounded in reversed(changes):
        text = text[:start] + rounded + text[end:]
    return text


def _card(body: str) -> tuple[Number, str, str | None] | None:
    """A card's one value: its number, the number as the card writes it, and its name."""
    plain = plain_numbers(body)
    if plain is None or len(plain[2].numbers) != 1:
        return None
    _headers, value, read = plain
    written = WRITTEN_NUMBER.search(value)
    if written is None or not in_tex(written):
        return None  # "1.77e-10", "1.8 × 10⁻⁵": prose's spelling, not a line of maths
    return read.numbers[0], written.group(0).replace("×", "\\times "), read.label


def _last_maths(above: str) -> tuple[int, int] | None:
    """Where the last maths above a card is (its inside), when only blank lines and bold
    headings stand between it and the card. The headings go first: "**Answer for $t$**"
    names the card, it is no working (``working_cards.without_closing_headings``)."""
    working = without_closing_headings(above)
    spans = [
        (match.start(group), match.end(group), match.end())
        for match in DISPLAY_MATH.finditer(working)
        for group in ("dollars", "brackets")
        if match.group(group) is not None
    ]
    # Display maths blanked, so its "$$" is never read as two inline lines.
    blanked = DISPLAY_MATH.sub(lambda match: " " * len(match.group(0)), working)
    spans += [
        (match.start(1), match.end(1), match.end()) for match in INLINE_MATH.finditer(blanked)
    ]
    if not spans:
        return None
    start, end, outer_end = max(spans, key=lambda span: span[2])
    after = working[outer_end:]
    closing = _CLOSING_MARK.match(after)
    if not only_headings(after[closing.end() :] if closing else after):
        return None
    return start, end


def _rounded(maths: str, card: Number, shown: str, label: str | None) -> str | None:
    """The line ending on the card's rounding, in the line's own sign and unit, or None to
    leave it. A rounding the line already writes is kept when it is the card's, and given the
    card's number when it is not: a model's "\\approx 25.4 m" over a card of 25.39 m. A unit
    written on one side only is both sides': "4.82488 s \\approx 4.8" and "4.82488 \\approx
    4.8 s" over a card of 4.82 s both end "\\approx 4.82 s" (review, #2577)."""
    body = maths.rstrip()
    head, equals, side = body.rpartition("=")
    rounding = ROUNDED_TO.search(side)
    reached = side[: rounding.start()] if rounding else side
    said_tex = side[rounding.end() :] if rounding else ""
    worked = line_value(body)
    said = _one_number(said_tex) if rounding else None
    if not equals or worked is None or (rounding and said is None):
        return None
    if said is not None and not worked.unit:
        worked = replace(worked, unit=said.unit)  # "4.82488 \approx 4.8 s": its unit
    unitless = said is not None and not said.unit and bool(worked.unit)
    if said is not None and unitless:
        said = replace(said, unit=worked.unit)  # "4.82488 s \approx 4.8": the same unit
    if worked.value == card.value or not rounding_of(card, worked):
        return None  # already the card's, or a disagreement: another pass's
    named = read_verified_value(f"{head}={reached}")
    if label and named is not None and named.label and named.label != label:
        return None  # another quantity's line: v_y above a card of v_x
    if said is None or rounding is None:
        ending = _with_number(reached.strip(), shown)
        return None if ending is None else f"{body} \\approx {ending}{maths[len(body) :]}"
    if said.unit != card.unit or (said.value < 0) != (card.value < 0):
        return None
    if said.value == card.value and not unitless:
        return None  # the line's own rounding is the card's
    # A rounding with no unit is written as the value before it is, with the card's number.
    again = _with_number(reached.strip(), shown) if unitless else _with_number(said_tex, shown)
    if again is None:
        return None
    lead = said_tex[: len(said_tex) - len(said_tex.lstrip())] if unitless else ""
    return f"{head}={side[: rounding.end()]}{lead}{again}{maths[len(body) :]}"


def _one_number(tex: str) -> Number | None:
    read = read_verified_value(tex)
    return read.numbers[0] if read is not None and len(read.numbers) == 1 else None


def _with_number(side: str, shown: str) -> str | None:
    """``side`` with its one number written as ``shown``, its sign and unit kept; None when
    the number stands inside something else ("\\text{about }4.82488")."""
    lead = len(side) - len(side.lstrip())
    number = WRITTEN_NUMBER.search(side)
    if number is None or not _SIGN.fullmatch(side[lead : number.start()]):
        return None
    return f"{side[: number.start()]}{shown}{side[number.end() :]}"
