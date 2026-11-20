"""The reply's own answer cards held to the server's values, card to card.

Each ```answer card the reply ends a part on is read as a quantity (its number and unit,
in any unit of its kind: 0.01 m² and 100 cm² are one area, 50 Ω is a resistance) and paired
with the server's value for the part it answers: by the part's letter when both have one,
otherwise within each kind: the one card of a kind, or each card by the name it gives its
value. Cards of one kind with no names are never paired by order, so never corrected. A card stands when the server's value, in the card's
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
from app.services.rounding_rule import RULE, Precision

logger = logging.getLogger(__name__)

# Beyond the card's own rounding (half its last digit), what a working that rounded along
# the way drifts by: 0.273 A carried into R = 220/0.273 is 805.9 Ω for 806.7. A value
# rounded too soon (R = 220/0.27 = 814.8 Ω, live G8 t42) is 1% off and no rounding of it.
_ROUNDING = 0.005
# "**(b) Current through the lamp**": a part's own heading above its working.
_PART_HEADING = re.compile(r"^\s*(?:#{1,4}\s+)?\*\*\((?P<letter>[a-h])\)", re.MULTILINE)
# A number the working writes: "1,200", "0.32", "2.4 \times 10^{3}".
_POWER = re.compile(
    r"(\d(?:[\d.]*\d)?)\s*(?:\\times|\\cdot|\u00d7|\*)\s*10\s*\^\s*\{?\s*([-+]?\d+)\s*\}?"
)
_NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*(?:e[-+]?\d+)?")
_TIGHT_SPACE = re.compile(r"(?<=\d)(?:\\,|\\ |\{,\}| )(?=\d{3}(?!\d))")


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
    # The card's own name for its value ("T2" from "T_2 = 30 N"), "" for none.
    label: str = ""


def reply_cards(text: str) -> list[ReplyCard]:
    """Each closed card holding one plain value, with the part its heading names."""
    cards: list[ReplyCard] = []
    previous = 0
    for fence in iter_fences(text):
        if not fence.closed or fence.lang not in ANSWER_FENCE_LANGS:
            continue
        above = text[previous : fence.start]
        previous = fence.end
        body = text[fence.body_start : fence.body_end]
        read = read_verified_value(_plain_value(_one_form(body)))
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
                label=read.label or "",
            )
        )
    return cards


# A value's other form in brackets after it, opened after a space: "0.840 (84.0 percent)".
_OTHER_FORM = re.compile(r"^(?P<first>.*\d.*?)(?:\s|\\[ ,;])+\((?P<other>[^()]*\d[^()]*)\)\s*$")
_PERCENT_WORD = re.compile(r"\\text\{\s*per\s*cent\s*\}|\bper\s*cent\b", re.IGNORECASE)


def _one_form(body: str) -> str:
    """The card with a second form of its value dropped, when the bracket states the same
    value another way: "0.840 (84.0 percent)" is 0.840 once, so a wrong "0.79 (79%)" is
    still held to the server's 84 % (the review of #2491's merge, owner's phone 2026-11-17).
    A bracket that states another value leaves the card unread: it says two things."""
    lines = body.rstrip("\n").split("\n")
    match = _OTHER_FORM.match(lines[-1])
    if match is None:
        return body
    first, other = (
        read_verified_value(_plain_value(_PERCENT_WORD.sub(r"\\%", part)))
        for part in (match["first"], match["other"])
    )
    if first is None or other is None or len(first.numbers) != 1 or len(other.numbers) != 1:
        return body
    if not _same_value(first.numbers[0], other.numbers[0]):
        return body
    return "\n".join([*lines[:-1], match["first"]])


def _same_value(one: Any, two: Any) -> bool:
    """Two written values are one quantity: 0.84 and 84 %, 1.5 kJ and 1500 J."""
    from app.services.formal.maths import as_quantity

    try:
        left = as_quantity(float(one.value), one.unit or "dimensionless")
        right = as_quantity(float(two.value), two.unit or "dimensionless").to(left.units)
    except Exception as exc:  # pint: kinds that do not convert are two values
        logger.info("formal answer: a card's two forms not compared (%s)", type(exc).__name__)
        return False
    return math.isclose(left.magnitude, right.magnitude, rel_tol=_ROUNDING * 2)


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
    numbers: list[float] = []
    # "20\,000" is one number, and "40 120" two: each spelling is read, the union kept.
    for spelling in {outside, _TIGHT_SPACE.sub("", outside)}:
        numbers += [float(m.group(1)) * 10.0 ** int(m.group(2)) for m in _POWER.finditer(spelling)]
        for match in _NUMBER.finditer(_POWER.sub(" ", spelling)):
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
    from app.services.formal.maths import as_quantity

    try:
        return as_quantity(1.0, unit).dimensionality
    except Exception as exc:  # pint: a unit it cannot read, so no kind to pair by
        logger.info("formal answer: a card's unit not read (%s)", type(exc).__name__)
        return None


def _in_card_unit(server: float, value: FormalValue, card: ReplyCard) -> list[float]:
    """The server's ``server`` (in its asked unit) as the card would write it: in the
    card's unit, or, for a card with no unit, both the bare number and the pure number."""
    from app.services.formal.maths import as_quantity

    quantity = as_quantity(server, value.unit)
    if not card.unit or quantity.dimensionless:
        # A card with no unit, or a count a card names in words ("4000 turns": pint reads
        # a turn as an angle): the bare number, and the pure number (90% is 0.9).
        bare = [server]
        if quantity.dimensionless:
            bare.append(float(quantity.to("dimensionless").magnitude))
            if card.unit:
                bare += _in_unit_if_pure(quantity, card.unit)
        return bare
    return [float(quantity.to(as_quantity(1.0, card.unit).units).magnitude)]


