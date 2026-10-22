"""One roll or one draw: the probability is favourable outcomes over all outcomes.

Two dice (36 outcomes), one die (6), one card from a standard deck (52).
``probability of rolling a sum of 7 with two dice`` -> 6/36 = 1/6, with the six
pairs listed.
"""

from __future__ import annotations

import re
from dataclasses import replace
from fractions import Fraction

from app.modules.math.schemas import MathIntent
from app.modules.math.tools.block import VerifiedMathBlock, finish_with_answer
from app.services.workout import math_line

_CHANCE = re.compile(r"\b(?:probability|chance|likelihood)\b", re.IGNORECASE)
_TWO_DICE = re.compile(r"\b(?:two|2|a\s+pair\s+of)\s+(?:fair\s+)?(?:dice|die)\b", re.IGNORECASE)
_DICE_SUM = re.compile(
    r"\b(?:sum|total)\s+(?:of\s+|is\s+|equal\s+to\s+|equals\s+)?(\d{1,2})\b", re.IGNORECASE
)
_DOUBLE = re.compile(r"\b(?:a\s+)?doubles?\b", re.IGNORECASE)
_ONE_DIE = re.compile(
    r"\b(?:a|one|single)\s+(?:fair\s+|six-sided\s+|standard\s+)?die\b", re.IGNORECASE
)
_DECK = re.compile(
    r"\b(?:standard\s+|ordinary\s+|well-shuffled\s+)?(?:deck|pack)(?:\s+of\s+(?:52\s+)?cards)?\b"
    r"|\b52\s+cards\b",
    re.IGNORECASE,
)
_RANKS = {"ace": "aces", "king": "kings", "queen": "queens", "jack": "jacks"}
_SUITS = ("heart", "spade", "club", "diamond")


def _die_face_count(lower: str) -> tuple[int, str] | None:
    """Favourable faces of one die, and what they are."""
    if re.search(r"\beven\b", lower):
        return 3, "2, 4, 6"
    if re.search(r"\bodd\b", lower):
        return 3, "1, 3, 5"
    if re.search(r"\bprime\b", lower):
        return 3, "2, 3, 5"
    bound = re.search(
        r"\b(greater\s+than|more\s+than|less\s+than|at\s+least|at\s+most)\s+(?:a\s+)?([1-6])\b",
        lower,
    )
    if bound is not None:
        relation, value = bound.group(1), int(bound.group(2))
        faces = [
            face
            for face in range(1, 7)
            if (relation.startswith(("greater", "more")) and face > value)
            or (relation.startswith("less") and face < value)
            or (relation == "at least" and face >= value)
            or (relation == "at most" and face <= value)
        ]
        return len(faces), ", ".join(str(face) for face in faces) or "none"
    face = re.search(
        r"\b(?:rolling|roll|getting|get|throwing|showing)\s+(?:a|an)\s+([1-6])\b", lower
    )
    if face is not None:
        return 1, face.group(1)
    return None


def _card_count(lower: str) -> tuple[int, str] | None:
    """Favourable cards in a 52-card deck, and what they are."""
    colour = re.search(r"\b(red|black)\b", lower)
    for rank, plural in _RANKS.items():
        if re.search(rf"\b{rank}s?\b", lower):
            suit = next((s for s in _SUITS if re.search(rf"\bof\s+{s}s\b", lower)), None)
            if suit is not None:
                return 1, f"the {rank} of {suit}s"
            if colour is not None:
                return 2, f"{colour.group(1)} {plural}"
            return 4, plural
    if re.search(r"\b(?:face|picture|court)\s+cards?\b", lower):
        return (6, f"{colour.group(1)} face cards") if colour else (12, "face cards")
    suit = next((s for s in _SUITS if re.search(rf"\b{s}s?\b", lower)), None)
    if suit is not None:
        return 13, f"{suit}s"
    if colour is not None and re.search(r"\bcards?\b", lower):
        return 26, f"{colour.group(1)} cards"
    return None


def extract_single_draw_intent(cleaned: str) -> MathIntent | None:
    if len(cleaned) > 300 or not _CHANCE.search(cleaned):
        return None
    lower = cleaned.lower()
    if re.search(r"\b(?:and\s+then|then|twice|again|without\s+replacement|times)\b", lower):
        return None
    favourable: int | None = None
    total = 0
    outcome = ""
    if _TWO_DICE.search(cleaned):
        total = 36
        dice_sum = _DICE_SUM.search(cleaned)
        if dice_sum is not None and 2 <= int(dice_sum.group(1)) <= 12:
            target = int(dice_sum.group(1))
            favourable, outcome = 6 - abs(target - 7), f"sum:{target}"
        elif _DOUBLE.search(cleaned):
            favourable, outcome = 6, "doubles"
    elif _DECK.search(cleaned) or re.search(r"\bcards?\b", lower):
        counted = _card_count(lower)
        if counted is not None and _DECK.search(cleaned):
            total = 52
            favourable, outcome = counted
    elif _ONE_DIE.search(cleaned) or re.search(r"\broll(?:ing)?\s+(?:a|an)\s+[1-6]\b", lower):
        counted = _die_face_count(lower)
        if counted is not None:
            total = 6
            favourable, outcome = counted
    if favourable is None or not total:
        return None
    return MathIntent(
        kind="probability",
        school_op="single_draw",
        combo_k=favourable,
        combo_n=total,
        trial_outcome=outcome,
        operation="solve",
    )


def probability_answer(probability: Fraction) -> str:
    """``\\frac{1}{4} = 0.25`` when the decimal ends, ``\\frac{1}{6} \\approx 0.1667`` when not."""
    exact = _fraction_tex(probability)
    if probability.denominator == 1:
        return exact
    denominator = probability.denominator
    for prime in (2, 5):
        while denominator % prime == 0:
            denominator //= prime
    decimal = float(probability)
    if denominator == 1:
        return f"{exact} = {decimal:g}"
    return rf"{exact} \approx {decimal:.4g}"


def _fraction_tex(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return rf"\frac{{{value.numerator}}}{{{value.denominator}}}"


def _dice_pairs(target: int) -> str:
    pairs = [f"({a}, {target - a})" for a in range(1, 7) if 1 <= target - a <= 6]
    return ", ".join(pairs)


def single_draw_block(intent: MathIntent, lines: list[str]) -> VerifiedMathBlock | None:
    favourable, total = intent.combo_k, intent.combo_n
    if favourable is None or not total:
        return None
    probability = Fraction(favourable, total)
    answer = probability_answer(probability)
    outcome = intent.trial_outcome or ""
    rows: list[str] = []
    if outcome.startswith("sum:"):
        target = int(outcome.split(":", 1)[1])
        rows.append(
            math_line(
                rf"\text{{{_dice_pairs(target)}}}",
                f"the {favourable} ways two dice make {target}, of 36",
            )
        )
    elif outcome == "doubles":
        rows.append(math_line(r"\text{(1, 1), (2, 2), ..., (6, 6)}", "6 doubles of 36"))
    elif total == 6:
        rows.append(math_line(rf"\text{{{outcome}}}", f"{favourable} of the 6 faces"))
    else:
        rows.append(math_line(rf"{favourable} \text{{ {outcome}}}", "in a deck of 52"))
    # The simplified value is the answer's, on its own line.
    rows.append(math_line(rf"P = \frac{{{favourable}}}{{{total}}}", "favourable over all outcomes"))
    lines.append(f"P = {favourable}/{total} = {probability}")
    block = finish_with_answer(lines, answer)
    shown = "  \n".join(rows)
    return replace(block, worked_reply=f"{shown}\n\n```answer\n{answer}\n```\n")
