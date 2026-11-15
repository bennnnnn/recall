"""What a question states, as a ```draw description is checked against it.

A description's numbers are the question's own, with their sign, unit and role
(``figure.grounding``); its points are coordinates the question writes ("P(4, -3, 5)", a
vector "(2, 1, 3)" or "2i + j + 3k"); its letters are ones the question or the reply's own
working writes ("let r be the radius"); its shapes are ones the question names
(``figure.shape_names``).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction

from app.modules.math.figure.grounding import (
    ASSIGNED,
    Written,
    changing_values,
    own_texts,
    written_numbers,
    written_pairs,
)

Triple = tuple[Fraction, Fraction, Fraction]
Point = tuple[Fraction, ...]

# A bracketed triple: "(4, -3, 5)", "<2, 5, 6>", "⟨2, 5, 6⟩".
_TRIPLE = re.compile(r"[(<⟨]([^()<>⟨⟩]*?,[^()<>⟨⟩]*?,[^()<>⟨⟩]*?)[)>⟩]")
# One term of a vector written with unit vectors: "2i", "- j", "+ 3.5k", "-7\hat{k}".
_UNIT_TERM = re.compile(
    r"([+\-\u2212]?)\s*(\d+(?:\.\d+)?)?\s*\*?\s*(?:\\hat\{|\\mathbf\{|\\vec\{)?([ijk])\}?(?![A-Za-z])"
)
_UNIT_RUN = re.compile(
    r"(?<![A-Za-z\\])(?:[+\-\u2212]?\s*(?:\d+(?:\.\d+)?)?\s*\*?\s*(?:\\hat\{|\\mathbf\{|\\vec\{)?"
    r"[ijk]\}?(?![A-Za-z])\s*){2,3}"
)
# A letter standing alone, as a variable: "r", "h", "A", "x'" (never one inside a word or a
# LaTeX command).
_LETTER = re.compile(r"(?<![A-Za-z\\])([A-Za-z])([\u2032']?)(?![A-Za-z])")
_CAPITALS = re.compile(r"(?<![A-Za-z\\])[A-Z]{1,12}(?![A-Za-z])")
# "a", "A" and "I" before a word are English ("a window", "A ladder", "I think").
_ENGLISH = frozenset("aAI")
_GREEK = {
    "θ": ("θ", "\\theta"),
    "\u03b1": ("\u03b1", "\\alpha"),
    "β": ("β", "\\beta"),
    "φ": ("φ", "\\phi", "\\varphi"),
}
# A coefficient written against a letter, as a term: the "3r" of "h = 3r" ("12 m" is a length).
_TERM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\*?([A-Za-z])(?![A-Za-z])")
# A letter set equal to a multiple of another: "h = 3r", "w = 2x".
_RELATION = re.compile(r"(?<![A-Za-z\\])[A-Za-z]\s*=\s*\d+(?:\.\d+)?\*?[A-Za-z](?![A-Za-z])")
# A letter naming a triple: "A(0, 0, 3)", "p = (2, 5, 6)", "a = 2i + j + 3k" (to the line's end
# or the next comma-free stop).
_NAMED = re.compile(
    r"(?<![A-Za-z\\])([A-Za-z])\s*(?:=\s*)?((?:[(<\u27e8][^()<>\u27e8\u27e9]*[)>\u27e9])"
    r"|(?:[-+]?\s*\d*(?:\.\d+)?\s*\*?\s*[ijk](?![A-Za-z])\s*){2,3})"
)
# A triple written as a vector: "b = (2, 0, 1)", "<1, 2, 3>", "⟨1, 2, 3⟩", "vector (1, 2, 3)".
_AS_VECTOR = re.compile(
    r"((?<=[=])\s*\([^()]*\)|[<\u27e8][^<>\u27e8\u27e9]*[>\u27e9]|(?<=vector)\s*\([^()]*\))"
)
# The reply giving a letter a value: "d = 2", "$D = 10.44\,\mathrm{m}$", "d = \sqrt{109}",
# "\theta \approx 70.53^\circ" (never a term of a formula: "x = 2x + 1", "d = 3 - 1").
_GIVEN = re.compile(
    r"(?<![A-Za-z\\_{])(\\theta|\u03b8|[A-Za-z])\s*(?:=|\\approx|\u2248)\s*"
    r"(?:(\d+(?:\.\d+)?)(?![\d.A-Za-z])(?!\s*[+\-*/^(])|\\sqrt\{(\d+)\}(?!\s*[+\-*/^]))"
)
# A letter after a number and a space is its unit ("12 m", "3 h").
_AFTER_NUMBER = re.compile(r"\d\s+$")
_UNIT_GAP = 8


@dataclass(frozen=True)
class Question:
    """What the question states, for the check: its numbers, triples, letters and words."""

    numbers: tuple[Written, ...]
    # The values the question gives a changing quantity ("when r = 3 cm", where "h = 3r").
    changing: frozenset[Fraction]
    pairs: frozenset[tuple[Fraction, Fraction]]
    triples: frozenset[Triple]
    letters: frozenset[str]
    terms: frozenset[str]
    # Each "letter = term" relation the question writes ("h = 3r"), as written, and each
    # value it gives a letter ("r = 5 cm": ("r", 5)).
    relations: frozenset[str]
    assigned: frozenset[tuple[str, Fraction]]
    # The points the question names ("P(4, -3, 5)", "A(0, 0)", "a = 2i + j + 3k"), and the
    # values the reply works out for its letters ("d = 2"), each with its decimal places.
    named: frozenset[tuple[str, Point]]
    reply_values: frozenset[tuple[str, float, int]]
    words: str
    texts: tuple[str, ...]
    # The triples the question writes as vectors ("b = (2, 0, 1)", "2i - j + 3k", "<1, 2, 3>"),
    # never a point's coordinates ("B(4, 5, 6)").
    vectors: frozenset[Triple] = frozenset()
    # The letters the question itself writes, and the points the reply names.
    stated_letters: frozenset[str] = frozenset()
    reply_named: frozenset[tuple[str, Point]] = frozenset()

    def states_triple(self, triple: Triple) -> bool:
        """A point the question places, or the origin. A point it does not ((4, 0, 0) below
        P(4, -3, 5)) is the reply's reading: round 3's c081 drew a foot under P as one of the
        two points √12 from it."""
        return all(value == 0 for value in triple) or triple in self.triples

    def names_right(self, name: str, at: Point) -> bool:
        """``name`` is no other point's: "A(0, 0, 3)" makes (2, 8, 1) no A, "A(0, 0)" makes
        (4, 0) no A, and "a = 2i + j + 3k" makes (-3, 4, -1) no a."""
        named = {written for letter, written in self.named if letter == name}
        named = {written for written in named if len(written) == len(at)}
        others = {letter for letter, written in self.named if written == at}
        return (not named or at in named) and (not others or name in others)

    def confirms(self, name: str, at: Point) -> bool:
        """A letter the question writes stands at ``at`` only where the question or the reply
        names it there: "OABCDEFG is a cuboid" puts no B anywhere in particular."""
        if name not in self.stated_letters:
            return self.names_right(name, at)
        return self.names_right(name, at) and (name, at) in self.named | self.reply_named

    def value_of(self, letter: str) -> set[float]:
        """The values the reply works out for ``letter`` ("d = 2", "D = \\sqrt{109}")."""
        return {value for name, value, _places in self.reply_values if name == letter}

    def agrees(self, letter: str, size: float) -> bool:
        """The reply works ``letter`` out, and every value it gives it is ``size`` as rounded
        to the places it writes ("r ≈ 4.3" for 4.301)."""
        given = [(value, places) for name, value, places in self.reply_values if name == letter]
        return bool(given) and all(
            abs(value - size) <= 0.5 * 10.0**-places + 1e-9 * max(1.0, abs(size))
            for value, places in given
        )


def _one_number(part: str) -> Fraction | None:
    found = written_numbers(part)
    return found[0].value if len(found) == 1 else None


def written_triples(text: str) -> set[Triple]:
    """The triples a text writes: bracketed coordinates, and vectors in i, j and k."""
    lowered = text.replace("\u2212", "-")
    found: set[Triple] = set()
    for inside in _TRIPLE.findall(lowered):
        parts = [_one_number(part) for part in inside.split(",")]
        x, y, z = parts if len(parts) == 3 else (None, None, None)
        if x is not None and y is not None and z is not None:
            found.add((x, y, z))
    for run in _UNIT_RUN.finditer(lowered):
        components = {"i": Fraction(0), "j": Fraction(0), "k": Fraction(0)}
        seen: set[str] = set()
        for sign, number, unit in _UNIT_TERM.findall(run.group()):
            if unit in seen:
                break
            seen.add(unit)
            value = Fraction(number) if number else Fraction(1)
            components[unit] = -value if sign in {"-", "\u2212"} else value
        else:
            if len(seen) >= 2:
                found.add((components["i"], components["j"], components["k"]))
    return found


def named_points(text: str) -> set[tuple[str, Point]]:
    """The points a text names: "A(0, 0, 3)", "A(0, 0)", "p = (2, 5, 6)", "a = 2i + j + 3k"."""
    found: set[tuple[str, Point]] = set()
    for match in _NAMED.finditer(text.replace("\u2212", "-")):
        for point in [*written_triples(match.group(2)), *written_pairs(match.group(2))]:
            found.add((match.group(1), point))
    return found


def written_vectors(text: str) -> set[Triple]:
    """The triples a text writes as vectors: in i, j and k, in angle brackets, or given a
    letter with "=" ("b = (2, 0, 1)"), never a point's "B(4, 5, 6)"."""
    lowered = text.replace("\u2212", "-")
    found = {
        triple for run in _UNIT_RUN.finditer(lowered) for triple in written_triples(run.group())
    }
    for match in _AS_VECTOR.finditer(lowered):
        found |= written_triples(match.group(1))
    return found


