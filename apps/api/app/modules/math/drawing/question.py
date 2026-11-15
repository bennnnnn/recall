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
    Written,
    changing_values,
    own_texts,
    written_numbers,
    written_pairs,
)

Triple = tuple[Fraction, Fraction, Fraction]

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
# The reply giving a letter a value: "d = 2", "$D = 10.44\,\mathrm{m}$", "d = \sqrt{109}",
# "\theta \approx 70.53^\circ" (never a term of a formula: "x = 2x + 1", "d = 3 - 1").
_GIVEN = re.compile(
    r"(?<![A-Za-z\\_{])(\\theta|\u03b8|[A-Za-z])\s*(?:=|\\approx|\u2248)\s*"
    r"(?:(\d+(?:\.\d+)?)(?![\d.A-Za-z])(?!\s*[+\-*/^(])|\\sqrt\{(\d+)\}(?!\s*[+\-*/^]))"
)
# A value given a letter: "r = 5 cm", "h=12".
_ASSIGNED = re.compile(r"(?<![A-Za-z\\])([A-Za-z])\s*=\s*(\d+(?:\.\d+)?)(?![\d.A-Za-z])")
# The words that say which part a stated size is, and how near the number they stand.
_ROLE_WORDS = {
    "radius": "radius", "radii": "radius", "diameter": "diameter", "across": "diameter",
    "height": "height", "high": "height", "tall": "height", "depth": "depth", "deep": "depth",
    "width": "width", "wide": "width", "breadth": "width", "length": "length", "long": "length",
    "side": "side", "sides": "side", "edge": "side", "slant": "slant",
}  # fmt: skip
_BEFORE, _AFTER = 3, 2
# A letter after a number and a space is its unit ("12 m", "3 h").
_AFTER_NUMBER = re.compile(r"\d\s+$")


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
    # The triples the question names ("P(4, -3, 5)", "a = 2i + j + 3k"), and the values the
    # reply works out for its letters ("d = 2").
    named: frozenset[tuple[str, Triple]]
    reply_values: frozenset[tuple[str, float]]
    words: str
    texts: tuple[str, ...]

    def roles(self, value: float) -> set[str]:
        """The parts the question names right beside ``value`` ("radius 5 cm", "12 m long"):
        empty when it names none there ("a 20 cm by 30 cm sheet")."""
        found: set[str] = set()
        for text in self.texts:
            words = re.findall(r"[a-z]+|\d+(?:\.\d+)?", text.lower())
            for at, word in enumerate(words):
                if word.replace(".", "", 1).isdigit() and abs(float(word) - value) < 1e-9:
                    near = words[max(0, at - _BEFORE) : at] + words[at + 1 : at + 1 + _AFTER]
                    found |= {_ROLE_WORDS[w] for w in near if w in _ROLE_WORDS}
        return found

    def states_triple(self, triple: Triple) -> bool:
        """A point the question places, or the origin. A point it does not ((4, 0, 0) below
        P(4, -3, 5)) is the reply's reading: round 3's c081 drew a foot under P as one of the
        two points √12 from it."""
        return all(value == 0 for value in triple) or triple in self.triples

    def names_right(self, name: str, triple: Triple) -> bool:
        """``name`` is no other triple's: "A(0, 0, 3)" makes (2, 8, 1) no A, and "a = 2i + j +
        3k" makes (-3, 4, -1) no a."""
        named = {written for letter, written in self.named if letter == name}
        others = {letter for letter, written in self.named if written == triple}
        return (not named or triple in named) and (not others or name in others)

    def value_of(self, letter: str) -> set[float]:
        """The values the reply works out for ``letter`` ("d = 2", "D = \\sqrt{109}")."""
        return {value for name, value in self.reply_values if name == letter}


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


def named_triples(text: str) -> set[tuple[str, Triple]]:
    """The triples a text names: "A(0, 0, 3)", "p = (2, 5, 6)", "a = 2i + j + 3k"."""
    found: set[tuple[str, Triple]] = set()
    for match in _NAMED.finditer(text.replace("\u2212", "-")):
        for triple in written_triples(match.group(2)):
            found.add((match.group(1), triple))
    return found


def _reply_values(reply: str) -> set[tuple[str, float]]:
    """Each value the reply's working gives a letter: "d = 2", "D = 10.44 m", "d = \\sqrt{109}"."""
    found: set[tuple[str, float]] = set()
    degrees = reply.replace("^{\\circ}", "\u00b0").replace("^\\circ", "\u00b0")
    for written, number, root in _GIVEN.findall(degrees):
        letter = "\u03b8" if written == "\\theta" else written
        if number:
            found.add((letter, float(number)))
        elif root:
            found.add((letter, float(root) ** 0.5))
    return found


def _letters(text: str) -> set[str]:
    found: set[str] = set()
    for match in _LETTER.finditer(text):
        letter = match.group(1)
        after = text[match.end() : match.end() + 2]
        if letter in _ENGLISH and len(after) == 2 and after[0] == " " and after[1].isalpha():
            continue
        if _AFTER_NUMBER.search(text[: match.start()]):
            continue
        found.add(letter + match.group(2).replace("'", "\u2032"))
    for greek, spellings in _GREEK.items():
        if any(spelling in text for spelling in spellings):
            found.add(greek)
    return found


def read_question(texts: Sequence[str], reply: str) -> Question:
    """What ``texts`` (the last user message first, then earlier ones) state; ``reply`` adds
    the letters its working names."""
    own = own_texts(list(texts))
    numbers = tuple(number for text in own for number in written_numbers(text))
    pairs = frozenset(pair for text in own for pair in written_pairs(text))
    triples = frozenset(triple for text in own for triple in written_triples(text))
    letters = frozenset(set().union(*(_letters(text) for text in [*texts, reply])))
    terms = frozenset(
        f"{Fraction(number)}{letter}" for text in texts for number, letter in _TERM.findall(text)
    )
    named = frozenset(pair for text in own for pair in named_triples(text))
    reply_values = frozenset(_reply_values(reply))
    relations = frozenset(match.group() for text in texts for match in _RELATION.finditer(text))
    assigned = frozenset(
        (letter, Fraction(value)) for text in own for letter, value in _ASSIGNED.findall(text)
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
    )
