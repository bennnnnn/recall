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
    words: str
    texts: tuple[str, ...]

    def states_triple(self, triple: Triple) -> bool:
        """A point the question places, or its foot on an axis or a coordinate plane: each
        coordinate is the stated one or 0 ((4, 0, 0) beneath P(4, -3, 5))."""
        if all(value == 0 for value in triple):
            return True
        return any(
            all(mine in {theirs, 0} for mine, theirs in zip(triple, stated, strict=True))
            for stated in self.triples
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
    words = " ".join(texts).lower()
    return Question(
        numbers, frozenset(changing_values(own)), pairs, triples, letters, terms, words, tuple(own)
    )