def _card_label(body: str) -> str:
    """The card's own "T_2 = " before its value, kept when the value is replaced."""
    value = body.rstrip("\n").split("\n")[-1].strip().strip("$")
    left, equals, _right = value.rpartition("=")
    return f"{left.strip()} = " if equals and left.strip() else ""


def _asked_slack(card: ReplyCard, asked: Precision) -> float:
    """The rounding the question asked of the card's value."""
    if asked.places >= 0:
        return 0.5 * 10.0**-asked.places
    if asked.figures > 0 and card.value:
        return 0.5 * 10.0 ** (math.floor(math.log10(abs(card.value))) - asked.figures + 1)
    return 0.0


def _rounding(card: ReplyCard) -> float:
    """Half the card's last digit, when it shows two significant figures or more: 0.27 may
    round 0.2727, but a lone "2" is no rounding of 1.5."""
    if card.places is None:
        return 0.0
    # A card in powers of ten has places below 0: 1.5 x 10^6 is to the hundred thousand.
    shown = f"{abs(card.value):.{max(card.places, 0)}f}".replace(".", "")
    digits = shown.lstrip("0").rstrip("0") if card.places < 0 else shown.lstrip("0")
    return 0.5 * 10.0**-card.places if len(digits) >= 2 else 0.0


def _in_unit_if_pure(quantity: Any, unit: str) -> list[float]:
    """A pure number as a card's percent ("0.9" as "90 %"); nothing for any other unit."""
    from app.services.formal.maths import as_quantity

    try:
        target = as_quantity(1.0, unit)
        if "percent" not in str(target.units):
            return []
        return [float(quantity.to(target.units).magnitude)]
    except Exception as exc:  # pint: no such unit
        logger.info("formal answer: no percent unit (%s)", type(exc).__name__)
        return []


def _on_a_scale(value: FormalValue, card: ReplyCard) -> bool:
    """A temperature on a scale (°C, °F) whose sign is its value, not a direction: -10 °C
    is no +10 °C, where a velocity's sign is the reply's own convention (review)."""
    from app.services.formal.maths import as_quantity

    try:
        units = [value.unit, *([card.unit] if card.unit else [])]
        return any(not as_quantity(1.0, unit)._is_multiplicative for unit in units)
    except Exception as exc:  # pint: a unit it cannot read is no temperature scale
        logger.info("formal answer: a unit not read (%s)", type(exc).__name__)
        return False


def agrees(card: ReplyCard, value: FormalValue, asked: Precision = RULE) -> bool | None:
    """The card states the server's value, within its rounding and the constants' range;
    None when the two cannot be compared (kinds that do not convert)."""
    try:
        ends = [_in_card_unit(end, value, card) for end in (value.low, value.high)]
    except Exception as exc:  # pint: kinds that do not convert
        logger.info("formal answer: kinds that do not convert (%s)", type(exc).__name__)
        return None
    rounding = max(_rounding(card), _asked_slack(card, asked))
    signed = _on_a_scale(value, card)
    shown = card.value if signed else abs(card.value)
    for low, high in zip(*ends, strict=True):
        lowest, highest = sorted((low, high) if signed else (abs(low), abs(high)))
        slack = max(rounding, _ROUNDING * max(abs(lowest), abs(highest), abs(shown)))
        if lowest - slack <= shown <= highest + slack:
            return True
    return False


