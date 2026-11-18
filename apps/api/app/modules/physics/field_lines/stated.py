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
_SIGN_IN_PHRASE = re.compile(r"\b(positive|negative)(?:ly)?\b(?![ \t]+test\b)", re.IGNORECASE)
_SIGN_AFTER = re.compile(
    r"[ \t]*(?:point[ \t]+)?(positive|negative)(?:ly)?\b(?![ \t]+test\b)", re.I
)
_CLAUSE_END = re.compile(r"[.;:?!](?!\d)")
_SENTENCE_END = re.compile(r"[.?!](?!\d)")
# A sign word for several charges: "negative charges of 3 nC and 2 nC".
_SHARED = re.compile(r"[ \t]+(?:point[ \t]+)?charges\b", re.IGNORECASE)
_TEST_CHARGE_BEFORE = re.compile(r"\btest[ \t]+charge[ \t,]*$", re.IGNORECASE)

Kind = Literal["q", "unit"]


@dataclass(frozen=True)
class Charge:
    kind: Kind
    # Its size: a multiple of q, or coulombs.
    size: float
    sign: Literal[1, -1]
    # As the question writes it, without its sign: "2q", "q", "3 nC".
    written: str


def stated_charges(texts: Sequence[str], part: str | None = None) -> list[Charge]:
    """The charges the picture's own question states: the message that asks for it, or the
    problem a follow-up points to, always the first text. An earlier turn's charges ("3.0 C
    and 2.0 C" before "draw a positive charge") are never this picture's, nor another
    part's: part a's picture holds only the question's stem and part a ("a) a positive
    charge b) a +3 nC charge" sizes no charge of part a)."""
    text = texts[0] if texts else ""
    span = _part_span(text, part)
    if span is not None:
        stem, start, end = span
        text = f"{text[:stem]} {text[start:end]}"
    return _in_units(text) + _in_q(text)


def part_named(text: str, part: str | None) -> bool:
    """A question with lettered parts names the picture's part among them; one with none
    takes a picture with no part."""
    letters = {marker.group(1) for marker in _PART.finditer(text)}
    if len(letters) < 2:
        return True
    return part is not None and part in letters


def _part_span(text: str, part: str | None) -> tuple[int, int, int] | None:
    """Where ``text``'s stem ends and part ``part``'s own words start and end, when it has
    lettered parts and that one; None otherwise. The one slicing both the charges and the
    named signs of a part read."""
    markers = list(_PART.finditer(text))
    for index, marker in enumerate(markers):
        if part is not None and marker.group(1) == part:
            end = markers[index + 1].start() if index + 1 < len(markers) else len(text)
            return markers[0].start(), marker.end(), end
    return None


@dataclass(frozen=True)
class _Named:
    """The sign a charge's own words name, and whether they name it for several charges
    ("two negative charges of 3 nC and 2 nC"), so the charges after share it."""

    sign: int | None
    shared: bool = False


def _sign_of(
    text: str, start: int, end: int, floor: int, carried: _Named | None
) -> tuple[int | None, _Named | None]:
    """A charge's named sign, or the one a plural phrase before it in its clause gave the
    charges it lists ("two negative point charges of 2q and q"); and what the next charge
    inherits. Both readers, in units and in q, read signs so."""
    if _CLAUSE_END.search(text, floor, start):
        carried = None
    named = _phrase_sign(text, start, end, floor)
    if named.sign is not None:
        return named.sign, named if named.shared else None
    return (carried.sign if carried else None), carried


def _phrase_sign(text: str, start: int, end: int, floor: int) -> _Named:
    """The sign the words of a charge's own phrase name: the last sign word between the
    charge before it (or its clause's start) and its number, or one straight after it."""
    clause = max((m.end() for m in _CLAUSE_END.finditer(text, floor, start)), default=floor)
    words = list(_SIGN_IN_PHRASE.finditer(text, clause, start))
    after = _SIGN_AFTER.match(text, end)
    found = words[-1] if words else after
    if found is None:
        return _Named(None)
    shared = _SHARED.match(text, found.end()) is not None
    return _Named(1 if found.group(1).lower() == "positive" else -1, shared)


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
    carried: _Named | None = None
    for given in read_givens(plain, PHYSICS_UNITS):
        if given.dimension != _CHARGE_DIMENSION or given.si is None:
            continue
        unit_at = plain.find(given.unit, given.end)
        end = unit_at + len(given.unit) if 0 <= unit_at <= given.end + 2 else given.end
        before = plain[: given.start].rstrip()[-1:] in _MINUS
        named, carried = _sign_of(plain, given.start, end, floor, carried)
        written = f"{abs(given.value):g} {given.unit}"
        charges.append(
            Charge("unit", abs(given.si), _signed(before or given.si < 0, named), written)
        )
        floor = end
    return charges


