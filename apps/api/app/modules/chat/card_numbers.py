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

# A number the card writes, its power of ten with it; never a script's (m^{2}, s^{-2}) or
# a fraction's part (\frac{1}{2}), nor a digit inside a word.
_WRITTEN = re.compile(
    r"(?<![\^_{\w.,])(?<!\^[-−])(?<!\^\{[-−])(?P<number>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:\s*(?:\\times|\\cdot|×)\s*10\s*\^\s*(?:\{\s*(?P<braced>[-+−]?\d+)\s*\}|(?P<bare>[-+]?\d)))?"
    r"(?![\w.])"
)
# Left as written: money, a decimal comma, a pH, pOH or pK.
_KEPT = re.compile(r"\\\$|[€£¥]|\{,\}|\bp(?:H|OH|K[ab]?)\b")
_INLINE_MATHS = re.compile(r"\$([^$\n]+)\$")
# A line that is a bold heading alone, in any language: "**Answer (b)**".
_BOLD_LINE = re.compile(r"\*\*[^*\n]+\*\*")


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


def cards_again(text: str, precision: Precision) -> list[tuple[str, str]] | None:
    """Every answer card of ``text`` again, its numbers in ``precision``, each with the Answer
    heading above it ("**Answer (b)**", "" for none): a precision-only follow-up ("1 digit")
    shows the cards of the reply before it once more, rounded as asked.

    None when a card cannot show it honestly: a number known to fewer places or figures than
    asked (a card of 3.13 with no working above it is no 3.130), one the precision would show
    as no figure at all (0.0456 A to one place is no 0.0 A), or one the rule leaves as
    written (an expression, a fraction, a sum of money, a pH).
    """
    cards: list[tuple[str, str]] = []
    previous = 0
    for fence in iter_fences(text):
        if not fence.closed or fence.lang not in ANSWER_FENCE_LANGS:
            continue
        above, previous = text[previous : fence.start], fence.end
        body = text[fence.body_start : fence.body_end]
        shown = _shown(body, above, precision)
        if shown is None or not _known_to(body, above, precision):
            return None
        card = text[fence.start : fence.body_start] + shown + text[fence.body_end : fence.end]
        cards.append((_heading_above(above), card.strip()))
    return cards or None


def _heading_above(above: str) -> str:
    """The heading right above a card, as written: "**Answer (b)**", "**Respuesta**"."""
    lines = [line for line in above.strip().split("\n") if line.strip()]
    return lines[-1].strip() if lines and _BOLD_LINE.fullmatch(lines[-1].strip()) else ""


def _known_to(body: str, above: str, precision: Precision) -> bool:
    """Each number the card shows is known to the precision asked: the working's value
    unrounded, or the card's own, has as many places or figures."""
    read = read_verified_value(body)
    if read is None:
        return False
    worked = _unrounded(read.numbers[0], above) if len(read.numbers) == 1 else None
    known = [worked] if worked is not None else list(read.numbers)
    if precision.unrounded:
        return worked is not None
    if len(known) == 1 and _exactly_whole(known[0], above):
        return True  # T = 75 N, worked to 75 N: 75.0 N is no figure it lacks
    return all(_holds(number, precision) for number in known)


def _exactly_whole(card: Number, above: str) -> bool:
    """A whole card the working above it reached as the same whole number."""
    worked = _worked(above)
    return (
        card.places == 0
        and worked is not None
        and worked.places == 0
        and worked.unit == card.unit
        and worked.value == card.value
    )


def _holds(number: Number, precision: Precision) -> bool:
    if number.places is None:
        return False
    if precision.places >= 0:
        shown = round_places(number.value, precision.places)
        return number.places >= precision.places and (shown != 0 or number.value == 0)
    written = format(round_places(number.value, number.places), "f")
    return _figures(written.lstrip("-")) >= precision.figures


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
    each = _unrounded_each(numbers, above)
    pieces, at = [], 0
    for match, number, worked in zip(written, numbers, each, strict=True):
        own = precision if worked is not None else _no_new_figures(match, number, precision)
        # The sign stays where the card wrote it, before the match.
        pieces += [value[at : match.start()], _number_shown(match, worked or number, own)]
        at = match.end()
    shown = "".join([*pieces, value[at:]])
    return "\n".join([*headers, shown]) + ("\n" if body.endswith("\n") else "")