def _pairs(
    cards: list[ReplyCard], values: Sequence[FormalValue]
) -> list[tuple[ReplyCard, FormalValue]]:
    """Each server value with the card that answers its part: by letter when both name
    parts and every lettered pair is of one kind, then the values no letter paired among
    the cards left, by kind, when they are as many: one with one, several by the cards' own
    names. A reply that letters its parts its own way (a part asked in words left out, so
    (b) is the resistance the setup calls (c)) pairs that part by kind (Claude on #2501)."""
    lettered = _by_letter(cards, values) or []
    paired_cards = {id(card) for card, _ in lettered}
    paired_values = {id(value) for _, value in lettered}
    rest = [value for value in values if id(value) not in paired_values]
    if not rest:
        return lettered
    left = [card for card in cards if id(card) not in paired_cards]
    return lettered + _by_kind(left, rest)


def _by_kind(
    cards: list[ReplyCard], values: Sequence[FormalValue]
) -> list[tuple[ReplyCard, FormalValue]]:
    """The cards and values of each kind, when they are as many: one with one, several by
    the cards' own names (``_by_label``)."""
    pairs: list[tuple[ReplyCard, FormalValue]] = []
    kinds = {str(_kind(value.unit)) for value in values}
    for kind in kinds:
        own = [value for value in values if str(_kind(value.unit)) == kind]
        of_kind = [card for card in cards if card.unit and str(_kind(card.unit)) == kind]
        if not of_kind and len(own) == 1 and len(cards) == 1 and not cards[0].unit:
            of_kind = cards  # the card left its unit off
        if len(of_kind) == len(own) == 1:
            pairs.append((of_kind[0], own[0]))
        elif len(of_kind) == len(own):
            pairs += _by_label(of_kind, own)
    return pairs


# A Greek letter a card writes, by the name a setup's symbol spells it with.
_GREEK_NAMES = {
    "\u0394": "Delta", "\u03b1": "alpha", "\u03b2": "beta", "\u03b3": "gamma",
    "\u03b8": "theta", "\u03bb": "lambda", "\u03bc": "mu", "\u03c1": "rho",
    "\u03c3": "sigma", "\u03c4": "tau", "\u03b7": "eta", "\u03c9": "omega",
    "\u03c6": "phi", "\u03b5": "epsilon",
}  # fmt: skip


def _plain_label(text: str) -> str:
    """A name as one key: "\\tau_{cw}", "τcw" and "tau_cw" alike."""
    spelled = "".join(_GREEK_NAMES.get(char, char) for char in text)
    return re.sub(r"[\s{}_\\]", "", spelled).lower()


def _by_label(
    cards: list[ReplyCard], values: list[FormalValue]
) -> list[tuple[ReplyCard, FormalValue]]:
    """Several values of one kind (two tensions): each card with the value its own label
    names, never by order: "T_2 = 30 N" written first is not the first asked (review)."""
    named = {_plain_label(value.symbol): value for value in values}
    return [
        (card, named[_plain_label(card.label)])
        for card in cards
        if card.label and _plain_label(card.label) in named
    ]


def _by_letter(
    cards: list[ReplyCard], values: Sequence[FormalValue]
) -> list[tuple[ReplyCard, FormalValue]] | None:
    if not (all(value.part for value in values) and any(card.letter for card in cards)):
        return None
    by_letter: dict[str, list[ReplyCard]] = {}
    for card in cards:
        by_letter.setdefault(card.letter, []).append(card)
    pairs = [
        (by_letter[value.part][0], value)
        for value in values
        if len(by_letter.get(value.part, [])) == 1
    ]
    if any(_kind(card.unit) != _kind(value.unit) for card, value in pairs if card.unit):
        return None
    return pairs


def held_to_server(
    text: str, values: Sequence[FormalValue], line: str, asked: Precision = RULE
) -> str:
    """``text`` with each card that disagrees with the server's value replaced by it, as
    the module docstring says; ``line`` goes directly above each replaced card. A card the
    question asked rounded (``asked``) is held to that rounding: "to 1 d.p." makes 0.3 A
    the server's 0.2727 A, not a slip."""
    numbers = written_numbers(text)
    changes: list[tuple[ReplyCard, FormalValue]] = []
    for card, value in _pairs(reply_cards(text), values):
        if not _read_it_so(value, numbers):
            logger.info("formal answer: the reply read a part another way")
            continue
        verdict = agrees(card, value, asked)
        logger.info("formal answer: a card agrees=%s", verdict is True)
        if verdict is False:
            changes.append((card, value))
    for card, value in sorted(changes, key=lambda change: -change[0].body_start):
        opener = text.rfind("\n", 0, card.body_start - 1) + 1
        named = f"{_card_label(text[card.body_start : card.body_end])}{value.card_value}"
        body = f"{UNCHECKED_ANSWER_MARKER}\n{named}\n"
        text = f"{text[:opener]}{line}\n\n{text[opener : card.body_start]}{body}{text[card.body_end :]}"
    return text