def _in_q(text: str) -> list[Charge]:
    charges = []
    floor = 0
    carried: _Named | None = None
    for match in _IN_Q.finditer(text):
        # "a positive test charge q" names the probe, never a source.
        if _TEST_CHARGE_BEFORE.search(text, max(0, match.start() - 16), match.start()):
            continue
        size = float(match.group(2) or 1)
        written = "q" if size == 1 else f"{size:g}q"
        named, carried = _sign_of(text, match.start(), match.end(), floor, carried)
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
    r"\b(?:(?P<count>two|three|2|3)[ \t]+(?:[a-z]+[ \t]+)?)?(?P<sign>positive|negative)(?:ly)?\b"
    r"(?![ \t]+test\b)",
    re.IGNORECASE,
)
# A sentence that asks for an explanation, not the setup: its sign words name no charge.
_EXPLAINS = re.compile(
    r"\s*(?:\(?[a-h]\)\s*)?(?:explain|describe|why|how|discuss|compare|state|suggest|justify)\b",
    re.IGNORECASE,
)
# "a)" or "(a)": where a part of the question starts.
_PART = re.compile(r"(?<![\w(])\(?([a-h])\)")
_COUNTS = {"two": 2, "three": 3, "2": 2, "3": 3}
_PLURAL = re.compile(r"[ \t]+(?:point[ \t]+)?charges\b", re.IGNORECASE)


def named_signs(texts: Sequence[str], part: str | None) -> tuple[list[int], bool] | None:
    """The signs the picture's question (the first text) names in words, in its part
    ``part`` when it has one, and whether they are the whole picture (one part, or a
    question with no parts) or only all the parts' together. None when it names no sign."""
    for whole in texts[:1]:
        span = _part_span(whole, part)
        if span is not None:
            _stem, start, end = span
            signs = _signs(_setup_sentences(whole[start:end]))
            if signs:
                return signs, True
        text = _setup_sentences(whole)
        signs = _signs(text)
        if signs:
            return signs, _PART.search(text) is None
    return None


# Which plate a question says is charged how: "the top plate is positive", "a negative
# lower plate", "the positive plate at the bottom".
_PLATE_SIDE = re.compile(
    r"\b(?P<side1>top|upper|bottom|lower)[ \t]+plate\b[^.;?!]{0,30}?"
    r"\b(?P<sign1>positive|negative)(?:ly)?\b"
    r"|\b(?P<sign2>positive|negative)(?:ly[ \t]+charged)?[ \t]+(?P<side2>top|upper|bottom|lower)"
    r"[ \t]+plate\b"
    r"|\b(?P<sign3>positive|negative)(?:ly[ \t]+charged)?[ \t]+plate\b[^.;?!]{0,20}?"
    r"\b(?P<side3>top|bottom)\b",
    re.IGNORECASE,
)
_PLATES = re.compile(r"\bplates?\b|\bcapacitor\b", re.IGNORECASE)
_TOP = frozenset({"top", "upper"})


def plates_of(text: str, positive: str, part: str | None = None) -> bool:
    """``text`` names plates, and its words put the positive one where the description
    does ("top" or "bottom"), or put it nowhere: in the picture's own part ("when: a) the
    top plate is positive b) the top plate is negative"), else in the question's stem."""
    if _PLATES.search(text) is None:
        return False
    span = _part_span(text, part)
    segments = [text] if span is None else [text[span[1] : span[2]], text[: span[0]]]
    said = next((list(_PLATE_SIDE.finditer(s)) for s in segments if _PLATE_SIDE.search(s)), [])
    for match in said:
        side = next(match.group(f"side{i}") for i in (1, 2, 3) if match.group(f"side{i}"))
        sign = next(match.group(f"sign{i}") for i in (1, 2, 3) if match.group(f"sign{i}"))
        top = side.lower() in _TOP
        top_positive = top == (sign.lower() == "positive")
        if top_positive != (positive == "top"):
            return False
    return True


def _setup_sentences(text: str) -> str:
    """``text`` without its explanation sentences ("Explain how the arrows show the force
    on a positive test charge"), every setup sentence kept wherever it stands ("Draw the
    electric field pattern. One charge is positive and the other is negative."). A colon or
    a semicolon ends no sentence, and a test charge's sign is never a source's
    (``_SIGN_WORD``)."""
    kept: list[str] = []
    start = 0
    for match in [*_SENTENCE_END.finditer(text), None]:
        end = match.end() if match is not None else len(text)
        sentence = text[start:end]
        if sentence.strip() and not _EXPLAINS.match(sentence):
            kept.append(sentence)
        start = end
    return "".join(kept)


def _signs(text: str) -> list[int]:
    signs: list[int] = []
    for match in _SIGN_WORD.finditer(text):
        # A count names several charges ("two negative charges"); the 2 of "a 2 nC negative
        # point charge" is its amount.
        plural = _PLURAL.match(text, match.end()) is not None
        count = _COUNTS.get((match.group("count") or "").lower(), 1) if plural else 1
        signs += [1 if match.group("sign").lower() == "positive" else -1] * count
    return signs
