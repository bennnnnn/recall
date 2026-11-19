"""The reply's own answer cards held to the server's values, card to card.

Each ```answer card the reply ends a part on is read as a quantity (its number and unit,
in any unit of its kind: 0.01 m² and 100 cm² are one area, 50 Ω is a resistance) and paired
with the server's value for the part it answers: by the part's letter when both have one,
otherwise in order within each kind. A card stands when the server's value, in the card's
unit and size, is within the card's rounding of it, anywhere in the range the standard
constants allow (g as 9.8 or 10: the book's g is an assumption, not an error), and when
the reply never wrote one of the question's numbers the server's value is worked from, it
read the question another way and is not held to that reading. Any other card is the
server's: its value replaces the card's, with one line saying where it comes from. No card
is ever added: a part the reply did not card keeps what it wrote.
"""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.services.answer_check import read_verified_value
from app.services.answer_fence import ANSWER_FENCE_LANGS, UNCHECKED_ANSWER_MARKER
from app.services.formal.answer import FormalValue
from app.services.md_fence_scan import iter_fences
from app.services.part_answer_cards import PART_ANSWER_HEADING

logger = logging.getLogger(__name__)

# Rounding a model may do: a card to 3 significant figures sits within 1% of the value.
_ROUNDING = 0.01
# "**(b) Current through the lamp**": a part's own heading above its working.
_PART_HEADING = re.compile(r"^\s*(?:#{1,4}\s+)?\*\*\((?P<letter>[a-h])\)", re.MULTILINE)
# A number the working writes: "1,200", "0.32", "2.4 \times 10^{3}".
_POWER = re.compile(
    r"(\d(?:[\d.]*\d)?)\s*(?:\\times|\\cdot|\u00d7|\*)\s*10\s*\^\s*\{?\s*([-+]?\d+)\s*\}?"
)
_NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*(?:e[-+]?\d+)?")
_TIGHT_SPACE = re.compile(r"(?<=\d)(?:\\,|\\ |\{,\}|\s)(?=\d{3}(?!\d))")


@dataclass(frozen=True)
class ReplyCard:
    """One card: the part it answers ("" when no heading names one), where its body is,
    and its value as a number, the unit written, and the digits after the point."""

    letter: str
    body_start: int
    body_end: int
    value: float
    unit: str
    places: int | None


def reply_cards(text: str) -> list[ReplyCard]:
    """Each closed card holding one plain value, with the part its heading names."""
    cards: list[ReplyCard] = []
    previous = 0
    for fence in iter_fences(text):
        if not fence.closed or fence.lang not in ANSWER_FENCE_LANGS:
            continue
        above = text[previous : fence.start]
        previous = fence.end
        read = read_verified_value(_plain_value(text[fence.body_start : fence.body_end]))
        if read is None or len(read.numbers) != 1:
            continue
        number = read.numbers[0]
        cards.append(
            ReplyCard(
                letter=_letter(above),
                body_start=fence.body_start,
                body_end=fence.body_end,
                value=float(number.value),
                unit=number.unit,
                places=number.places,
            )
        )
    return cards


# A note in brackets after the value, "(clockwise)", "(ratio)", brackets inside it too.
_NOTE = re.compile(r"\s*\((?:[^()\d\n]|\([^()\d\n]*\))*\)\s*$")
# A direction or a label in words after the maths: "$10\,\mathrm{m/s}$ east".
_WORDS_AFTER = re.compile(r"^(.*[}$])\s+[A-Za-z][A-Za-z ]*$")
_UNIT_GROUP = re.compile(r"\\(?:text|mathrm)\s*\{([^{}]*)\}")
# Two unit letters a space or a thin space joins are a product: "N m", "N\,m" is N·m.
_JOINED_UNITS = re.compile(r"(?<=[A-Za-zΩ])(?:\s+|\\,|\\ )(?=[A-Za-zΩ])")


def _plain_value(body: str) -> str:
    """The card's body with a note after its value dropped and a product of units kept
    whole ("N m" read as one N·m, not nanometres)."""
    lines = body.rstrip("\n").split("\n")
    value = lines[-1]
    for _ in range(3):
        value = _NOTE.sub("", value).strip()
        value = _WORDS_AFTER.sub(r"\1", value).strip().strip("$").strip()
    value = _UNIT_GROUP.sub(lambda m: "\\mathrm{" + _JOINED_UNITS.sub("·", m.group(1)) + "}", value)
    value = _JOINED_UNITS.sub("·", value) if "\\mathrm" not in value else value
    return "\n".join([*lines[:-1], value])


def _letter(above: str) -> str:
    """The part the text since the last card names: its last Answer (b) heading, else its
    last part heading; "" for none."""
    answers = [
        match.group("letter")
        for line in above.split("\n")
        if (match := PART_ANSWER_HEADING.match(line)) is not None
    ]
    if answers:
        return answers[-1]
    parts = [match.group("letter") for match in _PART_HEADING.finditer(above)]
    return parts[-1] if parts else ""


