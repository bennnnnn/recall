# ruff: noqa: RUF002, RUF003 -- the module reads × and − as a card writes them.
"""Every answer card's number shown by the one rule (``services.rounding_rule``), whoever
wrote the card: a subject's solver, the worked layout, the formal check or the model; a
chemistry solver's checked card is the exception (below).

A card that states plain values (``P = 109324.04\\,\\mathrm{Pa}``, ``x = 2 or x = -3``,
``1.09 \\times 10^{5}\\,\\mathrm{Pa}``) has each number written again by the rule, in the
precision the question asks for. A card holding one value the working above it reached
unrounded (the working's last line, the card's value a rounding of it, in the same unit)
shows the working's value rounded once: the model's own "3 significant figures" made
109324.04 Pa a card of 1.09 × 10⁵ (the owner's chat, 2026-11-18). An expression, a fraction,
a sum of money and a pH are left as written: a pH keeps the decimals its concentration's
figures give it.

A chemistry solver's checked cards keep the significant figures of the question's data, the
rule chemistry textbooks teach (``chemistry.sig_figs``; owner, 2026-11-23); only a precision
the question asks for rounds them again here. The model's own unchecked card on that turn
follows the rule.
"""

from __future__ import annotations

import re
from decimal import Decimal
from fractions import Fraction
from typing import TYPE_CHECKING

from app.modules.chat.card_lists import known_value, listed_values
from app.modules.chat.card_walk import answer_cards
from app.modules.chat.written_numbers import (
    WRITTEN_NUMBER,
    any_numbers,
    first_number,
    power_of,
)
from app.services.answer_check import (
    TRAILING_DOTS,
    Number,
    VerifiedValue,
    read_verified_value,
)
from app.services.answer_fence import (
    CHEMISTRY_NOTATION_LINE,
    UNCHECKED_ANSWER_MARKER,
    VERIFIED_ANSWER_MARKER,
    answer_header_and_value,
)
from app.services.rounding_rule import (
    PLACES,
    RULE,
    SMALL_BELOW,
    Precision,
    asked_precision,
    number_latex,
    number_parts,
)
from app.services.school_rounding import round_places

if TYPE_CHECKING:
    from app.modules.chat.finalize_passes import FinalizeState

# Left as written: money, a decimal comma, a pH, pOH or pK.
_KEPT = re.compile(r"\\\$|[€£¥]|\{,\}|\bp(?:H|OH|K[ab]?)\b")
_INLINE_MATHS = re.compile(r"\$([^$\n]+)\$")
# A line that is a bold heading alone, in any language: "**Answer (b)**".
_BOLD_LINE = re.compile(r"\*\*[^*\n]+\*\*")
# The rounding a line of working may end on: "t = 4.82488 s \approx 4.82 s".
ROUNDED_TO = re.compile(r"\\approx(?![A-Za-z])|≈")


def format_card_numbers(state: FinalizeState) -> str:
    """The reply with each card's numbers by the rule (the module docstring). A solver that
    writes its cards to its subject's own precision (chemistry's significant figures of the
    data) keeps them, unless the question asks for another."""
    precision = asked_precision(state.ctx.user_message_content or "")
    verified = state.ctx.verified_subject
    if verified is None or not verified.cards_keep_precision:
        return card_numbers(state.text, precision)
    # A photo read uncertainly unchecks the solver's card; it is still the solver's, and is
    # known by its numbers. The model's own card there follows the rule.
    unchecked: frozenset[str] = frozenset()
    if state.ctx.photo_uncertain is True:
        answers = (verified, *verified.question_parts)
        unchecked = frozenset(
            number for block in answers for number in any_numbers(block.canonical_answer or "")
        )
    return card_numbers(state.text, precision, keep_checked=True, solver_numbers=unchecked)


def card_numbers(
    text: str,
    precision: Precision,
    *,
    keep_checked: bool = False,
    solver_numbers: frozenset[str] = frozenset(),
) -> str:
    """``keep_checked``: a card the server checked keeps its solver's precision, and takes a
    precision the question asks for only when the working knows the value to it (a card of
    2.4 is no 2.400). ``solver_numbers``: the solver's answers' numbers, which an unchecked
    card that is the solver's (a photo read uncertainly) holds. The model's own unchecked
    card on that turn follows the rule."""
    changes: list[tuple[int, int, str]] = []
    for card in answer_cards(text):
        fence = card.fence
        above, body = text[card.since_card : fence.start], card.body(text)
        if keep_checked and _solver_card(body, solver_numbers):
            if precision == RULE or not _known_to(body, above, precision):
                continue
        shown = _shown(body, above, precision)
        if shown is not None and shown != body:
            changes.append((fence.body_start, fence.body_end, shown))
    for start, end, body in reversed(changes):
        text = text[:start] + body + text[end:]
    return text