def _number_shown(match: re.Match[str], number: Number, precision: Precision) -> str:
    """The number by the rule; a whole number with no unit written in full stays whole at
    any size: 2^40 is 1099511627776, an exact answer, not 1.10 x 10^12 (review)."""
    if number.places == 0 and not number.unit and match.group("braced", "bare") == (None, None):
        return str(abs(int(number.value)))
    return number_latex(abs(number.value), precision)


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


def _measured(unit: str) -> bool:
    """A unit of measure (N, m/s, g, kPa): a value in it is no count of things."""
    from app.services.law_binding.units import dimension_of

    kind = dimension_of(unit) if unit else None
    return kind is not None and kind != "dimensionless"


def _money(unit: str) -> bool:
    from app.services.subjects.registry import MONEY

    return bool(unit) and MONEY.names_currency(unit)


def _worked(above: str) -> Number | None:
    """The one value the working above a card ends on: its last line of maths, the side
    after its last "="."""
    lines = _INLINE_MATHS.findall(above)
    return _line_value(lines[-1]) if lines else None


def _line_value(line: str) -> Number | None:
    """The one value a line of maths reaches: the side after its last "="."""
    if "=" not in line:
        return None
    read = read_verified_value(line.rsplit("=", 1)[1])
    return None if read is None or len(read.numbers) != 1 else read.numbers[0]


def _unrounded_each(numbers: list[Number], above: str) -> list[Number | None]:
    """Each card number's value as the working above reached it, unrounded, or None.

    One number: the working's last line (``_unrounded``). Several ("2.34 s; 6.71 m; 38.3
    m"): each the nearest line above that reached it, in the card's order, each line once. A card of three
    values padded 38.3 to 38.30 where its working had reached 38.3157 (2026-11-21)."""
    if len(numbers) == 1:
        return [_unrounded(numbers[0], above)]
    lines = [value for line in _INLINE_MATHS.findall(above) if (value := _line_value(line))]
    # The card's last number takes the lowest line that reached it, and each number before
    # it a line above that one: card and working run in one order, so two values rounding
    # alike (H 23.22 and R 23.16, both 23.2) never swap (review, #2525).
    found: list[Number | None] = [None] * len(numbers)
    below = len(lines)
    for index in range(len(numbers) - 1, -1, -1):
        number = numbers[index]
        match = next(
            (at for at in range(below - 1, -1, -1) if _rounding_of(number, lines[at])), None
        )
        if match is not None:
            found[index] = _signed_as(number, lines[match])
            below = match
    return found


def _unrounded(card: Number, above: str) -> Number | None:
    """The value the working above the card reached, when the card's value is a rounding
    of it in the same unit."""
    worked = _worked(above)
    if worked is None or not _rounding_of(card, worked):
        return None
    return _signed_as(card, worked)


def _signed_as(card: Number, worked: Number) -> Number:
    sign = -1 if card.value < 0 else 1
    return Number(abs(worked.value) * sign, worked.places, card.unit)


def _rounding_of(card: Number, worked: Number) -> bool:
    """The card's value is a rounding of the working's, in the same unit."""
    # A whole card ("3" buses for 2.67) may be a count rounded up or down as the question
    # needs (review); a whole card in a unit of measure is a rounding of its working: the
    # tension at the bottom carded 104 N beside the top's 45.57 N (2026-11-20).
    if worked.places is None or worked.unit != card.unit or card.places is None:
        return False
    if card.places == 0 and not _measured(card.unit):
        return False
    if round_places(worked.value, card.places) != round_places(card.value, card.places):
        return False
    # The working says no more than the card: nothing to take back.
    return worked.places > card.places
