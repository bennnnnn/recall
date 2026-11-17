"""The charges a question states, and a described amount held to one of them.

A field picture's amounts are the question's: "+3 nC and +2 nC" is drawn with two positive
charges sized 3 to 2, never a + and a - (review of feat/field-lines), and "4 nC" is no
charge of a question that says "4 cm". Each charge is read with its unit and its sign, a
charge in units of the physics table ("3 nC", "-2 μC") or a multiple of q ("+2q", "-q"); a
charge written with no sign is positive, as a question means it.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.modules.physics.givens import PHYSICS_UNITS
from app.services.law_binding.fit import read_givens
from app.services.number_text import fold_scientific

_CHARGE_DIMENSION = "[current]^1 * [time]^1"
_MINUS = frozenset({"-", "\u2212"})
# "+2q", "-q", "2q", "q": a multiple of q, never the q of "q1" or "quark". Each optional part
# is at most one character apart, so the scan stays linear.
_IN_Q = re.compile(r"(?<![\w.])([+\-\u2212])?(?:[ \t]?(\d+(?:\.\d+)?))?[ \t]?q(?!\w)")

# A sign word in a charge's own phrase ("a negative charge of 2 nC", "a 2 nC negative
# charge"), never a test charge's ("the force on a positive test charge").
_SIGN_IN_PHRASE = re.compile(r"\b(positive|negative)\b(?![ \t]+test\b)", re.IGNORECASE)
_SIGN_AFTER = re.compile(r"[ \t]*(?:point[ \t]+)?(positive|negative)\b(?![ \t]+test\b)", re.I)
_CLAUSE_END = re.compile(r"[.;:?!](?!\d)")

Kind = Literal["q", "unit"]


@dataclass(frozen=True)
class Charge:
    kind: Kind
    # Its size: a multiple of q, or coulombs.
    size: float
    sign: Literal[1, -1]
    # As the question writes it, without its sign: "2q", "q", "3 nC".
    written: str


def stated_charges(texts: Sequence[str]) -> list[Charge]:
    """The charges the first message that states any states, the user's last message first:
    a picture's amounts are that question's, never a number from another message."""
    for text in texts:
        found = _in_units(text) + _in_q(text)
        if found:
            return found
    return []


def _phrase_sign(text: str, start: int, end: int, floor: int) -> int | None:
    """The sign the words of a charge's own phrase name: the last sign word between the
    charge before it (or its clause's start) and its number, or one straight after it;
    None when they name none."""
    clause = max((m.end() for m in _CLAUSE_END.finditer(text, floor, start)), default=floor)
    words = _SIGN_IN_PHRASE.findall(text, clause, start)
    after = _SIGN_AFTER.match(text, end)
    word = words[-1] if words else after.group(1) if after else None
    return None if word is None else (1 if word.lower() == "positive" else -1)


def _signed(written: bool, named: int | None) -> Literal[1, -1]:
    """A charge's sign: negative when its minus or its own words say so."""
    return -1 if written or named == -1 else 1


def _in_units(text: str) -> list[Charge]:
    """Charges in units, read as the physics readers read a number: "3 x 10^-9 C" is 3e-9 C.
    A sign is the one written before the number, the number's own, or the one its own
    phrase names ("a negative charge of 2 nC")."""
    plain = fold_scientific(text)
    charges = []
    floor = 0
    for given in read_givens(plain, PHYSICS_UNITS):
        if given.dimension != _CHARGE_DIMENSION or given.si is None:
            continue
        unit_at = plain.find(given.unit, given.end)
        end = unit_at + len(given.unit) if 0 <= unit_at <= given.end + 2 else given.end
        before = plain[: given.start].rstrip()[-1:] in _MINUS
        named = _phrase_sign(plain, given.start, end, floor)
        written = f"{abs(given.value):g} {given.unit}"
        charges.append(
            Charge("unit", abs(given.si), _signed(before or given.si < 0, named), written)
        )
        floor = end
    return charges


def _in_q(text: str) -> list[Charge]:
    charges = []
    floor = 0
    for match in _IN_Q.finditer(text):
        size = float(match.group(2) or 1)
        written = "q" if size == 1 else f"{size:g}q"
        named = _phrase_sign(text, match.start(), match.end(), floor)
        charges.append(Charge("q", size, _signed(match.group(1) in _MINUS, named), written))
        floor = match.end()
    return charges


def described_charge(sign: Literal[1, -1], amount: str) -> Charge | None:
    """A described charge's amount, read by the readers that read a stated one ("+2q", "-q",
    "3 μC", "3e-9 C"), so the two never read differently. Its own sign, when it writes one,
    must be the charge's."""
    text = amount.strip()
    written_sign = text[:1] if text[:1] in ("+", *_MINUS) else None
    if written_sign is not None and (-1 if written_sign in _MINUS else 1) != sign:
        return None
    in_q = _in_q(text)
    found = in_q if in_q and _IN_Q.fullmatch(text) else _in_units(text)
    if len(found) != 1:
        return None
    (charge,) = found
    return Charge(charge.kind, charge.size, sign, charge.written)


def held_to(described: Sequence[Charge], stated: Sequence[Charge]) -> list[Charge] | None:
    """Each described charge matched to its own stated one, same kind, size and sign, in
    the question's own writing; None when any is not the question's."""
    left = list(stated)
    held = []
    for charge in described:
        match = next(
            (
                one
                for one in left
                if one.kind == charge.kind
                and one.sign == charge.sign
                and math.isclose(one.size, charge.size, rel_tol=1e-9)
            ),
            None,
        )
        if match is None:
            return None
        left.remove(match)
        held.append(match)
    return held


# "a positive and a negative charge", "two negative charges", "two equal positive charges":
# the signs a question names in words, each as many times as its count says.
_SIGN_WORD = re.compile(
    r"\b(?:(?P<count>two|three|2|3)[ \t]+(?:[a-z]+[ \t]+)?)?(?P<sign>positive|negative)\b"
    r"(?![ \t]+test\b)",
    re.IGNORECASE,
)
# The sentence that asks for the picture: the signs it and the sentences before it name are
# the charges'; an explanation after it ("how the arrows show the force on a positive test
# charge") names none.
_ASKS_TO_DRAW = re.compile(r"\b(?:draw|sketch|plot|illustrate)\b", re.IGNORECASE)
# "a)" or "(a)": where a part of the question starts.
_PART = re.compile(r"(?<![\w(])\(?([a-h])\)")
_COUNTS = {"two": 2, "three": 3, "2": 2, "3": 3}
_PLURAL = re.compile(r"[ \t]+(?:point[ \t]+)?charges\b", re.IGNORECASE)


def named_signs(texts: Sequence[str], part: str | None) -> tuple[list[int], bool] | None:
    """The signs the question names in words, in its part ``part`` when it has one, and
    whether they are the whole picture (one part, or a question with no parts) or only all
    the parts' together. None when the question names no sign."""
    for whole in texts:
        text = _through_the_request(whole)
        markers = list(_PART.finditer(text))
        if part is not None and markers:
            for index, marker in enumerate(markers):
                if marker.group(1) == part:
                    end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
                    signs = _signs(text[marker.end() : end])
                    if signs:
                        return signs, True
        signs = _signs(text)
        if signs:
            return signs, not markers
    return None


def _through_the_request(text: str) -> str:
    """``text`` up to the end of the sentence that asks for the picture, or all of it when
    no sentence does."""
    asks = _ASKS_TO_DRAW.search(text)
    if asks is None:
        return text
    end = _CLAUSE_END.search(text, asks.end())
    return text if end is None else text[: end.end()]


def _signs(text: str) -> list[int]:
    signs: list[int] = []
    for match in _SIGN_WORD.finditer(text):
        # A count names several charges ("two negative charges"); the 2 of "a 2 nC negative
        # point charge" is its amount.
        plural = _PLURAL.match(text, match.end()) is not None
        count = _COUNTS.get((match.group("count") or "").lower(), 1) if plural else 1
        signs += [1 if match.group("sign").lower() == "positive" else -1] * count
    return signs