def written_numbers(text: str) -> list[float]:
    """Every number the reply writes outside its cards, powers of ten included."""
    from app.services.formal.solve import parse_number

    outside = text
    for fence in reversed(list(iter_fences(text))):
        if fence.lang in ANSWER_FENCE_LANGS:
            outside = outside[: fence.start] + "\n" + outside[fence.end :]
    outside = _TIGHT_SPACE.sub("", outside)
    numbers = [float(m.group(1)) * 10.0 ** int(m.group(2)) for m in _POWER.finditer(outside)]
    for match in _NUMBER.finditer(_POWER.sub(" ", outside)):
        number = parse_number(match.group())
        if number is not None:
            numbers.append(number)
    return numbers


def _read_it_so(value: FormalValue, numbers: Sequence[float]) -> bool:
    """The reply wrote every number of the question the server's value is worked from."""
    return all(
        any(math.isclose(used, n, rel_tol=1e-6, abs_tol=1e-12) for n in numbers)
        for used in value.uses
    )


def _kind(unit: str) -> Any | None:
    from app.services.formal.solve import as_quantity

    try:
        return as_quantity(1.0, unit).dimensionality
    except Exception:  # pint: a unit it cannot read, so no kind to pair by
        return None


def _in_card_unit(server: float, value: FormalValue, card: ReplyCard) -> list[float]:
    """The server's ``server`` (in its asked unit) as the card would write it: in the
    card's unit, or, for a card with no unit, both the bare number and the pure number."""
    from app.services.formal.solve import as_quantity

    quantity = as_quantity(server, value.unit)
    if not card.unit:
        bare = [server]
        if quantity.dimensionless:
            bare.append(float(quantity.to("dimensionless").magnitude))
        return bare
    return [float(quantity.to(as_quantity(1.0, card.unit).units).magnitude)]


def _rounding(card: ReplyCard) -> float:
    """Half the card's last digit, when it shows two significant figures or more: 0.27 may
    round 0.2727, but a lone "2" is no rounding of 1.5."""
    if card.places is None:
        return 0.0
    digits = f"{abs(card.value):.{card.places}f}".replace(".", "").lstrip("0")
    return 0.5 * 10.0**-card.places if len(digits) >= 2 else 0.0


def agrees(card: ReplyCard, value: FormalValue) -> bool | None:
    """The card states the server's value, within its rounding and the constants' range;
    None when the two cannot be compared (kinds that do not convert)."""
    try:
        ends = [_in_card_unit(end, value, card) for end in (value.low, value.high)]
    except Exception:  # pint: kinds that do not convert
        return None
    rounding = _rounding(card)
    shown = abs(card.value)
    for low, high in zip(*ends, strict=True):
        lowest, highest = sorted((abs(low), abs(high)))
        slack = max(rounding, _ROUNDING * max(highest, shown))
        if lowest - slack <= shown <= highest + slack:
            return True
    return False


def _pairs(
    cards: list[ReplyCard], values: Sequence[FormalValue]
) -> list[tuple[ReplyCard, FormalValue]]:
    """Each server value with the card that answers its part: by letter when both name
    parts, else in order among the cards and values of one kind, when they are as many."""
    if all(value.part for value in values) and any(card.letter for card in cards):
        by_letter: dict[str, list[ReplyCard]] = {}
        for card in cards:
            by_letter.setdefault(card.letter, []).append(card)
        return [
            (by_letter[value.part][0], value)
            for value in values
            if len(by_letter.get(value.part, [])) == 1
        ]
    pairs: list[tuple[ReplyCard, FormalValue]] = []
    kinds = {str(_kind(value.unit)) for value in values}
    for kind in kinds:
        own = [value for value in values if str(_kind(value.unit)) == kind]
        of_kind = [card for card in cards if card.unit and str(_kind(card.unit)) == kind]
        if not of_kind and len(own) == 1 and len(cards) == 1 and not cards[0].unit:
            of_kind = cards  # the card left its unit off
        if len(of_kind) == len(own):
            pairs += list(zip(of_kind, own, strict=True))
    return pairs


def held_to_server(text: str, values: Sequence[FormalValue], line: str) -> str:
    """``text`` with each card that disagrees with the server's value replaced by it, as
    the module docstring says; ``line`` goes directly above each replaced card."""
    numbers = written_numbers(text)
    changes: list[tuple[ReplyCard, FormalValue]] = []
    for card, value in _pairs(reply_cards(text), values):
        if not _read_it_so(value, numbers):
            logger.info("formal answer: the reply read part %r another way", value.part)
            continue
        verdict = agrees(card, value)
        logger.info("formal answer: part %r card %s", value.part, verdict)
        if verdict is False:
            changes.append((card, value))
    for card, value in sorted(changes, key=lambda change: -change[0].body_start):
        opener = text.rfind("\n", 0, card.body_start - 1) + 1
        body = f"{UNCHECKED_ANSWER_MARKER}\n{value.card_value}\n"
        text = f"{text[:opener]}{line}\n\n{text[opener : card.body_start]}{body}{text[card.body_end :]}"
    return text