def _solver_card(body: str, solver_numbers: frozenset[str]) -> bool:
    """Whether a card is the solver's: checked, or unchecked with a solver's value (the first
    number after its last "=": "0.1298" of "c_{2} = 0.1298\\,\\mathrm{mol/L}")."""
    headers, value = answer_header_and_value(body)
    if VERIFIED_ANSWER_MARKER in headers:
        return True
    found = first_number(value.rpartition("=")[2])
    return UNCHECKED_ANSWER_MARKER in headers and found is not None and found in solver_numbers


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
    for card in answer_cards(text):
        fence = card.fence
        above, body = text[card.since_card : fence.start], card.body(text)
        shown = _shown(body, above, precision)
        if shown is None or not _known_to(body, above, precision):
            return None
        whole = text[fence.start : fence.body_start] + shown + text[fence.body_end : fence.end]
        cards.append((_heading_above(above), whole.strip()))
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
    # The digits the card knows: 4 × 10^1 knows one, though "40" reads as two (review).
    known = round_places(number.value, number.places).as_tuple().digits
    return len(known) >= precision.figures


def plain_numbers(body: str) -> tuple[list[str], str, VerifiedValue] | None:
    """A card's headers, its value line and the numbers in it, when the rule writes them
    again; None for a card left as written: several lines, chemistry notation, an
    expression, an exact fraction, a sum of money, a decimal comma or a pH."""
    headers, value = answer_header_and_value(body)
    if not value or "\n" in value or CHEMISTRY_NOTATION_LINE in headers or _KEPT.search(value):
        return None
    read = read_verified_value(body)
    if read is None or len(WRITTEN_NUMBER.findall(value)) != len(read.numbers):
        return None
    if any(number.places is None for number in read.numbers):
        return None  # an exact fraction
    if any(_money(number.unit) for number in read.numbers):
        return None  # a sum of money, to the cent as written
    return headers, value, read


def _shown(body: str, above: str, precision: Precision) -> str | None:
    """The card's body with its numbers by the rule, or None to leave it as written."""
    plain = plain_numbers(body)
    if plain is None:
        return _listed_shown(body, above, precision)
    headers, value, read = plain
    numbers = list(read.numbers)
    written = list(WRITTEN_NUMBER.finditer(value))
    each = _unrounded_each(numbers, above)
    pieces, at = [], 0
    for match, number, worked in zip(written, numbers, each, strict=True):
        known = worked or _known(match, value, above)
        own = precision if known is not None else _no_new_figures(match, number, precision)
        # The sign stays where the card wrote it, before the match.
        pieces += [value[at : match.start()], _number_shown(match, known or number, own)]
        at = _past_dots(value, match.end())
    shown = "".join([*pieces, value[at:]])
    return "\n".join([*headers, shown]) + ("\n" if body.endswith("\n") else "")


def _past_dots(value: str, at: int) -> int:
    """Past an ellipsis after a number's digits ("0.357142857\\ldots"): once the number is
    rounded it no longer goes on."""
    dots = TRAILING_DOTS.match(value, at)
    return dots.end() if dots is not None else at


def _known(match: re.Match[str], value: str, above: str) -> Number | None:
    """The value a card's number rounds, as the working above it works it out
    (``card_lists.known_value``), when the card shows fewer places than the rule."""
    written = match.group("number").replace(",", "")
    places = len(written.partition(".")[2])
    if places >= PLACES or match.group("braced", "bare", "calculator") != (None,) * 3:
        return None
    found = known_value(written, value[match.end() :], above)
    return None if found is None else Number(Fraction(repr(found)), None)


def _listed_shown(body: str, above: str, precision: Precision) -> str | None:
    """A card of several values no single reading takes, each a number standing as a value: a
    vector's components ("(-9.0434 î + 8.6956 ĵ) m/s"), a magnitude, an angle and its
    direction. Each decimal number is written by the rule; a whole number, a script, a
    fraction's part, money and an expression are left as written (``listed_values``)."""
    headers, value = answer_header_and_value(body)
    if not value or "\n" in value or CHEMISTRY_NOTATION_LINE in headers or _KEPT.search(value):
        return None
    if not listed_values(value):
        return None
    pieces, at = [], 0
    for match in WRITTEN_NUMBER.finditer(value):
        number = match.group("number")
        if "." not in number or match.group("braced", "bare", "calculator") != (None,) * 3:
            continue
        read = Number(Fraction(Decimal(number.replace(",", ""))), len(number.partition(".")[2]))
        known = _known(match, value, above)
        own = precision if known is not None else _no_new_figures(match, read, precision)
        pieces += [value[at : match.start()], _number_shown(match, known or read, own)]
        at = _past_dots(value, match.end())
    shown = "".join([*pieces, value[at:]])
    return "\n".join([*headers, shown]) + ("\n" if body.endswith("\n") else "")