_EXACT_PLACES = 9


def _reply_values(reply: str) -> set[tuple[str, float, int]]:
    """Each value the reply's working gives a letter, with its decimal places: "d = 2",
    "D = 10.44 m", "d = \\sqrt{109}" (exact)."""
    found: set[tuple[str, float, int]] = set()
    degrees = reply.replace("^{\\circ}", "\u00b0").replace("^\\circ", "\u00b0")
    for written, number, root in _GIVEN.findall(degrees):
        letter = "\u03b8" if written == "\\theta" else written
        if number:
            found.add((letter, float(number), len(number.partition(".")[2])))
        elif root:
            found.add((letter, float(root) ** 0.5, _EXACT_PLACES))
    return found


def _letters(text: str) -> set[str]:
    found: set[str] = set()
    for match in _LETTER.finditer(text):
        letter = match.group(1)
        after = text[match.end() : match.end() + 2]
        if letter in _ENGLISH and len(after) == 2 and after[0] == " " and after[1].isalpha():
            continue
        if _AFTER_NUMBER.search(text, max(0, match.start() - _UNIT_GAP), match.start()):
            continue
        found.add(letter + match.group(2).replace("'", "\u2032"))
    for greek, spellings in _GREEK.items():
        if any(spelling in text for spelling in spellings):
            found.add(greek)
    return found


