"""The quantities a question states, and a described value held to one of them.

A scene a reply describes is drawn from the question's own numbers. Each value it names,
with its unit, must be one the question states, of the kind the scene's part takes, each
used once. Every other quantity the question states must be one the scene can leave aside
(a slope's length beside the block on it), or the question is another situation than the
scene draws: a pushing force, a pulley's moment of inertia, a time the scene would contradict.
A quantity is a number with a unit, or a decimal a pure number may be (a coefficient, an
index); a bare whole number is no quantity ("Question 3", "2 significant figures").
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.modules.physics.givens import PHYSICS_UNITS
from app.services.latex_markup import without_markup
from app.services.law_binding.fit import read_givens
from app.services.law_binding.givens import Given
from app.services.number_text import fold_scientific

# Where a clause ends: a speed belongs to a mass in its own clause.
_CLAUSE_END = re.compile(r"[.;:?!](?!\d)")
# Where a sentence ends: a full stop not inside a number ("1.5").
_SENTENCE_END = re.compile(r"[.;?!](?!\d)")
# "the 5 kg mass": the noun after a value written straight after "the".
_RESTATED = re.compile(r"\bthe[ \t]+$", re.IGNORECASE)
_NOUN = re.compile(r"[ \t]*([a-z]{3,})", re.IGNORECASE)
_WORD = re.compile(r"[a-z]{3,}", re.IGNORECASE)
# The harmonic a question names: "third harmonic", "3rd harmonic", "n = 3", "fundamental".
_ORDINAL = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6}
_HARMONIC = re.compile(
    r"\b(first|second|third|fourth|fifth|sixth|[1-6](?:st|nd|rd|th))[ \t]+harmonic\b"
    r"|\bn[ \t]*=[ \t]*([1-6])\b|\b(fundamental)\b",
    re.IGNORECASE,
)


def _plain(text: str) -> str:
    """The text as the physics readers read it: markup off, "5.97 x 10^24" one number."""
    return fold_scientific(without_markup(text))


def _dimension(sample: str) -> str | None:
    if not sample:
        return None
    read = read_givens(f"1 {sample}", PHYSICS_UNITS)
    return read[0].dimension if read else None


@dataclass
class Stated:
    """The quantities one question states, the ones a described scene used taken out."""

    text: str
    left: list[Given]
    taken: list[Given] = field(default_factory=list)

    @classmethod
    def of(cls, text: str) -> Stated:
        plain = _plain(text)
        quantities = [
            given
            for given in read_givens(plain, PHYSICS_UNITS)
            if given.dimension is not None or "." in plain[given.start : given.end]
        ]
        return cls(plain, quantities)

    def take(self, written: str, sample: str) -> Given | None:
        """The stated quantity ``written`` names ("20 m/s", "0.25"), of the kind ``sample``'s
        unit is ("m/s"; "" for a pure number), taken so no other part uses it."""
        read = list(read_givens(_plain(written), PHYSICS_UNITS))
        if len(read) != 1:
            return None
        (value,) = read
        kind = _dimension(sample)
        if value.dimension != kind:
            return None
        for given in self.left:
            if given.dimension == kind and _same(given, value):
                self.left.remove(given)
                self.taken.append(given)
                return given
        return None

    def take_air(self) -> Given | None:
        """A stated index of 1.00, air's, which a refraction from air need not name."""
        for given in self.left:
            if given.dimension is None and math.isclose(given.value, 1.0):
                self.left.remove(given)
                self.taken.append(given)
                return given
        return None

    def leaves_out(self, tolerated: Sequence[str]) -> bool:
        """A stated quantity no part used, beyond the ones the scene can leave aside (one
        of each kind ``tolerated`` names: a slope's length, a bob's mass)."""
        spare = [_dimension(sample) for sample in tolerated]
        for given in self.left:
            if self._restated(given):
                continue
            if given.dimension in spare:
                spare.remove(given.dimension)
                continue
            return True
        return False

    def _restated(self, given: Given) -> bool:
        """ "the speed of the 5 kg mass": a value straight after "the", followed by the noun
        the same value's first statement names ("masses of 3 kg and 5 kg", "a 5 kg mass"),
        is a body the scene already holds. "over the 2 kg pulley" beside "masses of 2 kg
        and 4 kg" is another body."""
        if not _RESTATED.search(self.text[max(0, given.start - 6) : given.start]):
            return False
        noun = _NOUN.match(self.text, self._after(given))
        if noun is None:
            return False
        name = noun.group(1).lower()
        for used in self.taken:
            if not _same(used, given):
                continue
            # The words naming the first statement: just before it, or just after its unit.
            beside = self.text[max(0, used.start - 20) : used.start]
            beside += " " + self.text[self._after(used) : self._after(used) + 12]
            if any(_one_noun(word.lower(), name) for word in _WORD.findall(beside)):
                return True
        return False

    def _after(self, given: Given) -> int:
        """Where the words after ``given``'s unit start."""
        at = self.text.find(given.unit, given.end) if given.unit else -1
        return given.end if at < 0 or at > given.end + 2 else at + len(given.unit)

    def sentence(self, given: Given) -> str:
        """The sentence ``given`` is written in."""
        start = max((m.end() for m in _SENTENCE_END.finditer(self.text, 0, given.start)), default=0)
        end_match = _SENTENCE_END.search(self.text, given.end)
        return self.text[start : end_match.start() if end_match else len(self.text)]

    def lengths_left(self) -> list[Given]:
        """The stated lengths no part used ("a wavelength of 0.8 m")."""
        kind = _dimension("m")
        return [given for given in self.left if given.dimension == kind]

    def owner(self, value: Given, masses: Sequence[Given]) -> Given | None:
        """The mass whose body ``value`` (a speed) belongs to: the last of ``masses`` written
        before it in its own clause, with no other mass between; None when no mass is."""
        before = [m for m in masses if m.start < value.start]
        if not before:
            return None
        nearest = max(before, key=lambda m: m.start)
        if _CLAUSE_END.search(self.text, nearest.end, value.start):
            return None
        return nearest

    def harmonics(self) -> set[int]:
        """The harmonics the question names: "third harmonic", "n = 3", "fundamental"."""
        named: set[int] = set()
        for match in _HARMONIC.finditer(self.text):
            word, number, fundamental = match.groups()
            if fundamental:
                named.add(1)
            elif number:
                named.add(int(number))
            elif word:
                lower = word.lower()
                named.add(_ORDINAL[lower] if lower in _ORDINAL else int(lower[0]))
        return named


def _one_noun(word: str, name: str) -> bool:
    """ "masses" and "mass", "balls" and "ball": one noun, singular or plural."""
    return word == name or word in (f"{name}s", f"{name}es") or name in (f"{word}s", f"{word}es")


def _same(one: Given, other: Given) -> bool:
    if one.si is None or other.si is None:
        return one.si is None and other.si is None and math.isclose(one.value, other.value)
    return math.isclose(one.si, other.si, rel_tol=1e-9)


def stated_texts(texts: Sequence[str]) -> Stated:
    """The question's quantities: the user's message, or on a follow-up ("draw it") the
    first earlier message that states any, the last first."""
    for text in texts:
        stated = Stated.of(text)
        if any(given.dimension is not None for given in stated.left):
            return stated
    return Stated.of(texts[0] if texts else "")


def states_quantities(text: str) -> bool:
    """The message states a quantity with a unit the physics readers read."""
    return any(given.dimension is not None for given in Stated.of(text).left)
