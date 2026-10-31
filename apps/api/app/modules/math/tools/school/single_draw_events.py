"""The event of one roll or one draw, read whole.

The event is the outcomes the question names, joined by "or", with a "not" before
them: "not getting a sum 5 or 9" is every roll of two dice but the 8 that make 5 or 9.
Every other word must be one that cannot change the event: the setup ("a pair of
fair dice is tossed"), the request ("what is the probability"), the dice or the deck.
A word the reader has no meaning for ("and a double", "given that", "the product",
"neither") declines the question, so a card never answers part of the event.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A multiple-choice list after the question: "a. 2/9  b. 8/9", "(A) 1/6 (B) 1/3".
_CHOICES = re.compile(r"(?:^|\s)\(?[aA][.)]\s*\S.*?\s\(?[bB][.)]\s*\S", re.S)
_COMPARE = (
    r"(?:(?:greater|more|bigger|larger|higher|less|smaller|lower)\s+than|at\s+least|at\s+most"
    r"|exactly)"
)
_NOT = (
    r"(?:(not)\s+(?:(?:getting|get|rolling|roll|throwing|throw|obtaining|obtain|drawing|draw"
    r"|picking|pick|selecting|select)\s+)?)?"
)
_SUM_VALUE = rf"(?:(?:a\s+)?(?:sum|total)\s+(?:of\s+)?)?(?:{_COMPARE}\s+)?\d{{1,2}}"
_SUM_EVENT = re.compile(
    rf"\b{_NOT}(?:(?:a|an|the)\s+)?(?:sum|total)"
    r"(?:\s+of\s+(?:the\s+)?(?:two\s+)?(?:numbers|faces|scores)"
    r"(?:\s+(?:on|shown\s+on)\s+(?:the\s+|both\s+)?(?:two\s+)?dice)?)?"
    r"(?:\s+(?:is|will\s+be|equals|of|is\s+equal\s+to|equal\s+to))?(?:\s+(not))?"
    rf"\s+({_SUM_VALUE}(?:\s*,\s*{_SUM_VALUE})*(?:\s*,?\s+or\s+{_SUM_VALUE})?)(?!\d|\.\d)",
    re.IGNORECASE,
)
_DOUBLES_EVENT = re.compile(rf"\b{_NOT}(?:(?:a|an)\s+)?doubles?\b", re.IGNORECASE)
_FACE = (
    rf"(?:\b(?:an?\s+)?(?:(?:even|odd|prime)(?:\s+numbers?)?|(?:number\s+)?{_COMPARE}\s+(?:an?\s+)?"
    r"[1-6]|multiple\s+of\s+[1-6]|(?<![\d.])[1-6](?!\d|\.\d)))"
)
_FACE_EVENT = re.compile(
    rf"{_NOT}(?:the\s+number\s+is\s+(?:(not)\s+)?)?({_FACE}(?:(?:\s*,\s*|\s+or\s+){_FACE})*)",
    re.IGNORECASE,
)
_FACE_PART = re.compile(
    rf"\b(even|odd|prime)\b|({_COMPARE})\s+(?:an?\s+)?([1-6])|multiple\s+of\s+([1-6])|([1-6])",
    re.IGNORECASE,
)
_SUIT = r"(?:heart|spade|club|diamond)s?"
_CARD = (
    r"(?:\b(?:(?:an?|the)\s+)?(?:(?:red|black)\s+)?(?:(?:king|queen|jack|ace)s?(?:\s+of\s+"
    rf"{_SUIT})?|(?:face|picture|court)\s+cards?|{_SUIT})"
    r"|\b(?:(?:an?|the)\s+)?(?:red|black)\s+cards?)"
)
_CARD_EVENT = re.compile(rf"{_NOT}({_CARD}(?:\s+or\s+{_CARD})*)\b", re.IGNORECASE)
_CARD_PART = re.compile(
    r"(?:(red|black)\s+)?(?:(king|queen|jack|ace)s?(?:\s+of\s+(heart|spade|club|diamond)s?)?"
    r"|(face|picture|court)\s+cards?|(heart|spade|club|diamond)s?|cards?)",
    re.IGNORECASE,
)

# The setup each kind of draw is stated with, read before the event is looked for.
_DICE_SETUP = re.compile(
    r"\b(?:two|2|a\s+pair\s+of)\s+(?:fair\s+|unbiased\s+)?(?:(?:six|6)[- ]sided\s+)?di(?:c)?e\b",
    re.IGNORECASE,
)
_DIE_SETUP = re.compile(r"\b(?:six|6)[- ]sided\b", re.IGNORECASE)
_DECK_SETUP = re.compile(
    r"\b(?:deck|pack)\s+of\s+52\s+(?:playing\s+)?cards\b|\b52[- ](?:playing\s+)?cards?\b"
    r"|\b52[- ]card\b",
    re.IGNORECASE,
)

# Words that cannot change which outcomes are favourable.
_FILLER = frozenset(
    """
    a an the of that this is are was were be will what s find calculate compute determine
    work out give write probability chance likelihood getting get gets got rolling roll rolls
    rolled throwing throw throws thrown tossing toss tosses tossed cast casting obtaining obtain
    obtained drawing draw draws drawn picking pick picks picked selecting select selected
    choosing choose chosen taking take taken showing show shows shown landing land lands up if
    when with on from in at random randomly once same time simultaneously together fair unbiased
    standard ordinary single one it its i you we he she they number numbers face faces result
    outcome your answer as fraction simplest form decimal
    """.split()
)
_DICE_WORDS = frozenset({"two", "pair", "dice", "die"})
_DIE_WORDS = frozenset({"die"})
_DECK_WORDS = frozenset({"card", "cards", "deck", "pack", "playing", "shuffled", "well", "full"})
_RED = ("heart", "diamond")
_RANK_VALUE = {"jack": 11, "queen": 12, "king": 13, "ace": 1}


@dataclass(frozen=True)
class DrawEvent:
    """Favourable outcomes of all, and what the block writes about them."""

    favourable: int
    total: int
    outcome: str


def _question(text: str) -> str:
    """The question without a multiple-choice list after it."""
    choices = _CHOICES.search(text)
    return text[: choices.start()] if choices else text


def _whole(text: str, spans: list[tuple[int, int]], words: frozenset[str]) -> bool:
    """True when nothing outside the read spans can change the event."""
    rest = list(text.lower())
    for start, end in spans:
        rest[start:end] = " " * (end - start)
    leftover = re.findall(r"[a-z]+|\d+", "".join(rest))
    return all(word in _FILLER or word in words for word in leftover)


def _sums(values: str) -> set[int]:
    sums: set[int] = set()
    for part in re.finditer(rf"(?:({_COMPARE})\s+)?(\d{{1,2}})", values, re.IGNORECASE):
        relation, number = " ".join((part.group(1) or "").lower().split()), int(part.group(2))
        sums |= {total for total in range(2, 13) if _holds(total, relation, number)}
    return sums


def _holds(value: int, relation: str, bound: int) -> bool:
    if relation.endswith("than"):
        return value > bound if relation.split()[0] in _ABOVE else value < bound
    if relation == "at least":
        return value >= bound
    if relation == "at most":
        return value <= bound
    return value == bound


_ABOVE = frozenset({"greater", "more", "bigger", "larger", "higher"})


def two_dice_event(text: str) -> DrawEvent | None:
    question = _question(text)
    setup = [match.span() for match in _DICE_SETUP.finditer(question)]
    if not setup:
        return None
    sums = list(_SUM_EVENT.finditer(question))
    doubles = list(_DOUBLES_EVENT.finditer(question))
    if len(sums) + len(doubles) != 1:
        return None
    event = (sums or doubles)[0]
    if not _whole(question, [*setup, event.span()], _DICE_WORDS):
        return None
    negated = bool(event.group(1)) or (bool(event.group(2)) if sums else False)
    if sums:
        if event.group(1) and event.group(2):
            return None
        totals = _sums(event.group(3))
        if not totals:
            return None  # "a sum of 13": no roll makes it, which is the model's to explain
        count = sum(6 - abs(total - 7) for total in totals)
        outcome = "sum:" + ",".join(str(total) for total in sorted(totals))
    else:
        count, outcome = 6, "doubles"
    if negated:
        return DrawEvent(36 - count, 36, f"not|{outcome}")
    return DrawEvent(count, 36, outcome)


def one_die_event(text: str) -> DrawEvent | None:
    question = _question(text)
    setup = [match.span() for match in _DIE_SETUP.finditer(question)]
    events = list(_FACE_EVENT.finditer(question))
    if len(events) != 1:
        return None
    event = events[0]
    if not _whole(question, [*setup, event.span()], _DIE_WORDS):
        return None
    if event.group(1) and event.group(2):
        return None
    faces: set[int] = set()
    for part in _FACE_PART.finditer(event.group(3)):
        kind, relation, bound, factor, face = part.groups()
        if kind:
            faces |= {"even": {2, 4, 6}, "odd": {1, 3, 5}, "prime": {2, 3, 5}}[kind.lower()]
        elif relation:
            words = " ".join(relation.lower().split())
            faces |= {value for value in range(1, 7) if _holds(value, words, int(bound))}
        elif factor:
            faces |= {value for value in range(1, 7) if value % int(factor) == 0}
        else:
            faces.add(int(face))
    if event.group(1) or event.group(2):
        faces = set(range(1, 7)) - faces
    if not faces or len(faces) == 6:
        return None  # an impossible or a certain roll is the model's to explain
    return DrawEvent(len(faces), 6, ", ".join(str(face) for face in sorted(faces)))


def card_event(text: str) -> DrawEvent | None:
    question = _question(text)
    setup = [match.span() for match in _DECK_SETUP.finditer(question)]
    events = list(_CARD_EVENT.finditer(question))
    if len(events) != 1:
        return None
    event = events[0]
    if not _whole(question, [*setup, event.span()], _DECK_WORDS):
        return None
    cards: set[tuple[int, str]] = set()
    labels: list[str] = []
    for part in _CARD_PART.finditer(event.group(2)):
        colour, rank, rank_suit, face, suit = part.groups()
        if not (colour or rank or face or suit):
            continue
        chosen = {
            (value, name)
            for value in range(1, 14)
            for name in ("heart", "diamond", "spade", "club")
            if (not colour or (name in _RED) == (colour.lower() == "red"))
            and (not rank or value == _RANK_VALUE[rank.lower()])
            and (not (rank_suit or suit) or name == (rank_suit or suit or "").lower())
            and (not face or value > 10)
        }
        cards |= chosen
        labels.append(_card_label(colour, rank, rank_suit, face, suit))
    if not labels:
        return None
    label = " or ".join(labels)
    if event.group(1):
        return DrawEvent(52 - len(cards), 52, f"not|{label}")
    return DrawEvent(len(cards), 52, label)


def _card_label(
    colour: str | None, rank: str | None, rank_suit: str | None, face: str | None, suit: str | None
) -> str:
    """``the king of hearts``, ``red kings``, ``face cards``, ``hearts``, ``red cards``."""
    tint = f"{colour.lower()} " if colour else ""
    if rank and rank_suit:
        return f"the {rank.lower()} of {rank_suit.lower()}s"
    if rank:
        return f"{tint}{rank.lower()}s"
    if face:
        return f"{tint}face cards"
    if suit:
        return f"{suit.lower()}s"
    return f"{tint}cards"