def _capitals(text: str) -> set[str]:
    """The capitals a text names points by, in runs too: "OABCDEFG is a cuboid", "OB"."""
    found: set[str] = set()
    for match in _CAPITALS.finditer(text):
        run = match.group()
        after = text[match.end() : match.end() + 2]
        if run in _ENGLISH and len(after) == 2 and after[0] == " " and after[1].isalpha():
            continue
        found |= set(run)
    return found


def read_question(texts: Sequence[str], reply: str) -> Question:
    """What ``texts`` (the last user message first, then earlier ones) state; ``reply`` adds
    the letters its working names."""
    own = own_texts(list(texts))
    numbers = tuple(number for text in own for number in written_numbers(text))
    pairs = frozenset(pair for text in own for pair in written_pairs(text))
    triples = frozenset(triple for text in own for triple in written_triples(text))
    stated_letters = frozenset(set().union(*(_letters(text) | _capitals(text) for text in texts)))
    letters = stated_letters | _letters(reply)
    terms = frozenset(
        f"{Fraction(number)}{letter}" for text in texts for number, letter in _TERM.findall(text)
    )
    named = frozenset(pair for text in own for pair in named_points(text))
    reply_values = frozenset(_reply_values(reply))
    relations = frozenset(match.group() for text in texts for match in _RELATION.finditer(text))
    assigned = frozenset(
        (letter, Fraction(value)) for text in own for letter, value in ASSIGNED.findall(text)
    )
    words = " ".join(texts).lower()
    return Question(
        numbers,
        frozenset(changing_values(own)),
        pairs,
        triples,
        letters,
        terms,
        relations,
        assigned,
        named,
        reply_values,
        words,
        tuple(own),
        frozenset(triple for text in own for triple in written_vectors(text)),
        stated_letters,
        frozenset(named_points(reply)),
    )