def _number_shown(match: re.Match[str], number: Number, precision: Precision) -> str:
    """The number by the rule; a whole number with no unit written in full stays whole at
    any size: 2^40 is 1099511627776, an exact answer, not 1.10 x 10^12 (review)."""
    if number.places == 0 and not number.unit and power_of(match) is None:
        return str(abs(int(number.value)))
    return number_latex(abs(number.value), precision)


def _figures(text: str) -> int:
    return len(text.replace(",", "").replace(".", "").lstrip("0")) or 1


def _no_new_figures(match: re.Match[str], number: Number, precision: Precision) -> Precision:
    """The card's own value, with no working to take it from: the rule shows no more figures
    than the card wrote, never a padded zero. A Kp of 1.2 x 10^-4 (two figures, from
    1.242 x 10^-4) as 1.20 x 10^-4 claimed a precision it never had, and a θ of 43.9° (from
    43.879°) as 43.90° a digit the true value contradicts (owner, 2026-11-25). A value the
    working knows, or one the card wrote to more places, is written by the rule."""
    if precision != RULE:
        return precision
    mantissa, exponent = number_parts(abs(number.value), precision)
    digits = match.group("number").replace(",", "")
    written = _figures(digits)
    if _figures(mantissa) <= written:
        return precision
    if exponent is not None or abs(number.value) < SMALL_BELOW:
        return Precision(figures=written)
    return Precision(places=len(digits.partition(".")[2]))


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
    # "\mu \approx 0.404" under "\mu = 0.404026": the rounding on a row of its own (the
    # calculation layout sets a chain with no unit one state per row) reaches nothing new.
    if len(lines) > 1 and "=" not in lines[-1] and ROUNDED_TO.search(lines[-1]):
        lines.pop()
    return line_value(lines[-1]) if lines else None


def line_value(line: str) -> Number | None:
    """The one value a line of maths reaches: the side after its last "=", before the
    rounding a line may end on ("4.82488 s \\approx 4.82 s" reaches 4.82488 s)."""
    if "=" not in line:
        return None
    reached = ROUNDED_TO.split(line.rsplit("=", 1)[1], maxsplit=1)[0]
    read = read_verified_value(reached)
    return None if read is None or len(read.numbers) != 1 else read.numbers[0]


def _unrounded_each(numbers: list[Number], above: str) -> list[Number | None]:
    """Each card number's value as the working above reached it, unrounded, or None.

    One number: the working's last line (``_unrounded``). Several ("2.34 s; 6.71 m; 38.3
    m"): each the nearest line above that reached it, in the card's order, each line once. A card of three
    values padded 38.3 to 38.30 where its working had reached 38.3157 (2026-11-21)."""
    if len(numbers) == 1:
        return [_unrounded(numbers[0], above)]
    lines = [value for line in _INLINE_MATHS.findall(above) if (value := line_value(line))]
    # The card's last number takes the lowest line that reached it, and each number before
    # it a line above that one: card and working run in one order, so two values rounding
    # alike (H 23.22 and R 23.16, both 23.2) never swap (review, #2525).
    found: list[Number | None] = [None] * len(numbers)
    below = len(lines)
    for index in range(len(numbers) - 1, -1, -1):
        number = numbers[index]
        match = next(
            (at for at in range(below - 1, -1, -1) if rounding_of(number, lines[at])), None
        )
        if match is not None:
            found[index] = _signed_as(number, lines[match])
            below = match
    return found


def _unrounded(card: Number, above: str) -> Number | None:
    """The value the working above the card reached, when the card's value is a rounding
    of it in the same unit."""
    worked = _worked(above)
    if worked is None or not rounding_of(card, worked):
        return None
    return _signed_as(card, worked)


def _signed_as(card: Number, worked: Number) -> Number:
    sign = -1 if card.value < 0 else 1
    return Number(abs(worked.value) * sign, worked.places, card.unit)


def rounding_of(card: Number, worked: Number) -> bool:
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
